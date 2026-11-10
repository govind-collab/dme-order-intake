"""Turning an uploaded PDF into an order.

Owns the PDF checks, the daily upload limits, parsing dates as printed, the review that turns each
extracted field into a stored value and a field report, and the upload flow itself.
"""

import logging
import re
import uuid
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from typing import Any

from pydantic import TypeAdapter, ValidationError
from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import UploadRejected
from app.extractor import ExtractedField, Extractor
from app.models import FieldStatus, Order, UploadAttempt
from app.schemas import FieldReport, OrderInput
from app.services import orders

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 50
ISO_DATE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
US_DATE = re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})")
WRITTEN_DATE_FORMATS = (
    "%B %d, %Y",
    "%b %d, %Y",
    "%B %d %Y",
    "%b %d %Y",
    "%d %B %Y",
    "%d %b %Y",
    "%d-%b-%Y",
    "%d-%B-%Y",
)
# The same validators as manual orders, so a value is checked the same way however it arrives
FIELD_TYPES = {
    field: TypeAdapter(info.annotation) for field, info in OrderInput.model_fields.items()
}

logger = logging.getLogger(__name__)
# pypdf quotes raw bytes from damaged files in its log messages, and those bytes can be patient
# text. Problems that matter still raise, and those become a 422.
logging.getLogger("pypdf").setLevel(logging.CRITICAL + 1)


def count_pdf_pages(pdf: bytes) -> int:
    """Return the page count of an uploaded PDF after checking the model can read it.

    Raises UploadRejected: 413 over 10 MB, 415 when it does not start like a PDF, and 422 when
    it cannot be opened, is encrypted, or has no pages or more than 50.
    """
    if len(pdf) > MAX_PDF_BYTES:
        raise UploadRejected(413, "PDF is larger than 10 MB")
    if b"%PDF-" not in pdf[:1024]:
        raise UploadRejected(415, "File is not a PDF")
    try:
        reader = PdfReader(BytesIO(pdf))
        encrypted = reader.is_encrypted
        pages = 0 if encrypted else len(reader.pages)
    except Exception as error:  # pypdf raises many different exception types on malformed files
        raise UploadRejected(422, "PDF could not be opened") from error
    if encrypted:
        raise UploadRejected(422, "PDF is encrypted")
    if not 1 <= pages <= MAX_PDF_PAGES:
        raise UploadRejected(422, f"PDF must have between 1 and {MAX_PDF_PAGES} pages")
    return pages


def parse_printed_date(text: str) -> tuple[date | None, str | None]:
    """Parse a date as printed, returning it or None with the reason it could not be read.

    Numeric dates are read as US month/day/year. A two-digit year is refused instead of guessing
    the century, and a date that does not exist, such as 02/30, is refused too.
    """
    if match := ISO_DATE.fullmatch(text):
        year, month, day = (int(part) for part in match.groups())
    elif match := US_DATE.fullmatch(text):
        if len(match[3]) == 2:
            return None, "two-digit year is ambiguous"
        month, day, year = (int(part) for part in match.groups())
    else:
        for date_format in WRITTEN_DATE_FORMATS:
            with suppress(ValueError):
                return datetime.strptime(text, date_format).date(), None
        return None, "date format is not recognised"
    try:
        return date(year, month, day), None
    except ValueError:
        return None, "not a real calendar date"


def checked_value(field: str, text: str) -> tuple[Any, str | None]:
    """Return the value to store for one field's text, or None with the reason it failed.

    Spaces and hyphens are removed from an NPI and printed dates are parsed first; then the
    value goes through the same field type as a manual order.
    """
    candidate: Any = text
    if field == "provider_npi":
        candidate = re.sub(r"[\s-]", "", text)
    elif field == "patient_dob":
        candidate, problem = parse_printed_date(text)
        if problem:
            return None, problem
    try:
        return FIELD_TYPES[field].validate_python(candidate), None
    except ValidationError as error:
        return None, error.errors()[0]["msg"].removeprefix("Value error, ")


def review_field(field: str, read: ExtractedField) -> tuple[Any, FieldReport]:
    """Return the value to store for one extracted field, and its field report.

    Missing (null or blank), illegible, ambiguous and conflicting readings store nothing, so a
    reply of empty strings ends as "no fields found". A reading that fails a check stores nothing
    either, and its report keeps the value as read with the reason.
    """
    value, status, reason = None, FieldStatus.OK, None
    if read.issue == "conflicting":
        status, reason = FieldStatus.CONFLICT, "the document gives different values"
    elif read.issue != "none":
        status, reason = FieldStatus.MISSING, f"the value is {read.issue}"
    elif read.value is None or not read.value.strip():
        status, reason = FieldStatus.MISSING, "not found in the document"
    else:
        value, reason = checked_value(field, read.value.strip())
        if reason:
            status = FieldStatus.INVALID
    report = FieldReport(
        status=status, value_as_read=read.value, reason=reason, page=read.page, quote=read.quote
    )
    return value, report


def claim_upload_slot(db: Session, owner_id: uuid.UUID) -> None:
    """Record an upload attempt, then refuse it if it takes a daily limit over.

    The attempt is committed before anything is counted, so uploads sent at the same moment see
    each other and cannot all slip under a limit. An attempt stays counted for 24 hours even if
    the upload is rejected afterwards or its order is deleted. An attempt refused here is
    removed again, so retrying while over a limit does not extend the wait. Raises
    UploadRejected: 429 past the per-user limit, 503 past the limit across all users.
    """
    attempt = UploadAttempt(user_id=owner_id)
    db.add(attempt)
    db.commit()
    recent = select(func.count()).where(
        UploadAttempt.created_at >= datetime.now(UTC) - timedelta(days=1)
    )
    per_user = settings.daily_upload_limit_per_user
    over_user_limit = db.scalar(recent.where(UploadAttempt.user_id == owner_id)) > per_user
    over_total_limit = db.scalar(recent) > settings.daily_upload_limit_total
    if over_user_limit or over_total_limit:
        db.delete(attempt)
    # Ending the transaction also hands the connection back before the slow model call
    db.commit()
    if over_user_limit:
        raise UploadRejected(429, f"Upload limit of {per_user} per 24 hours reached")
    if over_total_limit:
        raise UploadRejected(503, "The service has reached its daily upload limit")


def create_order_from_pdf(
    db: Session, owner_id: uuid.UUID, pdf: bytes, extract: Extractor
) -> Order:
    """Check, read and save an uploaded PDF, and return the new order.

    Raises UploadRejected: the PDF errors from count_pdf_pages, the limit errors from
    claim_upload_slot, the model errors from the extractor, and 422 when no field was found at
    all. No order is saved when it raises.
    """
    pages = count_pdf_pages(pdf)
    claim_upload_slot(db, owner_id)
    reviewed = {field: review_field(field, read) for field, read in extract(pdf)}
    if all(report.status == FieldStatus.MISSING for _, report in reviewed.values()):
        raise UploadRejected(422, "No order fields were found in the document")
    values = {field: value for field, (value, _) in reviewed.items()}
    reports = {field: report for field, (_, report) in reviewed.items()}
    order = orders.create_uploaded_order(db, owner_id, values, reports, pdf, pages)
    logger.info("upload saved order=%s status=%s pages=%d", order.id, order.status, pages)
    return order
