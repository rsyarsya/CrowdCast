import pytest
from fastapi.testclient import TestClient

from app.models import User
from app.services.login_limiter import LoginLimiter
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.anyio

LOGIN = "/api/v1/auth/login"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_limiter_blocks_after_max_failures_until_window_passes() -> None:
    clock = FakeClock()
    limiter = LoginLimiter(3, 60, clock)
    for _ in range(3):
        assert limiter.retry_after("k") is None
        limiter.record_failure("k")
        clock.now += 10
    assert limiter.retry_after("k") == 30
    assert limiter.retry_after("other") is None
    clock.now += 30
    assert limiter.retry_after("k") is None


def test_limiter_reset_clears_failures() -> None:
    limiter = LoginLimiter(1, 60, FakeClock())
    limiter.record_failure("k")
    assert limiter.retry_after("k") == 60
    limiter.reset("k")
    assert limiter.retry_after("k") is None


async def test_login_is_blocked_after_five_failures(client: TestClient, operator_user: User) -> None:
    def login(email: str, password: str):
        return client.post(LOGIN, data={"username": email, "password": password})

    for _ in range(5):
        assert login("operator@crowdcast.test", "salah-salah").status_code == 401
    blocked = login("Operator@crowdcast.test", TEST_PASSWORD)
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": "too_many_attempts"}
    assert 0 < int(blocked.headers["Retry-After"]) <= 900

    assert login("lain@crowdcast.test", "salah-salah").status_code == 401


async def test_successful_login_resets_failures(client: TestClient, operator_user: User) -> None:
    for _ in range(4):
        client.post(LOGIN, data={"username": "operator@crowdcast.test", "password": "salah"})
    assert client.post(LOGIN, data={"username": "operator@crowdcast.test", "password": TEST_PASSWORD}).status_code == 200
    for _ in range(4):
        assert client.post(LOGIN, data={"username": "operator@crowdcast.test", "password": "salah"}).status_code == 401
