"""Tests for PDF upload, using a fake extractor so no request leaves the machine.

Owns the checks on how each reading is stored and reported, date and NPI parsing, file rejections
before the model is called, the quota, PATCH on uploaded orders, privacy between users and log
hygiene.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from pypdf import PdfWriter

from app.db import SessionLocal
from app.deps import get_extractor
from app.errors import UploadRejected
from app.extractor import ExtractedField, ExtractedOrder
from app.main import app
from app.models import Order
from app.services import intake
from app.services.intake import MAX_PDF_BYTES

Headers = dict[str, str]


def make_pdf(pages: int = 1, password: str | None = None) -> bytes:
    """Return a blank PDF with this many pages, encrypted when a password is given."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    if password:
        writer.encrypt(password, algorithm="RC4-128")
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def read(value: str | None, issue: str = "none") -> ExtractedField:
    """Return an extracted field, with a quote and page when there is a value."""
    quote = None if value is None else f"Label: {value}"
    page = None if value is None else 1
    return ExtractedField(value=value, quote=quote, page=page, issue=issue)


def reading(**overrides: ExtractedField) -> ExtractedOrder:
    """Return a clean extraction of all five fields, with some fields replaced."""
    fields = {
        "patient_first_name": read("Ada"),
        "patient_last_name": read("Lovelace"),
        "patient_dob": read("12/10/1985"),
        "provider_name": read("Grace Hopper"),
        "provider_npi": read("1234567893"),
    }
    return ExtractedOrder(**(fields | overrides))


def use_extractor(result: ExtractedOrder | Exception) -> list[bytes]:
    """Make uploads use a fake extractor with this result and return the PDFs it receives."""
    calls: list[bytes] = []

    def fake_extract(pdf: bytes) -> ExtractedOrder:
        """Record the PDF and return or raise the result."""
        calls.append(pdf)
        if isinstance(result, Exception):
            raise result
        return result

    app.dependency_overrides[get_extractor] = lambda: fake_extract
    return calls


def upload(
    client: TestClient,
    headers: Headers,
    content: bytes | None = None,
    filename: str = "order.pdf",
) -> Response:
    """Upload a PDF, a blank one by default, and return the response."""
    content = make_pdf() if content is None else content
    files = {"file": (filename, content, "application/pdf")}
    return client.post("/orders/upload", files=files, headers=headers)


def test_clean_reading_creates_complete_order(client: TestClient, alice: Headers) -> None:
    """Expect a complete order, every report ok and the exact PDF sent to the extractor."""
    pdf = make_pdf(pages=3)
    calls = use_extractor(reading())

    response = upload(client, alice, pdf)

    assert response.status_code == 201
    order = response.json()
    assert calls == [pdf]
    assert order["status"] == "complete"
    assert order["source"] == "upload"
    assert order["patient_dob"] == "1985-12-10"
    assert order["provider_npi"] == "1234567893"
    assert {report["status"] for report in order["field_report"].values()} == {"ok"}


def test_value_that_fails_a_check_is_reported_but_not_stored(
    client: TestClient, alice: Headers
) -> None:
    """Expect a null NPI on the order, and the value as read with its reason in the report."""
    use_extractor(reading(provider_npi=read("1234567890")))

    order = upload(client, alice).json()

    assert order["status"] == "needs_review"
    assert order["provider_npi"] is None
    assert order["field_report"]["provider_npi"] == {
        "status": "invalid",
        "value_as_read": "1234567890",
        "reason": "NPI fails the check digit",
        "page": 1,
        "quote": "Label: 1234567890",
    }


@pytest.mark.parametrize(
    ("extracted", "status", "reason"),
    [
        (read(None), "missing", "not found in the document"),
        (read("Lovel?ce", "illegible"), "missing", "the value is illegible"),
        (read("Lovelace or Byron", "ambiguous"), "missing", "the value is ambiguous"),
        (read(None, "conflicting"), "conflict", "the document gives different values"),
    ],
)
def test_unusable_reading_is_not_stored(
    client: TestClient, alice: Headers, extracted: ExtractedField, status: str, reason: str
) -> None:
    """Expect missing, illegible, ambiguous and conflicting readings to store nothing."""
    use_extractor(reading(patient_last_name=extracted))

    order = upload(client, alice).json()

    assert order["patient_last_name"] is None
    assert order["status"] == "needs_review"
    report = order["field_report"]["patient_last_name"]
    assert (report["status"], report["reason"], report["value_as_read"]) == (
        status,
        reason,
        extracted.value,
    )


@pytest.mark.parametrize(
    "printed", ["12/10/1985", "12-10-1985", "12.10.1985", "1985-12-10", "December 10, 1985"]
)
def test_printed_dates_of_birth_are_parsed_as_us_dates(
    client: TestClient, alice: Headers, printed: str
) -> None:
    """Expect each printed form of 10 December 1985 to be stored as 1985-12-10."""
    use_extractor(reading(patient_dob=read(printed)))

    assert upload(client, alice).json()["patient_dob"] == "1985-12-10"


@pytest.mark.parametrize(
    ("printed", "reason"),
    [
        ("12/10/85", "two-digit year is ambiguous"),
        ("02/30/1985", "not a real calendar date"),
        ("sometime in 1985", "date format is not recognised"),
        ("12/10/2999", "date of birth is in the future"),
        ("12/10/1850", "date of birth is more than 130 years ago"),
    ],
)
def test_unusable_dates_of_birth_are_rejected_with_reason(
    client: TestClient, alice: Headers, printed: str, reason: str
) -> None:
    """Expect two-digit, impossible, unreadable, future and too-old dates to be refused."""
    use_extractor(reading(patient_dob=read(printed)))

    order = upload(client, alice).json()

    assert order["patient_dob"] is None
    assert order["field_report"]["patient_dob"]["reason"] == reason


@pytest.mark.parametrize("printed", ["1234 567 893", "123-456-7893", " 1234567893 "])
def test_npi_separators_are_removed(client: TestClient, alice: Headers, printed: str) -> None:
    """Expect spaces and hyphens in a printed NPI to be dropped."""
    use_extractor(reading(provider_npi=read(printed)))

    assert upload(client, alice).json()["provider_npi"] == "1234567893"


def test_curly_apostrophe_name_is_kept(client: TestClient, alice: Headers) -> None:
    """Expect a name with a curly apostrophe to be stored as printed."""
    use_extractor(reading(patient_last_name=read("O’Brien")))

    assert upload(client, alice).json()["patient_last_name"] == "O’Brien"


def test_overlong_name_is_invalid(client: TestClient, alice: Headers) -> None:
    """Expect a name over 100 characters to be reported invalid."""
    use_extractor(reading(patient_first_name=read("A" * 101)))

    report = upload(client, alice).json()["field_report"]["patient_first_name"]

    assert report["status"] == "invalid"
    assert report["reason"] == "String should have at most 100 characters"


def test_document_with_no_fields_is_rejected_and_not_saved(
    client: TestClient, alice: Headers
) -> None:
    """Expect a 422 and no order when nothing was found."""
    nothing = {field: read(None) for field in ExtractedOrder.model_fields}
    use_extractor(ExtractedOrder(**nothing))

    response = upload(client, alice)

    assert response.status_code == 422
    assert response.json() == {"detail": "No order fields were found in the document"}
    assert client.get("/orders", headers=alice).json() == []


@pytest.mark.parametrize(
    ("content", "status"),
    [
        (b"", 415),
        (b"plain text, not a pdf", 415),
        (b"%PDF-1.7 truncated garbage", 422),
        (make_pdf(password="secret"), 422),
        (make_pdf(pages=51), 422),
        (b"%PDF-" + b"0" * MAX_PDF_BYTES, 413),
    ],
)
def test_unusable_files_are_rejected_before_the_model_is_called(
    client: TestClient, alice: Headers, content: bytes, status: int
) -> None:
    """Expect bad files to be refused with the right status and no model call."""
    calls = use_extractor(reading())

    response = upload(client, alice, content)

    assert response.status_code == status
    assert calls == []
    assert client.get("/orders", headers=alice).json() == []


def test_request_far_over_the_cap_is_refused(client: TestClient, alice: Headers) -> None:
    """Expect a 413 from the size limit for a body twice the cap."""
    calls = use_extractor(reading())

    response = upload(client, alice, b"%PDF-" + b"0" * (MAX_PDF_BYTES * 2))

    assert response.status_code == 413
    assert calls == []


def test_extraction_failure_saves_nothing(client: TestClient, alice: Headers) -> None:
    """Expect the extractor's error status and no order."""
    use_extractor(UploadRejected(503, "Extraction service is unavailable, try again"))

    response = upload(client, alice)

    assert response.status_code == 503
    assert response.json() == {"detail": "Extraction service is unavailable, try again"}
    assert client.get("/orders", headers=alice).json() == []


def test_upload_requires_a_token(client: TestClient) -> None:
    """Expect a 401 and no model call without a token."""
    calls = use_extractor(reading())

    assert upload(client, {}).status_code == 401
    assert calls == []


def test_uploaded_order_is_private_to_the_uploader(
    client: TestClient, alice: Headers, bob: Headers
) -> None:
    """Expect another user to get a 404 and an empty list."""
    use_extractor(reading())
    order_id = upload(client, alice).json()["id"]

    assert client.get(f"/orders/{order_id}", headers=bob).status_code == 404
    assert client.get("/orders", headers=bob).json() == []


def test_patch_updates_the_field_report_of_the_fixed_field(
    client: TestClient, alice: Headers
) -> None:
    """Expect a fixed field's report to say set by hand, a cleared one cleared by hand."""
    use_extractor(reading(provider_npi=read("1234567890")))
    order = upload(client, alice).json()
    url = f"/orders/{order['id']}"

    fixed = client.patch(url, json={"provider_npi": "1234567893"}, headers=alice).json()
    cleared = client.patch(url, json={"provider_npi": None}, headers=alice).json()

    assert fixed["status"] == "complete"
    assert fixed["field_report"]["provider_npi"] == {
        **order["field_report"]["provider_npi"],
        "status": "ok",
        "reason": "set by hand",
    }
    assert fixed["field_report"]["patient_dob"] == order["field_report"]["patient_dob"]
    assert cleared["status"] == "needs_review"
    assert cleared["field_report"]["provider_npi"]["status"] == "missing"
    assert cleared["field_report"]["provider_npi"]["reason"] == "cleared by hand"


def test_patch_on_manual_order_adds_no_field_report(client: TestClient, alice: Headers) -> None:
    """Expect a manual order to keep a null field report after PATCH."""
    order = client.post("/orders", json={"patient_first_name": "Ada"}, headers=alice).json()

    patched = client.patch(
        f"/orders/{order['id']}", json={"patient_last_name": "Lovelace"}, headers=alice
    )

    assert patched.json()["field_report"] is None


def test_daily_upload_quota_counts_recent_uploads_per_user(
    client: TestClient, alice: Headers, bob: Headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expect a 429 past the limit; manual, other users' and day-old uploads don't count."""
    monkeypatch.setattr(intake, "DAILY_UPLOAD_LIMIT", 2)
    calls = use_extractor(reading())
    first = upload(client, alice).json()
    upload(client, alice)
    client.post("/orders", json={"patient_first_name": "Ada"}, headers=alice)

    refused = upload(client, alice)
    assert refused.status_code == 429
    assert refused.json() == {"detail": "Upload limit of 2 per 24 hours reached"}
    assert len(calls) == 2
    assert upload(client, bob).status_code == 201

    with SessionLocal() as db:
        db.get(Order, uuid.UUID(first["id"])).created_at = datetime.now(UTC) - timedelta(hours=25)
        db.commit()
    assert upload(client, alice).status_code == 201


def test_logs_hold_no_field_values_filename_or_quotes(
    client: TestClient, alice: Headers, caplog: pytest.LogCaptureFixture
) -> None:
    """Expect no field value, quote or filename in the logs after saved and rejected uploads."""
    caplog.set_level(logging.DEBUG)
    filename = "scan-for-zebedee-quillfeather.pdf"
    fields = {
        "patient_first_name": read("Zebedee"),
        "patient_last_name": read("Quillfeather"),
        "patient_dob": read("03/14/1962"),
        "provider_name": read("Ottoline Vex"),
        "provider_npi": read("1234567890"),
    }
    sensitive = [filename, "1962-03-14"] + [
        text for field in fields.values() for text in (field.value, field.quote)
    ]

    use_extractor(ExtractedOrder(**fields))
    saved = upload(client, alice, filename=filename)
    use_extractor(UploadRejected(502, "The model declined to read this document"))
    model_failed = upload(client, alice, filename=filename)
    not_a_pdf = upload(client, alice, b"plain text", filename=filename)

    assert [saved.status_code, model_failed.status_code, not_a_pdf.status_code] == [201, 502, 415]
    assert "upload saved" in caplog.text and "upload rejected" in caplog.text
    logged = caplog.text + "".join(str(record.args) for record in caplog.records)
    for text in sensitive:
        assert text not in logged


def test_damaged_pdf_text_never_reaches_the_log(
    client: TestClient, alice: Headers, caplog: pytest.LogCaptureFixture
) -> None:
    """Expect pypdf's complaints about a damaged PDF, which quote its bytes, to stay out of logs."""
    caplog.set_level(logging.DEBUG)
    damaged = make_pdf().replace(
        b"/Type /Page\n", b"/Type /Page\n/Note ] (Order for Zebedee Quillfeather)\n", 1
    )
    use_extractor(reading())

    response = upload(client, alice, damaged)

    assert response.status_code == 201
    assert "Zebedee" not in caplog.text
