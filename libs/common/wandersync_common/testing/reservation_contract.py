"""Batería de pruebas del contrato de reservas (docs/contratos/api-interna.md §2).

La comparten flights, hotels y cars: cada servicio la importa en tests/test_reservations.py
y define en su conftest.py estos fixtures:

    client        httpx.AsyncClient contra la app (con X-Internal-Token)
    make_offer    async (available: int, price: Decimal) -> UUID de una oferta de prueba
    inventory     async (offer_id) -> unidades disponibles actuales
    settings      configuración del servicio (para activar/desactivar la inyección de fallos)

Se ejecutan contra la base de datos REAL del servicio; los fixtures limpian lo que crean.
"""

import asyncio
import uuid
from decimal import Decimal

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


def body(offer_id, quantity=1, saga_id=None):
    return {
        "saga_id": str(saga_id or uuid.uuid4()),
        "order_id": str(uuid.uuid4()),
        "offer_id": str(offer_id),
        "quantity": quantity,
    }


async def test_reserve_decrements_inventory_and_prices_from_offer(client, make_offer, inventory):
    offer = await make_offer(available=5, price=Decimal("120.50"))
    response = await client.post("/reservations", json=body(offer, quantity=2))
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "RESERVED"
    assert Decimal(data["unit_price"]) == Decimal("120.50")
    assert Decimal(data["total_price"]) == Decimal("241.00")
    assert data["currency"] == "USD"
    assert await inventory(offer) == 3


async def test_replay_is_idempotent(client, make_offer, inventory):
    offer = await make_offer(available=5)
    request = body(offer, quantity=2)
    first = await client.post("/reservations", json=request)
    second = await client.post("/reservations", json=request)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]
    assert await inventory(offer) == 3  # descontado una sola vez


async def test_insufficient_availability(client, make_offer, inventory):
    offer = await make_offer(available=1)
    response = await client.post("/reservations", json=body(offer, quantity=2))
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "INSUFFICIENT_AVAILABILITY"
    assert error["details"] == {"available": 1, "requested": 2}
    assert await inventory(offer) == 1


async def test_unknown_offer(client):
    response = await client.post("/reservations", json=body(uuid.uuid4()))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "OFFER_NOT_FOUND"


async def test_simulated_failure_when_enabled(client, make_offer, inventory, settings, monkeypatch):
    monkeypatch.setattr(settings, "enable_fault_injection", True)
    offer = await make_offer(available=5)
    response = await client.post("/reservations", json=body(offer), headers={"X-Simulate-Failure": "true"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SIMULATED_FAILURE"
    assert await inventory(offer) == 5  # el fallo simulado no toca el inventario


async def test_simulated_failure_ignored_when_disabled(client, make_offer, settings, monkeypatch):
    monkeypatch.setattr(settings, "enable_fault_injection", False)
    offer = await make_offer(available=5)
    response = await client.post("/reservations", json=body(offer), headers={"X-Simulate-Failure": "true"})
    assert response.status_code == 201


async def test_cancel_restores_inventory_and_is_idempotent(client, make_offer, inventory):
    offer = await make_offer(available=4)
    request = body(offer, quantity=3)
    await client.post("/reservations", json=request)
    assert await inventory(offer) == 1
    first = await client.post(f"/reservations/{request['saga_id']}/cancel")
    second = await client.post(f"/reservations/{request['saga_id']}/cancel")
    assert (first.status_code, second.status_code) == (200, 200)
    assert second.json()["status"] == "CANCELLED"
    assert await inventory(offer) == 4  # restaurado una sola vez


async def test_cancel_before_reserve_leaves_tombstone(client, make_offer, inventory):
    offer = await make_offer(available=5)
    request = body(offer)
    tombstone = await client.post(f"/reservations/{request['saga_id']}/cancel")
    assert tombstone.status_code == 200
    assert tombstone.json()["status"] == "CANCELLED" and tombstone.json()["offer_id"] is None
    late = await client.post("/reservations", json=request)  # la reserva "llega tarde"
    assert late.status_code == 409
    assert late.json()["error"]["code"] == "RESERVATION_CANCELLED"
    assert await inventory(offer) == 5


async def test_confirm_lifecycle(client, make_offer):
    offer = await make_offer(available=5)
    request = body(offer)
    saga = request["saga_id"]
    assert (await client.post(f"/reservations/{saga}/confirm")).status_code == 404
    await client.post("/reservations", json=request)
    confirmed = await client.post(f"/reservations/{saga}/confirm")
    again = await client.post(f"/reservations/{saga}/confirm")
    assert (confirmed.status_code, again.status_code) == (200, 200)
    assert again.json()["status"] == "CONFIRMED"
    cancel = await client.post(f"/reservations/{saga}/cancel")
    assert cancel.status_code == 409
    assert cancel.json()["error"]["code"] == "RESERVATION_ALREADY_CONFIRMED"
    fetched = await client.get(f"/reservations/{saga}")
    assert fetched.status_code == 200 and fetched.json()["status"] == "CONFIRMED"


async def test_confirm_cancelled_is_rejected(client, make_offer):
    offer = await make_offer(available=5)
    request = body(offer)
    await client.post("/reservations", json=request)
    await client.post(f"/reservations/{request['saga_id']}/cancel")
    response = await client.post(f"/reservations/{request['saga_id']}/confirm")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RESERVATION_CANCELLED"


async def test_no_overselling_under_concurrency(client, make_offer, inventory):
    offer = await make_offer(available=3)
    responses = await asyncio.gather(*(client.post("/reservations", json=body(offer)) for _ in range(8)))
    codes = sorted(r.status_code for r in responses)
    assert codes == [201] * 3 + [409] * 5
    assert await inventory(offer) == 0


async def test_concurrent_replays_reserve_once(client, make_offer, inventory):
    offer = await make_offer(available=5)
    request = body(offer, quantity=2)
    responses = await asyncio.gather(*(client.post("/reservations", json=request) for _ in range(5)))
    assert sorted(r.status_code for r in responses) == [200] * 4 + [201]
    assert len({r.json()["id"] for r in responses}) == 1
    assert await inventory(offer) == 3


async def test_requires_internal_token(client, make_offer):
    offer = await make_offer(available=5)
    response = await client.post("/reservations", json=body(offer), headers={"X-Internal-Token": "wrong"})
    assert response.status_code == 401


async def test_validation_error_format(client, make_offer):
    offer = await make_offer(available=5)
    response = await client.post("/reservations", json=body(offer, quantity=0))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
