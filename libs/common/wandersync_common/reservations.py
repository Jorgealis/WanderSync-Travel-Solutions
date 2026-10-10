from collections.abc import AsyncIterator, Callable
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from wandersync_common.errors import AppError


class ReserveRequest(BaseModel):
    saga_id: UUID
    order_id: UUID
    offer_id: UUID
    quantity: int = Field(gt=0)


def create_reservation_router(
    *,
    tag: str,
    offer_model: type[DeclarativeBase],
    reservation_model: type[DeclarativeBase],
    inventory_field: str,
    unit_price_field: str,
    session_dependency: Callable[..., AsyncIterator[AsyncSession]],
    fault_injection_enabled: bool,
    quantity_must_be_one: bool = False,
) -> APIRouter:
    router = APIRouter(prefix="/reservations", tags=[tag])
    offer_id_column = getattr(offer_model, "id")
    saga_id_column = getattr(reservation_model, "saga_id")

    @router.post("", status_code=201)
    async def create_reservation(
        payload: ReserveRequest,
        response: Response,
        x_simulate_failure: bool = Header(False),
        session: AsyncSession = Depends(session_dependency),
    ) -> dict[str, Any]:
        if quantity_must_be_one and payload.quantity != 1:
            raise AppError(422, "VALIDATION_ERROR", "Car quantity must be exactly one")
        if fault_injection_enabled and x_simulate_failure:
            raise AppError(409, "SIMULATED_FAILURE", "Reservation failed by simulation")

        async with session.begin():
            existing_result = await session.execute(
                select(reservation_model)
                .where(saga_id_column == str(payload.saga_id))
                .with_for_update()
            )
            existing = existing_result.scalar_one_or_none()
            if existing is not None:
                if existing.status == "CANCELLED":
                    raise AppError(409, "RESERVATION_CANCELLED", "The saga has already been cancelled")
                _validate_replay(existing, payload)
                response.status_code = 200
                return _reservation_data(existing)

            offer_result = await session.execute(
                select(offer_model)
                .where(offer_id_column == str(payload.offer_id))
                .with_for_update()
            )
            offer = offer_result.scalar_one_or_none()
            if offer is None:
                raise AppError(404, "OFFER_NOT_FOUND", "The offer does not exist")

            available = getattr(offer, inventory_field)
            if available < payload.quantity:
                raise AppError(
                    409,
                    "INSUFFICIENT_AVAILABILITY",
                    "The requested quantity is not available",
                    {"available": available, "requested": payload.quantity},
                )

            unit_price = Decimal(str(getattr(offer, unit_price_field)))
            insert_result = await session.execute(
                insert(reservation_model)
                .values(
                    id=str(uuid4()),
                    saga_id=str(payload.saga_id),
                    order_id=str(payload.order_id),
                    offer_id=str(payload.offer_id),
                    quantity=payload.quantity,
                    unit_price=unit_price,
                    total_price=unit_price * payload.quantity,
                    currency="USD",
                    status="RESERVED",
                )
                .on_conflict_do_nothing(index_elements=["saga_id"])
                .returning(saga_id_column)
            )
            inserted_saga_id = insert_result.scalar_one_or_none()
            if inserted_saga_id is None:
                replay_result = await session.execute(
                    select(reservation_model)
                    .where(saga_id_column == str(payload.saga_id))
                    .with_for_update()
                )
                replay = replay_result.scalar_one()
                if replay.status == "CANCELLED":
                    raise AppError(409, "RESERVATION_CANCELLED", "The saga has already been cancelled")
                _validate_replay(replay, payload)
                response.status_code = 200
                return _reservation_data(replay)

            setattr(offer, inventory_field, available - payload.quantity)
            created_result = await session.execute(
                select(reservation_model).where(saga_id_column == str(payload.saga_id))
            )
            return _reservation_data(created_result.scalar_one())

    @router.post("/{saga_id}/cancel")
    async def cancel_reservation(
        saga_id: UUID,
        session: AsyncSession = Depends(session_dependency),
    ) -> dict[str, str]:
        async with session.begin():
            reservation_result = await session.execute(
                select(reservation_model)
                .where(saga_id_column == str(saga_id))
                .with_for_update()
            )
            reservation = reservation_result.scalar_one_or_none()

            if reservation is None:
                await session.execute(
                    insert(reservation_model)
                    .values(
                        id=str(uuid4()),
                        saga_id=str(saga_id),
                        order_id=None,
                        offer_id=None,
                        quantity=0,
                        unit_price=None,
                        total_price=None,
                        currency="USD",
                        status="CANCELLED",
                    )
                    .on_conflict_do_nothing(index_elements=["saga_id"])
                )
                return {"status": "CANCELLED", "saga_id": str(saga_id)}

            if reservation.status == "CONFIRMED":
                raise AppError(
                    409,
                    "RESERVATION_ALREADY_CONFIRMED",
                    "Confirmed reservations cannot be cancelled",
                )
            if reservation.status == "CANCELLED":
                return {"status": "CANCELLED", "saga_id": str(saga_id)}

            offer_result = await session.execute(
                select(offer_model)
                .where(offer_id_column == reservation.offer_id)
                .with_for_update()
            )
            offer = offer_result.scalar_one_or_none()
            if offer is None:
                raise AppError(
                    500,
                    "INTERNAL",
                    "The offer for this reservation no longer exists",
                )

            setattr(
                offer,
                inventory_field,
                getattr(offer, inventory_field) + reservation.quantity,
            )
            reservation.status = "CANCELLED"
            return {"status": "CANCELLED", "saga_id": str(saga_id)}

    @router.post("/{saga_id}/confirm")
    async def confirm_reservation(
        saga_id: UUID,
        session: AsyncSession = Depends(session_dependency),
    ) -> dict[str, str]:
        async with session.begin():
            reservation_result = await session.execute(
                select(reservation_model)
                .where(saga_id_column == str(saga_id))
                .with_for_update()
            )
            reservation = reservation_result.scalar_one_or_none()
            if reservation is None:
                raise AppError(404, "RESERVATION_NOT_FOUND", "The reservation does not exist")
            if reservation.status == "CANCELLED":
                raise AppError(409, "RESERVATION_CANCELLED", "The reservation was cancelled")
            reservation.status = "CONFIRMED"
            return {"status": "CONFIRMED", "saga_id": str(saga_id)}

    @router.get("/{saga_id}")
    async def get_reservation(
        saga_id: UUID,
        session: AsyncSession = Depends(session_dependency),
    ) -> dict[str, Any]:
        result = await session.execute(
            select(reservation_model).where(saga_id_column == str(saga_id))
        )
        reservation = result.scalar_one_or_none()
        if reservation is None:
            raise HTTPException(status_code=404, detail="RESERVATION_NOT_FOUND")
        return _reservation_data(reservation)

    return router


def _validate_replay(reservation: Any, payload: ReserveRequest) -> None:
    if (
        reservation.order_id != str(payload.order_id)
        or reservation.offer_id != str(payload.offer_id)
        or reservation.quantity != payload.quantity
    ):
        raise AppError(
            409,
            "RESERVATION_IDEMPOTENCY_CONFLICT",
            "The saga ID was already used with a different reservation request",
        )


def _reservation_data(reservation: Any) -> dict[str, Any]:
    return {
        "id": reservation.id,
        "saga_id": reservation.saga_id,
        "order_id": reservation.order_id,
        "offer_id": reservation.offer_id,
        "quantity": reservation.quantity,
        "unit_price": str(reservation.unit_price) if reservation.unit_price is not None else None,
        "total_price": str(reservation.total_price) if reservation.total_price is not None else None,
        "currency": reservation.currency,
        "status": reservation.status,
        "created_at": reservation.created_at,
        "updated_at": reservation.updated_at,
    }
