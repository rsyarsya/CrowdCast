import logging

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def access_log(caplog: pytest.LogCaptureFixture):
    logger = logging.getLogger("app.access")
    logger.addHandler(caplog.handler)
    caplog.set_level(logging.INFO, logger="app.access")
    yield caplog
    logger.removeHandler(caplog.handler)


def test_request_id_is_created_returned_and_logged(client: TestClient, access_log) -> None:
    response = client.get("/health", params={"ticket": "secret-ticket"})
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 32
    message = next(r.getMessage() for r in access_log.records if "/health" in r.getMessage())
    assert message.startswith("GET /health 200 ")
    assert f"rid={request_id}" in message
    assert "secret-ticket" not in message


def test_valid_incoming_request_id_is_kept_and_invalid_one_replaced(client: TestClient) -> None:
    kept = client.get("/health", headers={"X-Request-ID": "fe-abc.123"})
    assert kept.headers["X-Request-ID"] == "fe-abc.123"
    replaced = client.get("/health", headers={"X-Request-ID": "bad id"})
    assert replaced.headers["X-Request-ID"] != "bad id"


def test_unexpected_error_returns_internal_error_with_request_id(access_log) -> None:
    get_settings.cache_clear()
    app = create_app()

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("database exploded")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom", headers={"X-Request-ID": "req-1"})
    get_settings.cache_clear()

    assert response.status_code == 500
    assert response.json() == {"detail": "internal_error", "request_id": "req-1"}
    assert response.headers["X-Request-ID"] == "req-1"
    assert any(r.getMessage().startswith("GET /boom 500") for r in access_log.records)
