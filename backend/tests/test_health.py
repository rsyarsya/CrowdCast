import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_database_is_up(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_ready_returns_503_when_database_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Port 1 on localhost has no PostgreSQL server, so the connection fails.
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://nobody:nothing@127.0.0.1:1/none"
    )
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.get("/health/ready")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}


def test_liveness_does_not_need_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://nobody:nothing@127.0.0.1:1/none"
    )
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.get("/health")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
