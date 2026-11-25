from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, mask_source
from app.models import User, UserRole
from tests.conftest import TEST_PASSWORD, bearer, create_user

pytestmark = pytest.mark.anyio

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"


def login(client: TestClient, email: str, password: str = TEST_PASSWORD):
    return client.post(LOGIN, data={"username": email, "password": password})


async def test_login_returns_bearer_token_usable_for_me(
    client: TestClient, operator_user: User
) -> None:
    response = login(client, "OPERATOR@crowdcast.test")  # email is case-insensitive

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60 == 8 * 3600

    me = client.get(ME, headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json() == {
        "id": operator_user.id,
        "email": "operator@crowdcast.test",
        "name": "Operator",
        "role": "operator",
        "is_active": True,
    }


async def test_login_failures_share_one_error(
    client: TestClient, db_session: AsyncSession, operator_user: User
) -> None:
    await create_user(db_session, "nonaktif@crowdcast.test", is_active=False)
    attempts = [
        ("operator@crowdcast.test", "salah-password"),
        ("tidak-ada@crowdcast.test", TEST_PASSWORD),
        ("nonaktif@crowdcast.test", TEST_PASSWORD),
    ]
    for email, password in attempts:
        response = login(client, email, password)
        assert response.status_code == 401
        assert response.json() == {"detail": "invalid_credentials"}


async def test_expired_token_is_rejected(client: TestClient, operator_user: User) -> None:
    token = create_access_token(operator_user.id, expires_delta=timedelta(seconds=-1))
    response = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert (response.status_code, response.json()) == (401, {"detail": "invalid_token"})


async def test_token_for_unknown_user_is_rejected(client: TestClient) -> None:
    token = create_access_token(999_999)
    response = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert (response.status_code, response.json()) == (401, {"detail": "invalid_token"})


async def test_deactivation_revokes_existing_token(
    client: TestClient, db_session: AsyncSession, operator_user: User
) -> None:
    headers = bearer(operator_user)
    assert client.get(ME, headers=headers).status_code == 200

    operator_user.is_active = False
    await db_session.commit()

    assert client.get(ME, headers=headers).status_code == 401


async def test_role_is_read_from_database_not_token(
    client: TestClient, db_session: AsyncSession, operator_user: User
) -> None:
    # A token that claims admin does not grant admin rights.
    forged = create_access_token(operator_user.id, role=UserRole.ADMIN.value)
    response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {forged}"})
    assert (response.status_code, response.json()) == (403, {"detail": "forbidden"})


@pytest.mark.parametrize(
    ("source", "masked"),
    [
        ("rtsp://admin:p@ss@10.0.0.5:554/s1", "rtsp://admin:***@10.0.0.5:554/s1"),
        ("rtsp://10.0.0.5/stream", "rtsp://10.0.0.5/stream"),
        ("data/videos/sample.mp4", "data/videos/sample.mp4"),
    ],
)
def test_mask_source_hides_only_passwords(source: str, masked: str) -> None:
    assert mask_source(source) == masked
