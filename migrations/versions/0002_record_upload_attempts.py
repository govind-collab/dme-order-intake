"""Record upload attempts.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-10 16:09:35.530644
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the upload_attempts table that the daily upload limits count."""
    op.create_table(
        "upload_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_upload_attempts_created_at", "upload_attempts", ["created_at"])
    op.create_index("ix_upload_attempts_user_id", "upload_attempts", ["user_id"])


def downgrade() -> None:
    """Drop the upload_attempts table."""
    op.drop_index("ix_upload_attempts_user_id", table_name="upload_attempts")
    op.drop_index("ix_upload_attempts_created_at", table_name="upload_attempts")
    op.drop_table("upload_attempts")
