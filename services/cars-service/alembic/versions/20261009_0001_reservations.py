"""Create car offers and reservations."""

from alembic import op
import sqlalchemy as sa


revision = "car_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "car_offers",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("company", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("transmission", sa.String(10), nullable=False),
        sa.Column("seats", sa.SmallInteger(), nullable=False),
        sa.Column("city_code", sa.CHAR(3), nullable=False),
        sa.Column("pickup_date", sa.Date(), nullable=False),
        sa.Column("dropoff_date", sa.Date(), nullable=False),
        sa.Column(
            "days",
            sa.SmallInteger(),
            sa.Computed("(dropoff_date - pickup_date)::smallint", persisted=True),
            nullable=False,
        ),
        sa.Column("price_per_day", sa.Numeric(12, 2), nullable=False),
        sa.Column("price_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("units_total", sa.Integer(), nullable=False),
        sa.Column("units_available", sa.Integer(), nullable=False),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("dropoff_date > pickup_date", name="ck_car_offers_valid_dates"),
        sa.CheckConstraint("seats > 0", name="ck_car_offers_positive_seats"),
        sa.CheckConstraint("price_per_day > 0", name="ck_car_offers_positive_price_per_day"),
        sa.CheckConstraint("price_total > 0", name="ck_car_offers_positive_price_total"),
        sa.CheckConstraint("units_total > 0", name="ck_car_offers_positive_units_total"),
        sa.CheckConstraint(
            "units_available >= 0 AND units_available <= units_total",
            name="ck_car_offers_valid_inventory",
        ),
        sa.CheckConstraint(
            "category IN ('ECONOMY', 'COMPACT', 'SUV', 'VAN', 'LUXURY')",
            name="ck_car_offers_valid_category",
        ),
        sa.CheckConstraint(
            "transmission IN ('MANUAL', 'AUTOMATIC')",
            name="ck_car_offers_valid_transmission",
        ),
        sa.UniqueConstraint("source", "external_id", name="uq_car_offers_source_external_id"),
        schema="cars",
    )
    op.execute("GRANT SELECT ON cars.car_offers TO hasura_ro")
    op.execute("GRANT SELECT ON cars.car_offers TO ingest")
    op.execute("GRANT INSERT ON cars.car_offers TO ingest")
    op.execute(
        "GRANT UPDATE (company, model, category, transmission, seats, city_code, "
        "pickup_date, dropoff_date, price_per_day, price_total, currency, units_total, "
        "scraped_at, updated_at) ON cars.car_offers TO ingest"
    )
    op.create_index(
        "ix_car_offers_city_dates",
        "car_offers",
        ["city_code", "pickup_date", "dropoff_date"],
        schema="cars",
    )
    op.create_table(
        "reservations",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("saga_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("order_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("offer_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'RESERVED'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status = 'CANCELLED' OR (offer_id IS NOT NULL AND quantity > 0)",
            name="ck_reservations_valid_reservation_or_tombstone",
        ),
        sa.CheckConstraint(
            "status IN ('RESERVED', 'CONFIRMED', 'CANCELLED')",
            name="ck_reservations_valid_status",
        ),
        sa.CheckConstraint("quantity >= 0", name="ck_reservations_nonnegative_quantity"),
        sa.UniqueConstraint("saga_id", name="uq_reservations_saga_id"),
        sa.ForeignKeyConstraint(
            ["offer_id"],
            ["cars.car_offers.id"],
            name="fk_reservations_offer_id_car_offers",
        ),
        schema="cars",
    )


def downgrade() -> None:
    op.drop_table("reservations", schema="cars")
    op.drop_index("ix_car_offers_city_dates", table_name="car_offers", schema="cars")
    op.drop_table("car_offers", schema="cars")
