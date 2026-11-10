"""Routes for orders: manual create, read, update and delete, and PDF upload.

Owns every /orders route. Each route acts only on the caller's own orders; another user's order
answers 404, the same as one that does not exist.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status

from app.db import DbSession
from app.deps import CurrentUser, get_extractor
from app.extractor import Extractor
from app.models import Order, OrderStatus
from app.schemas import OrderInput, OrderRead
from app.services import intake, orders

router = APIRouter(prefix="/orders", tags=["orders"])


def owned_order(order_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Order:
    """Return the caller's order with this id, or raise a 404 if it is not theirs or not there."""
    order = orders.get_owned_order(db, user.id, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return order


OwnedOrder = Annotated[Order, Depends(owned_order)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_order(body: OrderInput, user: CurrentUser, db: DbSession) -> OrderRead:
    """Create an order from values typed in by hand.

    Every field is optional. Any value sent must pass the same checks as an upload, otherwise
    the request gets a 422 that names the field and the reason. Dates are `YYYY-MM-DD`. The
    status is worked out by the server: `complete` when all five fields are set, otherwise
    `needs_review`.
    """
    return OrderRead.model_validate(orders.create_order(db, user.id, body))


@router.post("/upload", status_code=status.HTTP_201_CREATED)
def upload_order(
    file: UploadFile,
    user: CurrentUser,
    db: DbSession,
    extract: Annotated[Extractor, Depends(get_extractor)],
) -> OrderRead:
    """Upload a faxed order PDF and create an order from what it says.

    The PDF (at most 10 MB and 50 pages, not encrypted) is read by Claude, every value is
    checked, and the order is saved and returned.

    **Each field comes back twice.** The top-level fields such as `provider_npi` hold only
    values that passed every check. `field_report` holds what the document said for each field:
    `value_as_read`, a `status` and a `reason`, plus the `page` and `quote` it came from. A
    value that fails a check is never stored on the order, so a field can be null on the order
    while `field_report` shows the value that was read.

    Made-up NPIs trip this first. An NPI must be 10 digits, start with 1 or 2 and pass the NPI
    check digit, so the NPI on the sample order comes back as `provider_npi: null` with
    `field_report.provider_npi` set to `{"status": "invalid", "value_as_read": "9182734556",
    "reason": "NPI must start with 1 or 2"}` and the order status `needs_review`.

    Statuses: `ok` passed, `missing` not found or not readable, `invalid` read but failed a
    check, `conflict` the document gives different values. Fix a field with PATCH and its report
    then says `set by hand`.

    Errors: 413 too large, 415 not a PDF, 422 unreadable or no fields found, 429 over your daily
    upload limit (100 in 24 hours by default), 503 over the service's daily limit, 502 or 503 when
    the model call fails. No order is saved on an error. Every upload that reaches the model
    counts against the limits, even if it fails or its order is deleted later.
    """
    order = intake.create_order_from_pdf(db, user.id, file.file.read(), extract)
    return OrderRead.model_validate(order)


@router.get("")
def list_orders(
    user: CurrentUser,
    db: DbSession,
    order_status: Annotated[OrderStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[OrderRead]:
    """List the caller's orders, newest first.

    Filter with `status` (`complete` or `needs_review`) and page with `limit` (1 to 100, default
    20) and `offset`.
    """
    found = orders.list_orders(db, user.id, order_status, limit, offset)
    return [OrderRead.model_validate(order) for order in found]


@router.get("/{order_id}")
def read_order(order: OwnedOrder) -> OrderRead:
    """Return one of the caller's orders, including its field report."""
    return OrderRead.model_validate(order)


@router.patch("/{order_id}")
def update_order(order: OwnedOrder, body: OrderInput, db: DbSession) -> OrderRead:
    """Change some fields of one of the caller's orders.

    Only the fields sent are changed; send null to clear one. Values must pass the same checks
    as on create, and the status is worked out again. On an uploaded order each field sent also
    updates its `field_report` entry: `ok` with reason `set by hand`, or `missing` with `cleared
    by hand`, keeping the value as read from the document.
    """
    return OrderRead.model_validate(orders.update_order(db, order, body))


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order(order: OwnedOrder, db: DbSession) -> None:
    """Delete one of the caller's orders."""
    orders.delete_order(db, order)
