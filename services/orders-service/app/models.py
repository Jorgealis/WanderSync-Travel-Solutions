from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    CHAR,
    text,
)
from sqlalchemy.sql import func

from .db import Base


class OrderModel(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_orders_user_id_idempotency_key"),
        CheckConstraint("passengers BETWEEN 1 AND 9", name="passengers_range"),
        CheckConstraint("rooms BETWEEN 1 AND 5", name="rooms_range"),
        CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'FAILED')",
            name="valid_status",
        ),
        Index("ix_orders_user_created_at", "user_id", "created_at"),
    )

    id = Column(Uuid(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(Uuid(as_uuid=False), nullable=False)
    idempotency_key = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    flight_offer_id = Column(Uuid(as_uuid=False), nullable=False)
    hotel_offer_id = Column(Uuid(as_uuid=False), nullable=False)
    car_offer_id = Column(Uuid(as_uuid=False), nullable=False)
    passengers = Column(SmallInteger, nullable=False, default=1)
    rooms = Column(SmallInteger, nullable=False, default=1)
    subtotal = Column(Numeric(12, 2), nullable=True)
    taxes = Column(Numeric(12, 2), nullable=True)
    total_amount = Column(Numeric(12, 2), nullable=True)
    currency = Column(CHAR(3), nullable=False, default="USD")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class SagaInstanceModel(Base):
    __tablename__ = "saga_instances"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_saga_instances_order_id"),
        CheckConstraint("version >= 0", name="version_nonnegative"),
        CheckConstraint(
            "status IN ('STARTED', 'COMPENSATING', 'COMPLETED', 'COMPENSATED', 'FAILED')",
            name="valid_status",
        ),
        Index(
            "ix_saga_instances_pending",
            "status",
            postgresql_where=text("status IN ('STARTED', 'COMPENSATING')"),
        ),
    )

    id = Column(Uuid(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    order_id = Column(Uuid(as_uuid=False), ForeignKey("orders.orders.id"), nullable=False)
    status = Column(String(20), nullable=False, default="STARTED")
    current_step = Column(String(30), nullable=True)
    simulate_failure_at = Column(String(20), nullable=True)
    failure_reason = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __mapper_args__ = {"version_id_col": version}


class SagaStepModel(Base):
    __tablename__ = "saga_steps"
    __table_args__ = (
        CheckConstraint("attempt > 0", name="attempt_positive"),
        CheckConstraint(
            "action IN ('EXECUTE', 'COMPENSATE')",
            name="valid_action",
        ),
        CheckConstraint(
            "status IN ('RUNNING', 'SUCCEEDED', 'FAILED')",
            name="valid_status",
        ),
        Index("ix_saga_steps_saga_started", "saga_id", "started_at"),
    )

    id = Column(Uuid(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    saga_id = Column(Uuid(as_uuid=False), ForeignKey("orders.saga_instances.id"), nullable=False)
    step = Column(String(30), nullable=False)
    action = Column(String(12), nullable=False)
    status = Column(String(12), nullable=False)
    attempt = Column(SmallInteger, nullable=False, default=1)
    external_ref = Column(String(100), nullable=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)


class PaymentModel(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("saga_id", name="uq_payments_saga_id"),
        CheckConstraint("status IN ('CAPTURED', 'REFUNDED', 'FAILED')", name="valid_status"),
    )

    id = Column(Uuid(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    order_id = Column(Uuid(as_uuid=False), ForeignKey("orders.orders.id"), nullable=False)
    saga_id = Column(Uuid(as_uuid=False), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(CHAR(3), nullable=False)
    status = Column(String(12), nullable=False)
    provider_ref = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class InvoiceModel(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_invoices_order_id"),
        UniqueConstraint("number", name="uq_invoices_number"),
    )

    id = Column(Uuid(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    order_id = Column(Uuid(as_uuid=False), ForeignKey("orders.orders.id"), nullable=False)
    number = Column(String(20), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)
    taxes = Column(Numeric(12, 2), nullable=False)
    total = Column(Numeric(12, 2), nullable=False)
    currency = Column(CHAR(3), nullable=False)
    issued_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
