"""Shared test setup: a fresh SQLite database per test and two signed-in users.

Owns the test environment variables, set before any app import so the real database and API key are
never used.
"""

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

# Settings are read when app modules are imported, so the test database must be set first
os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp()).as_posix()}/test.db"
os.environ["JWT_SECRET"] = "test-only-secret-that-is-at-least-32-characters"
# Environment variables beat .env, so the real API key never reaches the test process
os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"
os.environ["FRONTEND_ORIGIN"] = "https://review.example.test"

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture
def empty_database() -> None:
    """Drop every table, Alembic's version table included."""
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))


@pytest.fixture
def client(empty_database: None) -> Iterator[TestClient]:
    """Yield a test client on a freshly migrated database and remove overrides afterwards."""
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth_headers(client: TestClient, email: str) -> dict[str, str]:
    """Register a user with this email and return a bearer header for them."""
    password = "correct horse battery"
    client.post("/auth/register", json={"email": email, "password": password})
    response = client.post("/auth/token", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def alice(client: TestClient) -> dict[str, str]:
    """Return a bearer header for the first test user."""
    return auth_headers(client, "alice@example.com")


@pytest.fixture
def bob(client: TestClient) -> dict[str, str]:
    """Return a bearer header for a second, unrelated test user."""
    return auth_headers(client, "bob@example.com")
