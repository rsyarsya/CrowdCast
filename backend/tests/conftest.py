import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

# Tests always run against the dedicated test database, never the dev database
# configured in backend/.env. Environment variables take precedence over .env.
DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://crowdcast:crowdcast@localhost:5433/crowdcast_test"
)
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def client() -> Iterator[TestClient]:
    """App client; the context manager runs the lifespan (engine setup)."""
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()
