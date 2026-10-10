import enum

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)

from .db import Base


class ReservationStatus(str, enum.Enum):
    RESERVED = "RESERVED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class FlightOfferModel(Base):
    __tablename__ = "flight_offers"
    __table_args__ = (
        CheckConstraint("arrival_at > departure_at", name="valid_times"),
        CheckConstraint("price > 0", name="positive_price"),
        CheckConstraint("seats_total > 0", name="positive_seats_total"),
        CheckConstraint(
            "seats_available >= 0 AND seats_available <= seats_total",
            name="valid_inventory",
        ),
        CheckConstraint(
            "cabin_class IN ('ECONOMY', 'PREMIUM_ECONOMY', 'BUSINESS', 'FIRST')",
            name="valid_cabin_class",
        ),
        UniqueConstraint("source", "external_id", name="uq_flight_offers_source_external_id"),
    )

    id = Column(
        Uuid(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source = Column(String(50), nullable=False)
    external_id = Column(String(100), nullable=False)
    airline = Column(String(100), nullable=False)
    flight_number = Column(String(20), nullable=False)
    origin = Column(CHAR(3), nullable=False)
    destination = Column(CHAR(3), nullable=False)
    departure_at = Column(DateTime(timezone=True), nullable=False)
    arrival_at = Column(DateTime(timezone=True), nullable=False)
    cabin_class = Column(String(20), nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    currency = Column(CHAR(3), nullable=False, server_default=text("'USD'"))
    seats_total = Column(Integer, nullable=False)
    seats_available = Column(Integer, nullable=False)
    scraped_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class FlightReservationModel(Base):
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
        ForeignKey("flights.flight_offers.id", name="fk_reservations_offer_id_flight_offers"),
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
