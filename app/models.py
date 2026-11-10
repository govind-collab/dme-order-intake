"""Database tables and the status values stored in them.

Owns the User and Order tables and the enums for order status, order source and field-report status.
Column types stay portable between SQLite and Postgres.
"""

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Return the current time in UTC, for timestamp defaults."""
    return datetime.now(UTC)


class OrderStatus(StrEnum):
    """complete when all five fields passed their checks, needs_review otherwise."""

    COMPLETE = "complete"
    NEEDS_REVIEW = "needs_review"


class OrderSource(StrEnum):
    """How an order was created: typed in by hand or read from an uploaded PDF."""

    MANUAL = "manual"
    UPLOAD = "upload"


class FieldStatus(StrEnum):
    """Outcome for one extracted field.

    ok passed every check, missing was not found or not readable, invalid was read but failed a
    check, and conflict means the document gives different values.
    """

    OK = "ok"
    MISSING = "missing"
    INVALID = "invalid"
    CONFLICT = "conflict"


class Base(DeclarativeBase):
    """Declarative base for all tables."""

    pass


class User(Base):
    """An account; each order belongs to exactly one user."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Order(Base):
    """One DME order with its five fields, all nullable.

    A field holds a value only when it passed every check. `field_report` keeps, per field, what
    the document said and why a value was refused; it is null for orders created by hand.
    """

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(10))
    patient_first_name: Mapped[str | None] = mapped_column(String(100))
    patient_last_name: Mapped[str | None] = mapped_column(String(100))
    patient_dob: Mapped[date | None]
    provider_name: Mapped[str | None] = mapped_column(String(200))
    provider_npi: Mapped[str | None] = mapped_column(String(10))
    field_report: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    document_sha256: Mapped[str | None] = mapped_column(String(64))
    document_pages: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class UploadAttempt(Base):
    """One upload that passed the file checks and is about to be read by the model.

    Written before the model call and kept when the upload fails or its order is deleted, so the
    daily limits count every paid call. Only an attempt refused for being over a limit is removed.
    """

    __tablename__ = "upload_attempts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
