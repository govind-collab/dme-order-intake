"""Tests for /health.

Owns the healthy case and the 503 when the database cannot be reached.
"""

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db import get_db
from app.main import app


class UnreachableDatabase:
    """Stand-in session whose queries fail as if the database were down."""

    def execute(self, statement: object) -> None:
        """Raise an OperationalError."""
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def test_health_is_ok_when_database_answers(client: TestClient) -> None:
    """Expect 200 and status ok."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_is_503_when_database_is_unreachable(client: TestClient) -> None:
    """Expect 503 when the database query fails."""
    app.dependency_overrides[get_db] = UnreachableDatabase

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "database unavailable"}


def test_frontend_origin_passes_cors_preflight(client: TestClient) -> None:
    """Expect the configured frontend origin to be allowed to send a bearer token."""
    response = client.options(
        "/orders",
        headers={
            "Origin": "https://review.example.test",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://review.example.test"


def test_other_origins_get_no_cors_permission(client: TestClient) -> None:
    """Expect any other origin to get no allow-origin header, so browsers block it."""
    preflight = client.options(
        "/orders",
        headers={"Origin": "https://evil.example.test", "Access-Control-Request-Method": "GET"},
    )
    plain = client.get("/health", headers={"Origin": "https://evil.example.test"})

    assert "access-control-allow-origin" not in preflight.headers
    assert "access-control-allow-origin" not in plain.headers
