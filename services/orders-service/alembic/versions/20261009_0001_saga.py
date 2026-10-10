"""Create orders, saga, payment, and invoice tables."""

from alembic import op
import sqlalchemy as sa


revision = "orders_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("flight_offer_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("hotel_offer_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("car_offer_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("passengers", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("rooms", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=True),
        sa.Column("taxes", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("passengers BETWEEN 1 AND 9", name="ck_orders_passengers_range"),
        sa.CheckConstraint("rooms BETWEEN 1 AND 5", name="ck_orders_rooms_range"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'FAILED')",
            name="ck_orders_valid_status",
        ),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_orders_user_id_idempotency_key"),
        schema="orders",
    )
    op.create_index(
        "ix_orders_user_created_at",
        "orders",
        ["user_id", "created_at"],
        schema="orders",
    )
    op.create_table(
        "saga_instances",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="STARTED"),
        sa.Column("current_step", sa.String(30), nullable=True),
        sa.Column("simulate_failure_at", sa.String(20), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("version >= 0", name="ck_saga_instances_version_nonnegative"),
        sa.CheckConstraint(
            "status IN ('STARTED', 'COMPENSATING', 'COMPLETED', 'COMPENSATED', 'FAILED')",
            name="ck_saga_instances_valid_status",
        ),
        sa.UniqueConstraint("order_id", name="uq_saga_instances_order_id"),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.orders.id"],
            name="fk_saga_instances_order_id_orders",
        ),
        schema="orders",
    )
    op.create_index(
        "ix_saga_instances_pending",
        "saga_instances",
        ["status"],
        schema="orders",
        postgresql_where=sa.text("status IN ('STARTED', 'COMPENSATING')"),
    )
    op.create_table(
        "saga_steps",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("saga_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("step", sa.String(30), nullable=False),
        sa.Column("action", sa.String(12), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("attempt", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("external_ref", sa.String(100), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempt > 0", name="ck_saga_steps_attempt_positive"),
        sa.CheckConstraint("action IN ('EXECUTE', 'COMPENSATE')", name="ck_saga_steps_valid_action"),
        sa.CheckConstraint("status IN ('RUNNING', 'SUCCEEDED', 'FAILED')", name="ck_saga_steps_valid_status"),
        sa.ForeignKeyConstraint(
            ["saga_id"], ["orders.saga_instances.id"],
            name="fk_saga_steps_saga_id_saga_instances",
        ),
        schema="orders",
    )
    op.create_index("ix_saga_steps_saga_started", "saga_steps", ["saga_id", "started_at"], schema="orders")
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("saga_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("provider_ref", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("saga_id", name="uq_payments_saga_id"),
        sa.CheckConstraint(
            "status IN ('CAPTURED', 'REFUNDED', 'FAILED')",
            name="ck_payments_valid_status",
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.orders.id"], name="fk_payments_order_id_orders"),
        schema="orders",
    )
    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("number", sa.String(20), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("taxes", sa.Numeric(12, 2), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("order_id", name="uq_invoices_order_id"),
        sa.UniqueConstraint("number", name="uq_invoices_number"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.orders.id"], name="fk_invoices_order_id_orders"),
        schema="orders",
    )


def downgrade() -> None:
    op.drop_table("invoices", schema="orders")
    op.drop_table("payments", schema="orders")
    op.drop_index("ix_saga_steps_saga_started", table_name="saga_steps", schema="orders")
    op.drop_table("saga_steps", schema="orders")
    op.drop_index("ix_saga_instances_pending", table_name="saga_instances", schema="orders")
    op.drop_table("saga_instances", schema="orders")
    op.drop_index("ix_orders_user_created_at", table_name="orders", schema="orders")
    op.drop_table("orders", schema="orders")
