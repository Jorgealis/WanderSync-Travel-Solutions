"""Modelos del servicio de vuelos (docs/contratos/modelo-datos.md, esquema `flights`).

Todo modelo debe heredar de `Base` y estar importado aquí para que Alembic lo detecte.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from wandersync_common.reservations import ReservationMixin

from app.db import Base


class FlightOffer(Base):
    """Catálogo: lo llena la ingesta (Google Flights). El inventario solo lo toca este servicio."""

    __tablename__ = "flight_offers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    source: Mapped[str] = mapped_column(String(50))
    external_id: Mapped[str] = mapped_column(String(100))
    airline: Mapped[str] = mapped_column(String(100))
    operated_by: Mapped[str | None] = mapped_column(String(100))
    flight_number: Mapped[str | None] = mapped_column(String(20))
    origin: Mapped[str] = mapped_column(String(3))
    destination: Mapped[str] = mapped_column(String(3))
    departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    stops: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    cabin_class: Mapped[str] = mapped_column(String(20))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), server_default="USD")
    price_original: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency_original: Mapped[str] = mapped_column(String(3))
    seats_total: Mapped[int] = mapped_column(Integer)
    seats_available: Mapped[int] = mapped_column(Integer)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("source", "external_id"),
        Index("ix_flight_offers_search", "origin", "destination", "departure_at"),
        CheckConstraint("arrival_at > departure_at", name="arrival_after_departure"),
        CheckConstraint("stops >= 0", name="stops_non_negative"),
        CheckConstraint("cabin_class IN ('ECONOMY', 'PREMIUM_ECONOMY', 'BUSINESS', 'FIRST')", name="cabin_class_valid"),
        CheckConstraint("price > 0 AND price_original > 0", name="price_positive"),
        CheckConstraint("seats_total > 0", name="seats_total_positive"),
        CheckConstraint("seats_available >= 0 AND seats_available <= seats_total", name="seats_available_range"),
    )


class Reservation(ReservationMixin, Base):
    __tablename__ = "reservations"

    offer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("flights.flight_offers.id"))


__all__ = ["Base", "FlightOffer", "Reservation"]
