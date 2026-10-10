"""Create hotel offers and reservations."""

from alembic import op
import sqlalchemy as sa


revision = "hotel_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "room_offers",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("hotel_name", sa.String(150), nullable=False),
        sa.Column("city_code", sa.CHAR(3), nullable=False),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("stars", sa.SmallInteger(), nullable=False),
        sa.Column("rating", sa.Numeric(3, 1), nullable=True),
        sa.Column("room_type", sa.String(50), nullable=False),
        sa.Column("max_guests", sa.SmallInteger(), nullable=False),
        sa.Column("check_in", sa.Date(), nullable=False),
        sa.Column("check_out", sa.Date(), nullable=False),
        sa.Column(
            "nights",
            sa.SmallInteger(),
            sa.Computed("(check_out - check_in)::smallint", persisted=True),
            nullable=False,
        ),
        sa.Column("price_per_night", sa.Numeric(12, 2), nullable=False),
        sa.Column("price_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("rooms_total", sa.Integer(), nullable=False),
        sa.Column("rooms_available", sa.Integer(), nullable=False),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("stars BETWEEN 1 AND 5", name="ck_room_offers_valid_stars"),
        sa.CheckConstraint("rating IS NULL OR rating BETWEEN 0 AND 10", name="ck_room_offers_valid_rating"),
        sa.CheckConstraint("max_guests > 0", name="ck_room_offers_positive_max_guests"),
        sa.CheckConstraint("check_out > check_in", name="ck_room_offers_valid_dates"),
        sa.CheckConstraint("price_per_night > 0", name="ck_room_offers_positive_price_per_night"),
        sa.CheckConstraint("price_total > 0", name="ck_room_offers_positive_price_total"),
        sa.CheckConstraint("rooms_total > 0", name="ck_room_offers_positive_rooms_total"),
        sa.CheckConstraint(
            "rooms_available >= 0 AND rooms_available <= rooms_total",
            name="ck_room_offers_valid_inventory",
        ),
        sa.CheckConstraint(
            "room_type IN ('SINGLE', 'DOUBLE', 'TWIN', 'SUITE', 'FAMILY')",
            name="ck_room_offers_valid_room_type",
        ),
        sa.UniqueConstraint("source", "external_id", name="uq_room_offers_source_external_id"),
        schema="hotels",
    )
    op.execute("GRANT SELECT ON hotels.room_offers TO hasura_ro")
    op.execute("GRANT SELECT ON hotels.room_offers TO ingest")
    op.execute("GRANT INSERT ON hotels.room_offers TO ingest")
    op.execute(
        "GRANT UPDATE (hotel_name, city_code, address, stars, rating, room_type, "
        "max_guests, check_in, check_out, price_per_night, price_total, currency, "
        "rooms_total, scraped_at, updated_at) ON hotels.room_offers TO ingest"
    )
    op.create_index(
        "ix_room_offers_city_dates",
        "room_offers",
        ["city_code", "check_in", "check_out"],
        schema="hotels",
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
            ["hotels.room_offers.id"],
            name="fk_reservations_offer_id_room_offers",
        ),
        schema="hotels",
    )


def downgrade() -> None:
    op.drop_table("reservations", schema="hotels")
    op.drop_index("ix_room_offers_city_dates", table_name="room_offers", schema="hotels")
    op.drop_table("room_offers", schema="hotels")
