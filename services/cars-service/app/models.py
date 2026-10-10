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


class CarOfferModel(Base):
    __tablename__ = "car_offers"
    __table_args__ = (
        CheckConstraint("dropoff_date > pickup_date", name="valid_dates"),
        CheckConstraint("seats > 0", name="positive_seats"),
        CheckConstraint("price_per_day > 0", name="positive_price_per_day"),
        CheckConstraint("price_total > 0", name="positive_price_total"),
        CheckConstraint("units_total > 0", name="positive_units_total"),
        CheckConstraint(
            "units_available >= 0 AND units_available <= units_total",
            name="valid_inventory",
        ),
        CheckConstraint(
            "category IN ('ECONOMY', 'COMPACT', 'SUV', 'VAN', 'LUXURY')",
            name="valid_category",
        ),
        CheckConstraint(
            "transmission IN ('MANUAL', 'AUTOMATIC')",
            name="valid_transmission",
        ),
        UniqueConstraint("source", "external_id", name="uq_car_offers_source_external_id"),
    )

    id = Column(
        Uuid(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source = Column(String(50), nullable=False)
    external_id = Column(String(100), nullable=False)
    company = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    category = Column(String(20), nullable=False)
    transmission = Column(String(10), nullable=False)
    seats = Column(SmallInteger, nullable=False)
    city_code = Column(CHAR(3), nullable=False)
    pickup_date = Column(Date, nullable=False)
    dropoff_date = Column(Date, nullable=False)
    days = Column(
        SmallInteger,
        Computed("(dropoff_date - pickup_date)::smallint", persisted=True),
        nullable=False,
    )
    price_per_day = Column(Numeric(12, 2), nullable=False)
    price_total = Column(Numeric(12, 2), nullable=False)
    currency = Column(CHAR(3), nullable=False, server_default=text("'USD'"))
    units_total = Column(Integer, nullable=False)
    units_available = Column(Integer, nullable=False)
    scraped_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CarReservationModel(Base):
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
        ForeignKey("cars.car_offers.id", name="fk_reservations_offer_id_car_offers"),
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
