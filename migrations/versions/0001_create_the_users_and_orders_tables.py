"""Create the users and orders tables.

Revision ID: 0001
Revises:
Create Date: 2026-11-10 15:14:49.857435
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the tables exactly as create_all made them before migrations existed.

    Databases created that way are stamped with this revision instead of running it, so it
    must not differ from those tables.
    """
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.Column("patient_first_name", sa.String(length=100), nullable=True),
        sa.Column("patient_last_name", sa.String(length=100), nullable=True),
        sa.Column("patient_dob", sa.Date(), nullable=True),
        sa.Column("provider_name", sa.String(length=200), nullable=True),
        sa.Column("provider_npi", sa.String(length=10), nullable=True),
        sa.Column("field_report", sa.JSON(), nullable=True),
        sa.Column("document_sha256", sa.String(length=64), nullable=True),
        sa.Column("document_pages", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_owner_id", "orders", ["owner_id"])


def downgrade() -> None:
    """Drop both tables."""
    op.drop_index("ix_orders_owner_id", table_name="orders")
    op.drop_table("orders")
    op.drop_table("users")
