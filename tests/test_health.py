from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db import get_db
from app.main import app


class UnreachableDatabase:
    def execute(self, statement: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def test_health_is_ok_when_database_answers(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_is_503_when_database_is_unreachable(client: TestClient) -> None:
    app.dependency_overrides[get_db] = UnreachableDatabase

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "database unavailable"}
