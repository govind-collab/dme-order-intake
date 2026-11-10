import re
import uuid
from collections.abc import Callable
from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, StringConstraints

from app.checks import dob_problem, name_problem, npi_problem
from app.models import FieldStatus, OrderSource, OrderStatus


def rejected_by[T](problem: Callable[[T], str | None]) -> AfterValidator:
    def validate(value: T) -> T:
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
    email: Email
    password: Password


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OrderInput(BaseModel):
    patient_first_name: PatientName | None = None
    patient_last_name: PatientName | None = None
    patient_dob: BirthDate | None = None
    provider_name: ProviderName | None = None
    provider_npi: Npi | None = None


class FieldReport(BaseModel):
    status: FieldStatus
    value_as_read: str | None
    reason: str | None
    page: int | None
    quote: str | None


class OrderRead(BaseModel):
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
