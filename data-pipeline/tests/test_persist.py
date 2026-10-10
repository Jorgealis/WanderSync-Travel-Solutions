"""Integración de la persistencia (2.10) contra la BD REAL, con el usuario `ingest`.

Se omite si no hay credenciales; la ejecuta `python scripts/run_service_tests.py pipeline`,
que también pasa las credenciales del dueño del esquema (CLEANUP_*) solo para limpiar.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import ProgrammingError

from ingestion.persist import ingest_engine, upsert

pytestmark = pytest.mark.skipif(not os.environ.get("INGEST_DB_PASSWORD"), reason="requiere la BD del stack")
SOURCE = "pytest-ingest"


@pytest.fixture
def engine():
    return ingest_engine()


@pytest.fixture
def owner():
    url = URL.create(
        "postgresql+psycopg", username=os.environ["CLEANUP_DB_USER"], password=os.environ["CLEANUP_DB_PASSWORD"],
        host=os.environ.get("POSTGRES_HOST", "postgres"), database=os.environ.get("POSTGRES_DB", "wandersync"),
    )
    owner_engine = create_engine(url)
    yield owner_engine
    with owner_engine.begin() as conn:
        conn.execute(text("DELETE FROM flights.flight_offers WHERE source = :s"), {"s": SOURCE})


def flight_row(external_id: str, price: str, seats: int = 30) -> dict:
    departure = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=20)
    return {
        "source": SOURCE, "external_id": external_id, "airline": "Test Air", "operated_by": None,
        "flight_number": None, "origin": "BOG", "destination": "MDE", "departure_at": departure,
        "arrival_at": departure + timedelta(hours=1), "stops": 0, "cabin_class": "ECONOMY",
        "price": Decimal(price), "currency": "USD", "price_original": Decimal(price) * 3200,
        "currency_original": "COP", "seats_total": seats, "seats_available": seats,
        "scraped_at": datetime.now(timezone.utc),
    }


def test_insert_then_update_without_touching_inventory(engine, owner):
    ids = [str(uuid.uuid4()) for _ in range(3)]
    first = upsert(engine, "flights", [flight_row(i, "60.00") for i in ids], batch_size=2)
    assert (first.inserted, first.updated) == (3, 0)

    # La SAGA reservó 4 asientos de la primera oferta (lo simula el dueño del esquema).
    with owner.begin() as conn:
        conn.execute(text("UPDATE flights.flight_offers SET seats_available = 26 WHERE source = :s AND external_id = :e"),
                     {"s": SOURCE, "e": ids[0]})

    # Siguiente ingesta: precio nuevo y, por error, el inventario por defecto otra vez.
    second = upsert(engine, "flights", [flight_row(i, "55.00", seats=30) for i in ids] + [flight_row(str(uuid.uuid4()), "70.00")])
    assert (second.inserted, second.updated) == (1, 3)

    with owner.begin() as conn:
        price, available = conn.execute(
            text("SELECT price, seats_available FROM flights.flight_offers WHERE source = :s AND external_id = :e"),
            {"s": SOURCE, "e": ids[0]},
        ).one()
    assert price == Decimal("55.00")  # precio actualizado
    assert available == 26  # las reservas de la SAGA se conservan


def test_ingest_role_cannot_modify_inventory(engine, owner):
    external_id = str(uuid.uuid4())
    upsert(engine, "flights", [flight_row(external_id, "60.00")])
    with pytest.raises(ProgrammingError, match="permission denied"), engine.begin() as conn:
        conn.execute(text("UPDATE flights.flight_offers SET seats_available = 0 WHERE source = :s"), {"s": SOURCE})
