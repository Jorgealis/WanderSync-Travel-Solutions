"""Reservas de inventario con semántica SAGA, compartidas por flights, hotels y cars.

Implementa el contrato de docs/contratos/api-interna.md §2:

    POST /reservations                   reservar (paso de la SAGA), idempotente por saga_id
    POST /reservations/{saga_id}/cancel  compensación, idempotente, con tombstone
    POST /reservations/{saga_id}/confirm confirmación tras el pago, idempotente
    GET  /reservations/{saga_id}

Garantías:
- **Sin sobreventa**: la oferta se bloquea con SELECT ... FOR UPDATE antes de descontar.
- **Idempotencia**: UNIQUE(saga_id). Una reserva repetida devuelve la original (200).
- **Tombstone**: cancelar un saga_id desconocido deja una fila CANCELLED; si la reserva
  original llega tarde, choca con el UNIQUE y se rechaza. Así una compensación nunca
  queda "por detrás" de la reserva que compensa.
- **Precio**: siempre el de la oferta en el momento de reservar, nunca el del cliente.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import CheckConstraint, DateTime, Integer, Numeric, String, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from wandersync_common.config import ServiceSettings
from wandersync_common.db import Database
from wandersync_common.errors import AppError

RESERVED, CONFIRMED, CANCELLED = "RESERVED", "CONFIRMED", "CANCELLED"


class ReservationMixin:
    """Columnas comunes de `<esquema>.reservations`. Cada servicio declara `offer_id` con su FK."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    saga_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    order_id: Mapped[uuid.UUID | None]
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), server_default="USD")
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        CheckConstraint(f"status IN ('{RESERVED}', '{CONFIRMED}', '{CANCELLED}')", name="status_valid"),
        # Solo un tombstone puede carecer de oferta o cantidad.
        CheckConstraint(
            f"status = '{CANCELLED}' OR (offer_id IS NOT NULL AND quantity > 0)", name="offer_required"
        ),
    )


class ReserveRequest(BaseModel):
    saga_id: uuid.UUID
    order_id: uuid.UUID
    offer_id: uuid.UUID
    quantity: int = Field(gt=0, le=9)


class ReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    saga_id: uuid.UUID
    order_id: uuid.UUID | None
    offer_id: uuid.UUID | None
    quantity: int
    unit_price: Decimal | None
    total_price: Decimal | None
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class InventorySpec:
    """Qué tabla de ofertas y qué columna de inventario maneja un servicio."""

    offer_model: type
    reservation_model: type
    available_column: str  # p. ej. "seats_available"
    unit_price: Callable[[Any], Decimal]  # precio por unidad reservada, tomado de la oferta


def _out(reservation: Any, status_code: int) -> JSONResponse:
    body = ReservationOut.model_validate(reservation).model_dump(mode="json")
    return JSONResponse(status_code=status_code, content=body)


def reservation_router(db: Database, spec: InventorySpec, settings: ServiceSettings) -> APIRouter:
    router = APIRouter(prefix="/reservations", tags=["reservations"])
    Offer, Reservation = spec.offer_model, spec.reservation_model

    async def locked_reservation(session: AsyncSession, saga_id: uuid.UUID) -> Any:
        stmt = select(Reservation).where(Reservation.saga_id == saga_id).with_for_update()
        return await session.scalar(stmt)

    async def locked_offer(session: AsyncSession, offer_id: uuid.UUID) -> Any:
        return await session.scalar(select(Offer).where(Offer.id == offer_id).with_for_update())

    @router.post("")
    async def reserve(
        body: ReserveRequest,
        x_simulate_failure: Annotated[str | None, Header()] = None,
    ) -> JSONResponse:
        for attempt in range(2):  # 2º intento solo si otra petición con el mismo saga_id ganó la carrera
            try:
                async with db.sessionmaker() as session, session.begin():
                    existing = await locked_reservation(session, body.saga_id)
                    if existing is not None:
                        if existing.status == CANCELLED:
                            raise AppError(409, "RESERVATION_CANCELLED", "The saga already compensated this reservation")
                        return _out(existing, 200)  # replay idempotente

                    if settings.enable_fault_injection and (x_simulate_failure or "").lower() == "true":
                        raise AppError(409, "SIMULATED_FAILURE", "Simulated failure requested by the SAGA (demo)")

                    offer = await locked_offer(session, body.offer_id)
                    if offer is None:
                        raise AppError(404, "OFFER_NOT_FOUND", f"Offer {body.offer_id} does not exist")
                    available = getattr(offer, spec.available_column)
                    if available < body.quantity:
                        raise AppError(
                            409,
                            "INSUFFICIENT_AVAILABILITY",
                            f"Only {available} unit(s) available, requested {body.quantity}",
                            {"available": available, "requested": body.quantity},
                        )

                    setattr(offer, spec.available_column, available - body.quantity)
                    unit_price = spec.unit_price(offer)
                    reservation = Reservation(
                        saga_id=body.saga_id,
                        order_id=body.order_id,
                        offer_id=body.offer_id,
                        quantity=body.quantity,
                        unit_price=unit_price,
                        total_price=unit_price * body.quantity,
                        currency=offer.currency,
                        status=RESERVED,
                    )
                    session.add(reservation)
                    await session.flush()
                    await session.refresh(reservation)
                    return _out(reservation, 201)
            except IntegrityError:
                if attempt == 1:
                    raise
        raise AssertionError("unreachable")

    @router.post("/{saga_id}/cancel")
    async def cancel(saga_id: uuid.UUID) -> JSONResponse:
        for attempt in range(2):
            try:
                async with db.sessionmaker() as session, session.begin():
                    reservation = await locked_reservation(session, saga_id)
                    if reservation is None:
                        # Tombstone: la reserva nunca llegó (p. ej. timeout); si llega tarde, se rechaza.
                        reservation = Reservation(saga_id=saga_id, quantity=0, status=CANCELLED)
                        session.add(reservation)
                    elif reservation.status == CONFIRMED:
                        raise AppError(409, "RESERVATION_ALREADY_CONFIRMED", "Confirmed reservations cannot be compensated")
                    elif reservation.status == RESERVED:
                        offer = await locked_offer(session, reservation.offer_id)
                        setattr(offer, spec.available_column, getattr(offer, spec.available_column) + reservation.quantity)
                        reservation.status = CANCELLED
                    await session.flush()
                    await session.refresh(reservation)
                    return _out(reservation, 200)
            except IntegrityError:
                if attempt == 1:
                    raise
        raise AssertionError("unreachable")

    @router.post("/{saga_id}/confirm")
    async def confirm(saga_id: uuid.UUID) -> JSONResponse:
        async with db.sessionmaker() as session, session.begin():
            reservation = await locked_reservation(session, saga_id)
            if reservation is None:
                raise AppError(404, "RESERVATION_NOT_FOUND", f"No reservation for saga {saga_id}")
            if reservation.status == CANCELLED:
                raise AppError(409, "RESERVATION_CANCELLED", "Cancelled reservations cannot be confirmed")
            reservation.status = CONFIRMED
            await session.flush()
            await session.refresh(reservation)
            return _out(reservation, 200)

    @router.get("/{saga_id}")
    async def get_reservation(saga_id: uuid.UUID) -> JSONResponse:
        async with db.sessionmaker() as session:
            reservation = await session.scalar(select(Reservation).where(Reservation.saga_id == saga_id))
            if reservation is None:
                raise AppError(404, "RESERVATION_NOT_FOUND", f"No reservation for saga {saga_id}")
            return _out(reservation, 200)

    return router
