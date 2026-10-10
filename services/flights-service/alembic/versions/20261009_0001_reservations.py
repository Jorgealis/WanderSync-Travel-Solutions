"""Create flight offers and reservations."""

from alembic import op
import sqlalchemy as sa


revision = "flight_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "flight_offers",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("airline", sa.String(100), nullable=False),
        sa.Column("flight_number", sa.String(20), nullable=False),
        sa.Column("origin", sa.CHAR(3), nullable=False),
        sa.Column("destination", sa.CHAR(3), nullable=False),
        sa.Column("departure_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrival_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cabin_class", sa.String(20), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("seats_total", sa.Integer(), nullable=False),
        sa.Column("seats_available", sa.Integer(), nullable=False),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("arrival_at > departure_at", name="ck_flight_offers_valid_times"),
        sa.CheckConstraint("price > 0", name="ck_flight_offers_positive_price"),
        sa.CheckConstraint("seats_total > 0", name="ck_flight_offers_positive_seats_total"),
        sa.CheckConstraint(
            "seats_available >= 0 AND seats_available <= seats_total",
            name="ck_flight_offers_valid_inventory",
        ),
        sa.CheckConstraint(
            "cabin_class IN ('ECONOMY', 'PREMIUM_ECONOMY', 'BUSINESS', 'FIRST')",
            name="ck_flight_offers_valid_cabin_class",
        ),
        sa.UniqueConstraint("source", "external_id", name="uq_flight_offers_source_external_id"),
        schema="flights",
    )
    op.execute("GRANT SELECT ON flights.flight_offers TO hasura_ro")
    op.execute("GRANT SELECT ON flights.flight_offers TO ingest")
    op.execute("GRANT INSERT ON flights.flight_offers TO ingest")
    op.execute(
        "GRANT UPDATE (airline, flight_number, origin, destination, departure_at, "
        "arrival_at, cabin_class, price, currency, seats_total, scraped_at, updated_at) "
        "ON flights.flight_offers TO ingest"
    )
    op.create_index(
        "ix_flight_offers_route_departure",
        "flight_offers",
        ["origin", "destination", "departure_at"],
        schema="flights",
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
            ["flights.flight_offers.id"],
            name="fk_reservations_offer_id_flight_offers",
        ),
        schema="flights",
    )


def downgrade() -> None:
    op.drop_table("reservations", schema="flights")
    op.drop_index("ix_flight_offers_route_departure", table_name="flight_offers", schema="flights")
    op.drop_table("flight_offers", schema="flights")
