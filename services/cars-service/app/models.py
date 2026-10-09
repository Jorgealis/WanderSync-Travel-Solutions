"""Modelos del servicio de autos (docs/contratos/modelo-datos.md, esquema `cars`).

Todo modelo debe heredar de `Base` y estar importado aquí para que Alembic lo detecte.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Computed, Date, DateTime, ForeignKey, Index, Integer, Numeric, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from wandersync_common.reservations import ReservationMixin

from app.db import Base


class CarOffer(Base):
    """Catálogo: lo llena la ingesta (fuente simulada de autos). El inventario solo lo toca este servicio."""

    __tablename__ = "car_offers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    source: Mapped[str] = mapped_column(String(50))
    external_id: Mapped[str] = mapped_column(String(100))
    company: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(20))
    transmission: Mapped[str] = mapped_column(String(10))
    seats: Mapped[int] = mapped_column(SmallInteger)
    city_code: Mapped[str] = mapped_column(String(3))
    pickup_date: Mapped[date] = mapped_column(Date)
    dropoff_date: Mapped[date] = mapped_column(Date)
    days: Mapped[int] = mapped_column(SmallInteger, Computed("dropoff_date - pickup_date", persisted=True))
    price_per_day: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    price_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), server_default="USD")
    price_original: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency_original: Mapped[str] = mapped_column(String(3))
    units_total: Mapped[int] = mapped_column(Integer)
    units_available: Mapped[int] = mapped_column(Integer)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("source", "external_id"),
        Index("ix_car_offers_search", "city_code", "pickup_date", "dropoff_date"),
        CheckConstraint("dropoff_date > pickup_date", name="dropoff_after_pickup"),
        CheckConstraint("category IN ('ECONOMY', 'COMPACT', 'SUV', 'VAN', 'LUXURY')", name="category_valid"),
        CheckConstraint("transmission IN ('MANUAL', 'AUTOMATIC')", name="transmission_valid"),
        CheckConstraint("seats > 0", name="seats_positive"),
        CheckConstraint("price_per_day > 0 AND price_total > 0 AND price_original > 0", name="price_positive"),
        CheckConstraint("units_total > 0", name="units_total_positive"),
        CheckConstraint("units_available >= 0 AND units_available <= units_total", name="units_available_range"),
    )


class Reservation(ReservationMixin, Base):
    __tablename__ = "reservations"

    offer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cars.car_offers.id"))


__all__ = ["Base", "CarOffer", "Reservation"]
