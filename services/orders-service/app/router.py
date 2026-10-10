from collections.abc import AsyncIterator
from typing import Any, Literal
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import db
from .limiter import enforce_payment_rate_limit
from .models import (
    InvoiceModel,
    OrderModel,
    PaymentModel,
    SagaInstanceModel,
    SagaStepModel,
)
from .saga import execute_saga


router = APIRouter(prefix="/orders", tags=["Saga Orchestrator Orders"])


class CreateOrderRequest(BaseModel):
    flight_offer_id: UUID
    hotel_offer_id: UUID
    car_offer_id: UUID
    passengers: int = Field(default=1, ge=1, le=9)
    rooms: int = Field(default=1, ge=1, le=5)
    idempotency_key: str = Field(min_length=1, max_length=64)
    simulate_failure_at: Literal["FLIGHT", "HOTEL", "CAR", "PAYMENT"] | None = None


async def get_async_session() -> AsyncIterator[AsyncSession]:
    # db.session es una dependencia (generador), no un context manager: se usa el sessionmaker.
    async with db.sessionmaker() as session:
        yield session


@router.post("", status_code=202)
async def create_order(
    payload: CreateOrderRequest,
    background_tasks: BackgroundTasks,
    response: Response,
    user_id: UUID = Header(alias="X-User-ID"),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    await enforce_payment_rate_limit(str(user_id), response)
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"{user_id}:{payload.idempotency_key}"},
    )
    existing_result = await session.execute(
        select(OrderModel).where(
            OrderModel.user_id == str(user_id),
            OrderModel.idempotency_key == payload.idempotency_key,
        )
    )
    order = existing_result.scalar_one_or_none()
    if order is not None:
        response.status_code = 200
        return await _order_data(session, order)

    order_id = str(uuid4())
    saga_id = str(uuid4())
    simulate_failure_at = (
        payload.simulate_failure_at if settings.enable_fault_injection else None
    )
    order = OrderModel(
        id=order_id,
        user_id=str(user_id),
        idempotency_key=payload.idempotency_key,
        status="PENDING",
        flight_offer_id=str(payload.flight_offer_id),
        hotel_offer_id=str(payload.hotel_offer_id),
        car_offer_id=str(payload.car_offer_id),
        passengers=payload.passengers,
        rooms=payload.rooms,
        currency="USD",
    )
    saga = SagaInstanceModel(
        id=saga_id,
        order_id=order_id,
        status="STARTED",
        simulate_failure_at=simulate_failure_at,
    )
    session.add_all([order, saga])
    await session.commit()

    background_tasks.add_task(_run_saga_background, saga_id)
    return await _order_data(session, order)


@router.get("/{order_id}")
async def get_order(
    order_id: UUID,
    user_id: UUID = Header(alias="X-User-ID"),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    result = await session.execute(
        select(OrderModel).where(
            OrderModel.id == str(order_id),
            OrderModel.user_id == str(user_id),
        )
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="ORDER_NOT_FOUND")
    return await _order_data(session, order)


@router.get("")
async def list_orders(
    limit: int = 20,
    offset: int = 0,
    user_id: UUID = Header(alias="X-User-ID"),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    if limit < 1 or limit > 50 or offset < 0:
        raise HTTPException(status_code=422, detail="INVALID_PAGINATION")
    total_result = await session.execute(
        select(func.count()).select_from(OrderModel).where(OrderModel.user_id == str(user_id))
    )
    orders_result = await session.execute(
        select(OrderModel)
        .where(OrderModel.user_id == str(user_id))
        .order_by(OrderModel.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return {
        "items": [
            await _order_data(session, order)
            for order in orders_result.scalars()
        ],
        "total": total_result.scalar_one(),
    }


async def _run_saga_background(saga_id: str) -> None:
    async with db.sessionmaker() as session:
        async with httpx.AsyncClient(timeout=settings.saga_step_timeout_seconds) as client:
            await execute_saga(session, saga_id, client)


async def _order_data(
    session: AsyncSession,
    order: OrderModel,
) -> dict[str, Any]:
    saga_result = await session.execute(
        select(SagaInstanceModel).where(SagaInstanceModel.order_id == order.id)
    )
    saga = saga_result.scalar_one()
    steps_result = await session.execute(
        select(SagaStepModel)
        .where(SagaStepModel.saga_id == saga.id)
        .order_by(SagaStepModel.started_at, SagaStepModel.id)
    )
    steps = list(steps_result.scalars())

    payment_result = await session.execute(
        select(PaymentModel).where(PaymentModel.order_id == order.id)
    )
    payment = payment_result.scalar_one_or_none()
    invoice_result = await session.execute(
        select(InvoiceModel).where(InvoiceModel.order_id == order.id)
    )
    invoice = invoice_result.scalar_one_or_none()

    return {
        "id": order.id,
        "user_id": order.user_id,
        "status": order.status,
        "flight_offer_id": order.flight_offer_id,
        "hotel_offer_id": order.hotel_offer_id,
        "car_offer_id": order.car_offer_id,
        "passengers": order.passengers,
        "rooms": order.rooms,
        "subtotal": _decimal(order.subtotal),
        "taxes": _decimal(order.taxes),
        "total_amount": _decimal(order.total_amount),
        "currency": order.currency,
        "saga": {
            "id": saga.id,
            "status": saga.status,
            "current_step": saga.current_step,
            "simulate_failure_at": saga.simulate_failure_at,
            "failure_reason": saga.failure_reason,
            "steps": [
                {
                    "step": step.step,
                    "action": step.action,
                    "status": step.status,
                    "attempt": step.attempt,
                    "external_ref": step.external_ref,
                    "error_code": step.error_code,
                    "error_message": step.error_message,
                    "started_at": step.started_at,
                    "finished_at": step.finished_at,
                }
                for step in steps
            ],
        },
        "payment": (
            {
                "status": payment.status,
                "amount": _decimal(payment.amount),
                "currency": payment.currency,
                "provider_ref": payment.provider_ref,
            }
            if payment is not None else None
        ),
        "invoice": (
            {
                "number": invoice.number,
                "subtotal": _decimal(invoice.subtotal),
                "taxes": _decimal(invoice.taxes),
                "total": _decimal(invoice.total),
                "currency": invoice.currency,
                "issued_at": invoice.issued_at,
            }
            if invoice is not None else None
        ),
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


def _decimal(value: Any) -> str | None:
    return str(value) if value is not None else None
