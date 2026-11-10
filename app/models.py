import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class OrderStatus(StrEnum):
    COMPLETE = "complete"
    NEEDS_REVIEW = "needs_review"


class OrderSource(StrEnum):
    MANUAL = "manual"
    UPLOAD = "upload"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Order(Base):
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
