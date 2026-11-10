"""Request and response models, and the field types that carry the order checks.

Owns the checked field types (names, NPI, date of birth), the request bodies and the response models
shown in /docs. Uploads reuse the same field types, so a value is checked the same way however it
arrives.
"""

import re
import uuid
from collections.abc import Callable
from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, StringConstraints

from app.checks import dob_problem, name_problem, npi_problem
from app.models import FieldStatus, OrderSource, OrderStatus


def rejected_by[T](problem: Callable[[T], str | None]) -> AfterValidator:
    """Return a validator that raises the reason given by a `*_problem` check.

    The reason becomes the 422 message, and it never contains the value itself.
    """

    def validate(value: T) -> T:
        """Raise ValueError with the check's reason, or return the value unchanged."""
        reason = problem(value)
        if reason:
            raise ValueError(reason)
        return value

    return AfterValidator(validate)


Email = Annotated[str, StringConstraints(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]
PatientName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    rejected_by(name_problem),
]
ProviderName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    rejected_by(name_problem),
]
Npi = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=10), rejected_by(npi_problem)
]


def iso_date_only(value: object) -> object:
    """Return the value if it is a date or a YYYY-MM-DD string, otherwise raise ValueError.

    Without this, pydantic would also read a number as a Unix timestamp.
    """
    if isinstance(value, date) or (
        isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
    ):
        return value
    raise ValueError("date must be a YYYY-MM-DD string")


BirthDate = Annotated[
    date,
    BeforeValidator(iso_date_only),
    rejected_by(lambda dob: dob_problem(dob, date.today())),
]


class UserCreate(BaseModel):
    """Email and password for a new account."""

    email: Email
    password: Password


class UserRead(BaseModel):
    """An account as returned by the API; the password hash is never included."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    created_at: datetime


class Token(BaseModel):
    """A bearer token for the Authorization header."""

    access_token: str
    token_type: str = "bearer"


class OrderInput(BaseModel):
    """Order fields for create and update; every field is optional and every value is checked."""

    patient_first_name: PatientName | None = None
    patient_last_name: PatientName | None = None
    patient_dob: BirthDate | None = None
    provider_name: ProviderName | None = None
    provider_npi: Npi | None = None


class FieldReport(BaseModel):
    """What the document said for one field and what became of it.

    `value_as_read` is the text as printed, even when it was refused. `status` is ok, missing,
    invalid or conflict, and `reason` says why a value was not stored. `page` and `quote` show
    where in the document it came from.
    """

    status: FieldStatus
    value_as_read: str | None
    reason: str | None
    page: int | None
    quote: str | None


class OrderRead(BaseModel):
    """An order as returned by the API.

    The five fields hold only values that passed every check. For uploaded orders,
    `field_report` shows per field what the document said and why a value was refused; it is
    null for orders created by hand.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: OrderStatus
    source: OrderSource
    patient_first_name: str | None
    patient_last_name: str | None
    patient_dob: date | None
    provider_name: str | None
    provider_npi: str | None
    field_report: dict[str, FieldReport] | None
    created_at: datetime
    updated_at: datetime
