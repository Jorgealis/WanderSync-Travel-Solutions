import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models import (
    InvoiceModel,
    OrderModel,
    PaymentModel,
    SagaInstanceModel,
    SagaStepModel,
)
from .db import db


class RemoteStepError(Exception):
    def __init__(self, code: str, message: str, *, transient: bool) -> None:
        super().__init__(message)
        self.code = code
        self.transient = transient


RemoteOperation = Callable[[], Awaitable[tuple[Any, str | None]]]

RESERVATION_SERVICES = (
    ("RESERVE_FLIGHT", "flights", settings.flights_service_url),
    ("RESERVE_HOTEL", "hotels", settings.hotels_service_url),
    ("RESERVE_CAR", "cars", settings.cars_service_url),
)


async def recover_pending_sagas() -> None:
    async with db.sessionmaker() as session:
        pending_result = await session.execute(
            select(SagaInstanceModel.id).where(
                SagaInstanceModel.status.in_(("STARTED", "COMPENSATING"))
            )
        )
        saga_ids = list(pending_result.scalars())

    for saga_id in saga_ids:
        await _run_recovered_saga(saga_id)


async def _run_recovered_saga(saga_id: str) -> None:
    # El intento que estaba en curso cuando cayó el orquestador nunca terminó: se cierra
    # como interrumpido para que la línea de tiempo no muestre un paso "RUNNING" eterno.
    async with db.sessionmaker() as session, session.begin():
        await session.execute(
            update(SagaStepModel)
            .where(SagaStepModel.saga_id == saga_id, SagaStepModel.status == "RUNNING")
            .values(
                status="FAILED",
                error_code="ORCHESTRATOR_RESTARTED",
                error_message="Interrumpido por un reinicio del orquestador; la SAGA se retomó",
                finished_at=datetime.now(timezone.utc),
            )
        )
    async with db.sessionmaker() as session:
        async with httpx.AsyncClient(timeout=settings.saga_step_timeout_seconds) as client:
            await execute_saga(session, saga_id, client)


async def execute_saga(
    session: AsyncSession,
    saga_id: str,
    client: httpx.AsyncClient,
) -> dict[str, str]:
    saga_result = await session.execute(
        select(SagaInstanceModel)
        .where(SagaInstanceModel.id == saga_id)
        .with_for_update()
    )
    saga = saga_result.scalar_one()
    order_result = await session.execute(
        select(OrderModel).where(OrderModel.id == saga.order_id)
    )
    order = order_result.scalar_one()

    if saga.status == "COMPENSATING":
        await _compensate(session, saga, order, client)
        return {"saga_id": saga.id, "status": saga.status}
    if saga.status in {"COMPLETED", "COMPENSATED", "FAILED"}:
        return {"saga_id": saga.id, "status": saga.status}

    service_data: dict[str, dict[str, Any]] = {}
    order_payload = {
        "flight_offer_id": order.flight_offer_id,
        "hotel_offer_id": order.hotel_offer_id,
        "car_offer_id": order.car_offer_id,
        "passengers": order.passengers,
        "rooms": order.rooms,
    }

    try:
        for step, service, base_url in RESERVATION_SERVICES:
            offer_id = {
                "flights": order_payload["flight_offer_id"],
                "hotels": order_payload["hotel_offer_id"],
                "cars": order_payload["car_offer_id"],
            }[service]
            quantity = (
                order.passengers if service == "flights"
                else order.rooms if service == "hotels"
                else 1
            )
            reservation_data, _ = await _run_step(
                session,
                saga,
                step,
                lambda service=service, base_url=base_url, offer_id=offer_id, quantity=quantity:
                    _reserve(client, base_url, saga.id, order.id, offer_id, quantity, service, saga),
            )
            service_data[service] = reservation_data

        subtotal = sum(
            (Decimal(str(service_data[name]["total_price"])) for name in ("flights", "hotels", "cars")),
            Decimal("0.00"),
        )
        taxes = (subtotal * Decimal(str(settings.tax_rate))).quantize(Decimal("0.01"))
        order.subtotal = subtotal
        order.taxes = taxes
        order.total_amount = subtotal + taxes
        await session.commit()

        await _run_step(
            session,
            saga,
            "PROCESS_PAYMENT",
            lambda: _process_payment(session, order, saga),
        )

        for step, service, base_url in (
            ("CONFIRM_FLIGHT", "flights", settings.flights_service_url),
            ("CONFIRM_HOTEL", "hotels", settings.hotels_service_url),
            ("CONFIRM_CAR", "cars", settings.cars_service_url),
        ):
            await _run_step(
                session,
                saga,
                step,
                lambda base_url=base_url: _confirm(client, base_url, saga.id),
                retry_business_errors=True,
                retry_forever=True,
            )

        await _run_step(
            session,
            saga,
            "ISSUE_INVOICE",
            lambda: _issue_invoice(session, order),
            retry_business_errors=True,
            retry_forever=True,
        )

        saga.status = "COMPLETED"
        saga.current_step = None
        order.status = "CONFIRMED"
        await session.commit()
        return {"saga_id": saga.id, "status": saga.status}
    except (RemoteStepError, httpx.RequestError) as error:
        saga.status = "COMPENSATING"
        saga.failure_reason = f"{saga.current_step}: {error}"
        order.status = "PENDING"
        await session.commit()
        await _compensate(session, saga, order, client)
        return {"saga_id": saga.id, "status": saga.status}


async def _run_step(
    session: AsyncSession,
    saga: SagaInstanceModel,
    name: str,
    operation: RemoteOperation,
    *,
    action: str = "EXECUTE",
    retry_business_errors: bool = False,
    retry_forever: bool = False,
) -> tuple[Any, str | None]:
    previous = await session.execute(
        select(SagaStepModel.attempt)
        .where(
            SagaStepModel.saga_id == saga.id,
            SagaStepModel.step == name,
            SagaStepModel.action == action,
        )
        .order_by(SagaStepModel.attempt.desc())
        .limit(1)
    )
    attempt = previous.scalar_one_or_none() or 0

    while True:
        attempt += 1
        step_record = SagaStepModel(
            id=str(uuid4()),
            saga_id=saga.id,
            step=name,
            action=action,
            status="RUNNING",
            attempt=attempt,
            started_at=datetime.now(timezone.utc),
        )
        session.add(step_record)
        saga.current_step = name
        await session.commit()

        try:
            result, external_ref = await operation()
        except RemoteStepError as error:
            step_record.status = "FAILED"
            step_record.error_code = error.code
            step_record.error_message = str(error)
            step_record.finished_at = datetime.now(timezone.utc)
            await session.commit()
            can_retry = error.transient or retry_business_errors or retry_forever
            if not can_retry or (not retry_forever and attempt > settings.saga_max_retries):
                raise
            await _retry_delay(attempt, retry_forever=retry_forever)
        except httpx.RequestError as error:
            step_record.status = "FAILED"
            step_record.error_code = "UPSTREAM_UNAVAILABLE"
            step_record.error_message = str(error)
            step_record.finished_at = datetime.now(timezone.utc)
            await session.commit()
            if not retry_forever and attempt > settings.saga_max_retries:
                raise
            await _retry_delay(attempt, retry_forever=retry_forever)
        else:
            step_record.status = "SUCCEEDED"
            step_record.external_ref = external_ref
            step_record.finished_at = datetime.now(timezone.utc)
            await session.commit()
            return result, external_ref


async def _reserve(
    client: httpx.AsyncClient,
    base_url: str,
    saga_id: str,
    order_id: str,
    offer_id: str,
    quantity: int,
    service: str,
    saga: SagaInstanceModel,
) -> tuple[dict[str, Any], str | None]:
    headers = _internal_headers()
    if settings.enable_fault_injection and saga.simulate_failure_at == service.upper().rstrip("S"):
        headers["X-Simulate-Failure"] = "true"
    response = await client.post(
        f"{base_url}/reservations",
        json={
            "saga_id": saga_id,
            "order_id": order_id,
            "offer_id": offer_id,
            "quantity": quantity,
        },
        headers=headers,
    )
    data = _response_data(response)
    if not isinstance(data.get("total_price"), str):
        raise RemoteStepError("INVALID_UPSTREAM_RESPONSE", "Reservation omitted total_price", transient=False)
    return data, str(data.get("id", ""))


async def _confirm(
    client: httpx.AsyncClient,
    base_url: str,
    saga_id: str,
) -> tuple[dict[str, Any], str | None]:
    response = await client.post(
        f"{base_url}/reservations/{saga_id}/confirm",
        headers=_internal_headers(),
    )
    return _response_data(response), None


async def _process_payment(
    session: AsyncSession,
    order: OrderModel,
    saga: SagaInstanceModel,
) -> tuple[dict[str, str], str | None]:
    existing_result = await session.execute(
        select(PaymentModel).where(PaymentModel.saga_id == saga.id).with_for_update()
    )
    payment = existing_result.scalar_one_or_none()
    if payment is not None and payment.status == "CAPTURED":
        return {"status": "CAPTURED"}, payment.provider_ref

    if saga.simulate_failure_at == "PAYMENT" and settings.enable_fault_injection:
        if payment is None:
            payment = PaymentModel(
                id=str(uuid4()),
                order_id=order.id,
                saga_id=saga.id,
                amount=order.total_amount,
                currency=order.currency,
                status="FAILED",
            )
            session.add(payment)
        else:
            payment.status = "FAILED"
        await session.commit()
        raise RemoteStepError("SIMULATED_FAILURE", "Payment failed by simulation", transient=False)

    provider_ref = f"PAY-{uuid4().hex[:12].upper()}"
    if payment is None:
        payment = PaymentModel(
            id=str(uuid4()),
            order_id=order.id,
            saga_id=saga.id,
            amount=order.total_amount,
            currency=order.currency,
            status="CAPTURED",
            provider_ref=provider_ref,
        )
        session.add(payment)
    else:
        payment.amount = order.total_amount
        payment.status = "CAPTURED"
        payment.provider_ref = provider_ref
    await session.commit()
    return {"status": "CAPTURED"}, provider_ref


async def _issue_invoice(
    session: AsyncSession,
    order: OrderModel,
) -> tuple[dict[str, str], str | None]:
    existing_result = await session.execute(
        select(InvoiceModel).where(InvoiceModel.order_id == order.id)
    )
    invoice = existing_result.scalar_one_or_none()
    if invoice is None:
        invoice = InvoiceModel(
            id=str(uuid4()),
            order_id=order.id,
            number=f"WS-{order.id.replace('-', '')[:14].upper()}",
            subtotal=order.subtotal,
            taxes=order.taxes,
            total=order.total_amount,
            currency=order.currency,
        )
        session.add(invoice)
        await session.commit()
    return {"number": invoice.number}, invoice.number


async def _compensate(
    session: AsyncSession,
    saga: SagaInstanceModel,
    order: OrderModel,
    client: httpx.AsyncClient,
) -> None:
    saga.status = "COMPENSATING"
    order.status = "PENDING"
    await session.commit()

    payment_result = await session.execute(
        select(PaymentModel).where(PaymentModel.saga_id == saga.id).with_for_update()
    )
    payment = payment_result.scalar_one_or_none()
    if payment is not None and payment.status == "CAPTURED":
        async def refund() -> tuple[dict[str, str], str | None]:
            payment.status = "REFUNDED"
            await session.commit()
            return {"status": "REFUNDED"}, payment.provider_ref

        await _run_step(
            session,
            saga,
            "PROCESS_PAYMENT",
            refund,
            action="COMPENSATE",
            retry_forever=True,
        )

    for step, service, base_url in reversed(RESERVATION_SERVICES):
        async def cancel(base_url: str = base_url) -> tuple[dict[str, Any], str | None]:
            response = await client.post(
                f"{base_url}/reservations/{saga.id}/cancel",
                headers=_internal_headers(),
            )
            return _response_data(response), None

        await _run_step(
            session,
            saga,
            step,
            cancel,
            action="COMPENSATE",
            retry_forever=True,
        )

    saga.status = "COMPENSATED"
    saga.current_step = None
    order.status = "CANCELLED"
    await session.commit()


def _internal_headers() -> dict[str, str]:
    return {
        "X-Internal-Token": settings.internal_api_token.get_secret_value(),
    }


def _response_data(response: httpx.Response) -> dict[str, Any]:
    if response.is_success:
        try:
            data = response.json()
        except ValueError as error:
            raise RemoteStepError(
                "INVALID_UPSTREAM_RESPONSE",
                "Upstream service returned invalid JSON",
                transient=False,
            ) from error
        if not isinstance(data, dict):
            raise RemoteStepError(
                "INVALID_UPSTREAM_RESPONSE",
                "Upstream service returned an invalid response shape",
                transient=False,
            )
        return data

    try:
        detail = response.json()
    except ValueError:
        detail = response.text
    error_data = detail.get("error") if isinstance(detail, dict) else None
    if isinstance(error_data, dict):
        code = str(error_data.get("code", "UPSTREAM_ERROR"))
        message = str(error_data.get("message", "Upstream service returned an error"))
    else:
        message = str(detail)
        code = "UPSTREAM_ERROR"
    if response.status_code < 500:
        if isinstance(detail, dict):
            message = str(detail.get("detail", message))
        raise RemoteStepError(code, message, transient=False)
    raise RemoteStepError(code, message, transient=True)


async def _retry_delay(attempt: int, *, retry_forever: bool) -> None:
    delay = settings.saga_retry_backoff_seconds * (2 ** (attempt - 1))
    if retry_forever:
        delay = min(delay, settings.saga_compensation_max_backoff_seconds)
    await asyncio.sleep(delay)
