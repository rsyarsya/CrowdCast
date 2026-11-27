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
from app.core.security import create_access_token, get_password_hash  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import User, UserRole  # noqa: E402

TABLES = "users, cameras, crowd_records, predictions, alerts"


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


TEST_PASSWORD = "rahasia-123"


async def create_user(
    session: AsyncSession,
    email: str,
    role: UserRole = UserRole.OPERATOR,
    is_active: bool = True,
) -> User:
    user = User(
        email=email,
        name=email.split("@")[0].title(),
        hashed_password=get_password_hash(TEST_PASSWORD),
        role=role,
        is_active=is_active,
    )
    session.add(user)
    await session.commit()
    return user


def bearer(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


@pytest.fixture
async def operator_user(db_session: AsyncSession) -> User:
    return await create_user(db_session, "operator@crowdcast.test")


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    return await create_user(db_session, "admin@crowdcast.test", UserRole.ADMIN)


@pytest.fixture
def operator_headers(operator_user: User) -> dict[str, str]:
    return bearer(operator_user)


@pytest.fixture
def admin_headers(admin_user: User) -> dict[str, str]:
    return bearer(admin_user)
