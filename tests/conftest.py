import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Settings are read when app modules are imported, so the test database must be set first
os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp()).as_posix()}/test.db"
os.environ["JWT_SECRET"] = "test-only-secret-that-is-at-least-32-characters"
# Environment variables beat .env, so the real API key never reaches the test process
os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture
def client() -> Iterator[TestClient]:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth_headers(client: TestClient, email: str) -> dict[str, str]:
    password = "correct horse battery"
    client.post("/auth/register", json={"email": email, "password": password})
    response = client.post("/auth/token", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def alice(client: TestClient) -> dict[str, str]:
    return auth_headers(client, "alice@example.com")


@pytest.fixture
def bob(client: TestClient) -> dict[str, str]:
    return auth_headers(client, "bob@example.com")
