"""Tests for registration, login and tokens.

Owns the checks that emails are case-insensitive, that a wrong password and an unknown email fail
the same way, that bad tokens resolve to nobody, and that 422s never echo input.
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from argon2.exceptions import VerifyMismatchError
from fastapi.testclient import TestClient
from httpx2 import Response

from app.config import settings
from app.db import SessionLocal
from app.services import auth
from app.services.auth import authenticate, create_access_token, user_from_token

PASSWORD = "correct horse battery"


def register(client: TestClient, email: str, password: str = PASSWORD) -> Response:
    """Post a registration and return the response."""
    return client.post("/auth/register", json={"email": email, "password": password})


def login(client: TestClient, email: str, password: str = PASSWORD) -> Response:
    """Post a login form and return the response."""
    return client.post("/auth/token", data={"username": email, "password": password})


def test_register_returns_user_without_password(client: TestClient) -> None:
    """Expect the lower-cased email back and no password field."""
    response = register(client, "Alice@Example.com")

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert set(body) == {"id", "email", "created_at"}


def test_register_rejects_same_email_in_other_case(client: TestClient) -> None:
    """Expect a 409 for an email already registered in another case."""
    register(client, "alice@example.com")

    assert register(client, "ALICE@example.com").status_code == 409


def test_register_rejects_short_password(client: TestClient) -> None:
    """Expect a 422 for a password under 8 characters."""
    assert register(client, "alice@example.com", "short").status_code == 422


def test_token_issued_for_correct_password(client: TestClient) -> None:
    """Expect a bearer token for the right password."""
    register(client, "alice@example.com")

    response = login(client, "alice@example.com")

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


def test_token_refused_for_wrong_password(client: TestClient) -> None:
    """Expect a 401 for a wrong password."""
    register(client, "alice@example.com")

    assert login(client, "alice@example.com", "wrong password").status_code == 401


def test_token_refused_for_unknown_email(client: TestClient) -> None:
    """Expect a 401 for an email with no account."""
    assert login(client, "nobody@example.com").status_code == 401


class CountingHasher:
    """Stand-in password hasher that counts checks and always reports a mismatch."""

    def __init__(self) -> None:
        """Start the count at zero."""
        self.verified = 0

    def verify(self, password_hash: str, password: str) -> bool:
        """Count the check and raise a mismatch."""
        self.verified += 1
        raise VerifyMismatchError


def test_unknown_email_still_runs_one_password_check(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expect one password check for an unknown email, as for a wrong password."""
    hasher = CountingHasher()
    monkeypatch.setattr(auth, "password_hasher", hasher)

    with SessionLocal() as db:
        assert authenticate(db, "nobody@example.com", PASSWORD) is None

    assert hasher.verified == 1


def test_token_resolves_to_its_user(client: TestClient) -> None:
    """Expect a fresh token to resolve to the user it was made for."""
    user_id = uuid.UUID(register(client, "alice@example.com").json()["id"])

    with SessionLocal() as db:
        user = user_from_token(db, create_access_token(user_id))

    assert user is not None and user.id == user_id


def test_expired_forged_and_garbage_tokens_resolve_to_nobody(client: TestClient) -> None:
    """Expect no user for an expired token, one signed with another key, and a non-token."""
    user_id = register(client, "alice@example.com").json()["id"]
    past = datetime.now(UTC) - timedelta(minutes=1)
    expired = jwt.encode({"sub": user_id, "exp": past}, settings.jwt_secret, algorithm="HS256")
    future = datetime.now(UTC) + timedelta(minutes=5)
    forged = jwt.encode({"sub": user_id, "exp": future}, "x" * 32, algorithm="HS256")

    with SessionLocal() as db:
        for token in (expired, forged, "not-a-token"):
            assert user_from_token(db, token) is None


def test_validation_errors_never_echo_input(client: TestClient) -> None:
    """Send bad requests carrying a marker and expect 422s without the marker."""
    marker = "MARKER-5f2c9d"
    bad_requests = [
        client.post("/auth/register", json={"email": f"{marker}-no-at-sign", "password": PASSWORD}),
        client.post("/auth/register", json={"email": "a@example.com", "password": marker * 20}),
        client.post(
            "/auth/register",
            content=f'{{"email": "{marker}',
            headers={"Content-Type": "application/json"},
        ),
        client.post("/auth/token", data={"username": marker * 30, "password": PASSWORD}),
    ]

    for response in bad_requests:
        assert response.status_code == 422
        assert marker not in response.text
