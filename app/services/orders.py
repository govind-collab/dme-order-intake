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
    if all(getattr(order, field) is not None for field in ORDER_FIELDS):
        return OrderStatus.COMPLETE
    return OrderStatus.NEEDS_REVIEW


def save_new_order(db: Session, order: Order) -> Order:
    order.status = order_status(order)
    db.add(order)
    db.commit()
    return order


def create_order(db: Session, owner_id: uuid.UUID, values: OrderInput) -> Order:
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
    query = select(func.count()).where(
        Order.owner_id == owner_id,
        Order.source == OrderSource.UPLOAD,
        Order.created_at >= since,
    )
    return db.scalar(query) or 0


def list_orders(
    db: Session, owner_id: uuid.UUID, status: OrderStatus | None, limit: int, offset: int
) -> list[Order]:
    query = select(Order).where(Order.owner_id == owner_id)
    if status is not None:
        query = query.where(Order.status == status)
    query = query.order_by(Order.created_at.desc(), Order.id).limit(limit).offset(offset)
    return list(db.scalars(query))


def get_owned_order(db: Session, owner_id: uuid.UUID, order_id: uuid.UUID) -> Order | None:
    return db.scalar(select(Order).where(Order.id == order_id, Order.owner_id == owner_id))


def update_order(db: Session, order: Order, changes: OrderInput) -> Order:
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
    db.delete(order)
    db.commit()
