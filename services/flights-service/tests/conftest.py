"""Fixtures del contrato de reservas (wandersync_common.testing.reservation_contract).

Las pruebas usan la base de datos real del servicio: crean ofertas con source='pytest'
y al final borran esas ofertas y todas sus reservas (incluidos los tombstones).
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, or_, select

from app.config import settings as service_settings
from app.db import db
from app.main import app
from tests.offer_factory import INVENTORY_COLUMN, Offer, Reservation, build_offer

TEST_SOURCE = "pytest"


@pytest.fixture
def settings():
    return service_settings


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    token = service_settings.internal_api_token.get_secret_value()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers={"X-Internal-Token": token}) as c:
        yield c


@pytest_asyncio.fixture(loop_scope="session")
async def make_offer():
    created: list[uuid.UUID] = []
    started = datetime.now(timezone.utc)

    async def factory(available: int = 5, price: Decimal = Decimal("100.00")) -> uuid.UUID:
        async with db.sessionmaker() as session, session.begin():
            offer = build_offer(TEST_SOURCE, str(uuid.uuid4()), available, price)
            session.add(offer)
            await session.flush()
            created.append(offer.id)
            return offer.id

    yield factory

    async with db.sessionmaker() as session, session.begin():
        await session.execute(delete(Reservation).where(or_(
            Reservation.offer_id.in_(created),
            (Reservation.offer_id.is_(None)) & (Reservation.created_at >= started),  # tombstones de la prueba
        )))
        await session.execute(delete(Offer).where(Offer.id.in_(created)))


@pytest_asyncio.fixture(loop_scope="session")
async def inventory():
    async def current(offer_id: uuid.UUID) -> int:
        async with db.sessionmaker() as session:
            return await session.scalar(select(getattr(Offer, INVENTORY_COLUMN)).where(Offer.id == offer_id))

    return current
