"""Reading and writing orders.

Owns the order status rule, creating orders by hand or from an upload, the upload count behind the
quota, owner-scoped queries, and updates that keep the field report in step with the order.
"""

import hashlib
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import FieldStatus, Order, OrderSource, OrderStatus
from app.schemas import FieldReport, OrderInput

ORDER_FIELDS = tuple(OrderInput.model_fields)


def order_status(order: Order) -> OrderStatus:
    """Return complete when all five fields are set, otherwise needs_review."""
    if all(getattr(order, field) is not None for field in ORDER_FIELDS):
        return OrderStatus.COMPLETE
    return OrderStatus.NEEDS_REVIEW


def save_new_order(db: Session, order: Order) -> Order:
    """Set the status of a new order, save it and return it."""
    order.status = order_status(order)
    db.add(order)
    db.commit()
    return order


def create_order(db: Session, owner_id: uuid.UUID, values: OrderInput) -> Order:
    """Create and return an order from values typed in by hand."""
    order = Order(owner_id=owner_id, source=OrderSource.MANUAL, **values.model_dump())
    return save_new_order(db, order)


def create_uploaded_order(
    db: Session,
    owner_id: uuid.UUID,
    values: dict[str, Any],
    reports: dict[str, FieldReport],
    pdf: bytes,
    pages: int,
) -> Order:
    """Create and return an order from an upload's checked values and field reports.

    Keeps the PDF's SHA-256 and page count, never the PDF itself.
    """
    order = Order(
        owner_id=owner_id,
        source=OrderSource.UPLOAD,
        field_report={field: report.model_dump(mode="json") for field, report in reports.items()},
        document_sha256=hashlib.sha256(pdf).hexdigest(),
        document_pages=pages,
        **values,
    )
    return save_new_order(db, order)


def count_uploads_since(db: Session, owner_id: uuid.UUID, since: datetime) -> int:
    """Return how many orders the user has uploaded since `since`.

    Deleted orders no longer count, and uploads that were rejected never did.
    """
    query = select(func.count()).where(
        Order.owner_id == owner_id,
        Order.source == OrderSource.UPLOAD,
        Order.created_at >= since,
    )
    return db.scalar(query) or 0


def list_orders(
    db: Session, owner_id: uuid.UUID, status: OrderStatus | None, limit: int, offset: int
) -> list[Order]:
    """Return a page of the user's orders, newest first, optionally only those with one status."""
    query = select(Order).where(Order.owner_id == owner_id)
    if status is not None:
        query = query.where(Order.status == status)
    query = query.order_by(Order.created_at.desc(), Order.id).limit(limit).offset(offset)
    return list(db.scalars(query))


def get_owned_order(db: Session, owner_id: uuid.UUID, order_id: uuid.UUID) -> Order | None:
    """Return the order if it exists and belongs to the user, otherwise None."""
    return db.scalar(select(Order).where(Order.id == order_id, Order.owner_id == owner_id))


def update_order(db: Session, order: Order, changes: OrderInput) -> Order:
    """Apply the fields that were sent, recompute the status and return the order.

    On an uploaded order each changed field's report is marked as edited by hand (ok with "set
    by hand", or missing with "cleared by hand"), while its value as read, page and quote stay.
    """
    reports = dict(order.field_report or {})
    for field, value in changes.model_dump(exclude_unset=True).items():
        setattr(order, field, value)
        if field in reports:
            status, reason = (
                (FieldStatus.OK, "set by hand")
                if value is not None
                else (FieldStatus.MISSING, "cleared by hand")
            )
            reports[field] = {**reports[field], "status": status, "reason": reason}
    if order.field_report is not None:
        order.field_report = reports
    order.status = order_status(order)
    db.commit()
    return order


def delete_order(db: Session, order: Order) -> None:
    """Delete the order."""
    db.delete(order)
    db.commit()
