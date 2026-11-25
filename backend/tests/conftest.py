import os
from collections.abc import AsyncIterator, Iterator

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command

# Tests always run against the dedicated test database, never the dev database
# configured in backend/.env. Environment variables take precedence over .env.
DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://crowdcast:crowdcast@localhost:5433/crowdcast_test"
)
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

from app.core.config import BACKEND_DIR, get_settings  # noqa: E402
from app.main import create_app  # noqa: E402

TABLES = "users, cameras, crowd_records, predictions"


def alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = TEST_DATABASE_URL
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Bring the test database schema to the latest migration once per run."""
    command.upgrade(alembic_config(), "head")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """A session on a fresh engine; every table is emptied after the test."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=pool.NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            yield session
        async with engine.begin() as connection:
            await connection.execute(
                text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE")
            )
    finally:
        await engine.dispose()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """App client; the context manager runs the lifespan (engine setup)."""
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()
