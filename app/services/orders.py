import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, OrderSource, OrderStatus
from app.schemas import OrderInput

ORDER_FIELDS = tuple(OrderInput.model_fields)


def order_status(order: Order) -> OrderStatus:
    if all(getattr(order, field) is not None for field in ORDER_FIELDS):
        return OrderStatus.COMPLETE
    return OrderStatus.NEEDS_REVIEW


def create_order(db: Session, owner_id: uuid.UUID, values: OrderInput) -> Order:
    order = Order(owner_id=owner_id, source=OrderSource.MANUAL, **values.model_dump())
    order.status = order_status(order)
    db.add(order)
    db.commit()
    return order


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
    for field, value in changes.model_dump(exclude_unset=True).items():
        setattr(order, field, value)
    order.status = order_status(order)
    db.commit()
    return order


def delete_order(db: Session, order: Order) -> None:
    db.delete(order)
    db.commit()
