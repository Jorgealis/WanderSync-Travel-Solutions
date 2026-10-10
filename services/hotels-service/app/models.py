import enum

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    Computed,
    func,
    text,
)

from .db import Base


class ReservationStatus(str, enum.Enum):
    RESERVED = "RESERVED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class RoomOfferModel(Base):
    __tablename__ = "room_offers"
    __table_args__ = (
        CheckConstraint("stars BETWEEN 1 AND 5", name="valid_stars"),
        CheckConstraint("rating IS NULL OR rating BETWEEN 0 AND 10", name="valid_rating"),
        CheckConstraint("max_guests > 0", name="positive_max_guests"),
        CheckConstraint("check_out > check_in", name="valid_dates"),
        CheckConstraint("price_per_night > 0", name="positive_price_per_night"),
        CheckConstraint("price_total > 0", name="positive_price_total"),
        CheckConstraint("rooms_total > 0", name="positive_rooms_total"),
        CheckConstraint(
            "rooms_available >= 0 AND rooms_available <= rooms_total",
            name="valid_inventory",
        ),
        CheckConstraint(
            "room_type IN ('SINGLE', 'DOUBLE', 'TWIN', 'SUITE', 'FAMILY')",
            name="valid_room_type",
        ),
        UniqueConstraint("source", "external_id", name="uq_room_offers_source_external_id"),
    )

    id = Column(
        Uuid(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source = Column(String(50), nullable=False)
    external_id = Column(String(100), nullable=False)
    hotel_name = Column(String(150), nullable=False)
    city_code = Column(CHAR(3), nullable=False)
    address = Column(String(255), nullable=True)
    stars = Column(SmallInteger, nullable=False)
    rating = Column(Numeric(3, 1), nullable=True)
    room_type = Column(String(50), nullable=False)
    max_guests = Column(SmallInteger, nullable=False)
    check_in = Column(Date, nullable=False)
    check_out = Column(Date, nullable=False)
    nights = Column(
        SmallInteger,
        Computed("(check_out - check_in)::smallint", persisted=True),
        nullable=False,
    )
    price_per_night = Column(Numeric(12, 2), nullable=False)
    price_total = Column(Numeric(12, 2), nullable=False)
    currency = Column(CHAR(3), nullable=False, server_default=text("'USD'"))
    rooms_total = Column(Integer, nullable=False)
    rooms_available = Column(Integer, nullable=False)
    scraped_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class RoomReservationModel(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint(
            "status = 'CANCELLED' OR (offer_id IS NOT NULL AND quantity > 0)",
            name="valid_reservation_or_tombstone",
        ),
        CheckConstraint(
            "status IN ('RESERVED', 'CONFIRMED', 'CANCELLED')",
            name="valid_status",
        ),
        CheckConstraint("quantity >= 0", name="nonnegative_quantity"),
        UniqueConstraint("saga_id", name="uq_reservations_saga_id"),
    )

    id = Column(
        Uuid(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    saga_id = Column(Uuid(as_uuid=False), nullable=False)
    order_id = Column(Uuid(as_uuid=False), nullable=True)
    offer_id = Column(
        Uuid(as_uuid=False),
        ForeignKey("hotels.room_offers.id", name="fk_reservations_offer_id_room_offers"),
        nullable=True,
    )
    quantity = Column(Integer, nullable=False, server_default=text("0"))
    unit_price = Column(Numeric(12, 2), nullable=True)
    total_price = Column(Numeric(12, 2), nullable=True)
    currency = Column(CHAR(3), nullable=False, server_default=text("'USD'"))
    status = Column(String(20), nullable=False, server_default=text("'RESERVED'"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
