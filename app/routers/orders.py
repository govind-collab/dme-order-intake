import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db import DbSession
from app.deps import CurrentUser
from app.models import Order, OrderStatus
from app.schemas import OrderInput, OrderRead
from app.services import orders

router = APIRouter(prefix="/orders", tags=["orders"])


def owned_order(order_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Order:
    order = orders.get_owned_order(db, user.id, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return order


OwnedOrder = Annotated[Order, Depends(owned_order)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_order(body: OrderInput, user: CurrentUser, db: DbSession) -> OrderRead:
    return OrderRead.model_validate(orders.create_order(db, user.id, body))


@router.get("")
def list_orders(
    user: CurrentUser,
    db: DbSession,
    order_status: Annotated[OrderStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[OrderRead]:
    found = orders.list_orders(db, user.id, order_status, limit, offset)
    return [OrderRead.model_validate(order) for order in found]


@router.get("/{order_id}")
def read_order(order: OwnedOrder) -> OrderRead:
    return OrderRead.model_validate(order)


@router.patch("/{order_id}")
def update_order(order: OwnedOrder, body: OrderInput, db: DbSession) -> OrderRead:
    return OrderRead.model_validate(orders.update_order(db, order, body))


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order(order: OwnedOrder, db: DbSession) -> None:
    orders.delete_order(db, order)
