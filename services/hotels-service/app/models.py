"""Modelos del servicio de hoteles (docs/contratos/modelo-datos.md, esquema `hotels`).

Todo modelo debe heredar de `Base` y estar importado aquí para que Alembic lo detecte.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Computed, Date, DateTime, ForeignKey, Index, Integer, Numeric, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from wandersync_common.reservations import ReservationMixin

from app.db import Base


class RoomOffer(Base):
    """Catálogo: lo llena la ingesta (Hotelbeds). El inventario solo lo toca este servicio."""

    __tablename__ = "room_offers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    source: Mapped[str] = mapped_column(String(50))
    external_id: Mapped[str] = mapped_column(String(100))
    hotel_code: Mapped[str] = mapped_column(String(20))
    hotel_name: Mapped[str] = mapped_column(String(150))
    city_code: Mapped[str] = mapped_column(String(3))
    zone_name: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(255))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    stars: Mapped[int | None] = mapped_column(SmallInteger)
    category_name: Mapped[str | None] = mapped_column(String(50))
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    room_code: Mapped[str] = mapped_column(String(30))
    room_name: Mapped[str] = mapped_column(String(150))
    room_type: Mapped[str] = mapped_column(String(20))
    board_code: Mapped[str] = mapped_column(String(10))
    board_name: Mapped[str] = mapped_column(String(50))
    max_guests: Mapped[int] = mapped_column(SmallInteger)
    check_in: Mapped[date] = mapped_column(Date)
    check_out: Mapped[date] = mapped_column(Date)
    nights: Mapped[int] = mapped_column(SmallInteger, Computed("check_out - check_in", persisted=True))
    price_per_night: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    price_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), server_default="USD")
    price_original: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency_original: Mapped[str] = mapped_column(String(3))
    rooms_total: Mapped[int] = mapped_column(Integer)
    rooms_available: Mapped[int] = mapped_column(Integer)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("source", "external_id"),
        Index("ix_room_offers_search", "city_code", "check_in", "check_out"),
        Index("ix_room_offers_hotel_code", "hotel_code"),
        CheckConstraint("check_out > check_in", name="checkout_after_checkin"),
        CheckConstraint("stars IS NULL OR stars BETWEEN 1 AND 5", name="stars_range"),
        CheckConstraint("rating IS NULL OR rating BETWEEN 0 AND 10", name="rating_range"),
        CheckConstraint("room_type IN ('SINGLE', 'DOUBLE', 'TWIN', 'SUITE', 'FAMILY', 'OTHER')", name="room_type_valid"),
        CheckConstraint("max_guests > 0", name="max_guests_positive"),
        CheckConstraint("price_per_night > 0 AND price_total > 0 AND price_original > 0", name="price_positive"),
        CheckConstraint("rooms_total > 0", name="rooms_total_positive"),
        CheckConstraint("rooms_available >= 0 AND rooms_available <= rooms_total", name="rooms_available_range"),
    )


class Reservation(ReservationMixin, Base):
    __tablename__ = "reservations"

    offer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hotels.room_offers.id"))


__all__ = ["Base", "Reservation", "RoomOffer"]
