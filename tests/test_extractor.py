import base64
import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest
from pydantic import ValidationError

from app import extractor
from app.config import settings
from app.errors import UploadRejected
from app.extractor import ExtractedOrder, extract_with_claude

BLANK_FIELD = {"value": None, "quote": None, "page": None, "issue": "none"}
PARSED = ExtractedOrder(**{field: BLANK_FIELD for field in ExtractedOrder.model_fields})
API_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


class FakeMessages:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.sent: dict[str, Any] = {}

    def parse(self, **request: object) -> object:
        self.sent = request
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def install_fake_client(monkeypatch: pytest.MonkeyPatch, outcome: object) -> FakeMessages:
    messages = FakeMessages(outcome)
    client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    monkeypatch.setattr(extractor, "claude_client", lambda: client)
    return messages


def reply(stop_reason: str, parsed: ExtractedOrder | None = PARSED) -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop_reason, parsed_output=parsed, model="claude-opus-5-5", _request_id="req_1"
    )


def test_sends_pdf_before_the_instruction_and_returns_parsed_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = install_fake_client(monkeypatch, reply("end_turn"))

    assert extract_with_claude(b"%PDF-1.7 bytes") == PARSED

    document, instruction = messages.sent["messages"][0]["content"]
    assert document["source"]["data"] == base64.standard_b64encode(b"%PDF-1.7 bytes").decode()
    assert document["source"]["media_type"] == "application/pdf"
    assert instruction["type"] == "text"
    assert messages.sent["output_format"] is ExtractedOrder
    assert messages.sent["fallbacks"] == "default"


@pytest.mark.parametrize(
    ("outcome", "status"),
    [
        (reply("refusal", parsed=None), 502),
        (reply("max_tokens", parsed=None), 502),
        (anthropic.APIConnectionError(request=API_REQUEST), 503),
        (anthropic.APITimeoutError(request=API_REQUEST), 503),
        (
            anthropic.BadRequestError(
                "bad", response=httpx2.Response(400, request=API_REQUEST), body=None
            ),
            502,
        ),
    ],
)
def test_model_failures_become_upload_errors(
    monkeypatch: pytest.MonkeyPatch, outcome: object, status: int
) -> None:
    install_fake_client(monkeypatch, outcome)

    with pytest.raises(UploadRejected) as rejected:
        extract_with_claude(b"%PDF-1.7")

    assert rejected.value.status_code == status


def test_reply_that_fails_the_strict_model_is_a_model_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValidationError) as invalid:
        ExtractedOrder.model_validate_json("{}")
    install_fake_client(monkeypatch, invalid.value)

    with pytest.raises(UploadRejected) as rejected:
        extract_with_claude(b"%PDF-1.7")

    assert rejected.value.status_code == 502


@pytest.mark.parametrize(
    "bad_field",
    [
        {**BLANK_FIELD, "page": "1"},
        {**BLANK_FIELD, "issue": "blurry"},
        {**BLANK_FIELD, "confidence": 0.9},
    ],
)
def test_strict_reply_model_rejects_coercion_unknown_values_and_extra_keys(
    bad_field: dict[str, Any],
) -> None:
    fields = {field: BLANK_FIELD for field in ExtractedOrder.model_fields}

    with pytest.raises(ValidationError):
        ExtractedOrder.model_validate_json(json.dumps(fields | {"provider_npi": bad_field}))


def test_missing_api_key_means_extraction_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    extractor.claude_client.cache_clear()

    with pytest.raises(UploadRejected) as rejected:
        extract_with_claude(b"%PDF-1.7")

    assert rejected.value.status_code == 503
