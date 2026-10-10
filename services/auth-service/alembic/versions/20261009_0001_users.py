"""Create the auth users table."""

from alembic import op
import sqlalchemy as sa


revision = "auth_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="auth",
    )
    op.create_index("ix_users_email", "users", ["email"], schema="auth", unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users", schema="auth")
    op.drop_table("users", schema="auth")
