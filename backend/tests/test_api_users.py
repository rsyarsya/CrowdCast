import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserRole
from tests.conftest import bearer, create_user

pytestmark = pytest.mark.anyio

USERS = "/api/v1/users"
LOGIN = "/api/v1/auth/login"


async def test_operator_cannot_manage_users(
    client: TestClient, operator_headers: dict[str, str]
) -> None:
    for method, path in (("GET", USERS), ("POST", USERS), ("PATCH", f"{USERS}/1")):
        response = client.request(method, path, headers=operator_headers, json={})
        assert (response.status_code, response.json()) == (403, {"detail": "forbidden"})


async def test_admin_creates_user_who_can_log_in(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    created = client.post(
        USERS,
        headers=admin_headers,
        json={"email": "Budi@Crowdcast.test", "name": "Budi", "password": "operator-123"},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["email"] == "budi@crowdcast.test"
    assert body["role"] == "operator"
    assert "password" not in body and "hashed_password" not in body

    login = client.post(LOGIN, data={"username": "budi@crowdcast.test", "password": "operator-123"})
    assert login.status_code == 200

    listed = client.get(USERS, headers=admin_headers).json()
    assert [u["email"] for u in listed] == ["admin@crowdcast.test", "budi@crowdcast.test"]


async def test_duplicate_email_conflicts(
    client: TestClient, admin_headers: dict[str, str], operator_user: User
) -> None:
    response = client.post(
        USERS,
        headers=admin_headers,
        json={"email": "OPERATOR@crowdcast.test", "name": "Dup", "password": "operator-123"},
    )
    assert (response.status_code, response.json()) == (409, {"detail": "email_already_exists"})


@pytest.mark.parametrize(
    "body",
    [
        {"email": "bukan-email", "name": "X", "password": "operator-123"},
        {"email": "x@crowdcast.test", "name": "X", "password": "pendek"},
        {"email": "x@crowdcast.test", "name": "X", "password": "operator-123", "role": "root"},
    ],
)
async def test_invalid_user_payload(
    client: TestClient, admin_headers: dict[str, str], body: dict
) -> None:
    assert client.post(USERS, headers=admin_headers, json=body).status_code == 422


async def test_admin_updates_and_deactivates_user(
    client: TestClient, admin_headers: dict[str, str], operator_user: User
) -> None:
    updated = client.patch(
        f"{USERS}/{operator_user.id}",
        headers=admin_headers,
        json={"name": "Operator Shift Pagi", "password": "password-baru"},
    )
    assert updated.json()["name"] == "Operator Shift Pagi"
    login = client.post(
        LOGIN, data={"username": "operator@crowdcast.test", "password": "password-baru"}
    )
    assert login.status_code == 200

    deactivated = client.patch(
        f"{USERS}/{operator_user.id}", headers=admin_headers, json={"is_active": False}
    )
    assert deactivated.json()["is_active"] is False
    assert client.get("/api/v1/auth/me", headers=bearer(operator_user)).status_code == 401


async def test_admin_cannot_lock_out_themselves(
    client: TestClient, db_session: AsyncSession, admin_user: User, admin_headers: dict[str, str]
) -> None:
    await create_user(db_session, "admin2@crowdcast.test", UserRole.ADMIN)
    for change in ({"is_active": False}, {"role": "operator"}):
        response = client.patch(f"{USERS}/{admin_user.id}", headers=admin_headers, json=change)
        assert (response.status_code, response.json()) == (422, {"detail": "cannot_modify_self"})


async def test_admin_manages_another_admin(
    client: TestClient, db_session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    other = await create_user(db_session, "admin2@crowdcast.test", UserRole.ADMIN)
    response = client.patch(f"{USERS}/{other.id}", headers=admin_headers, json={"role": "operator"})
    assert response.json()["role"] == "operator"
    assert client.get(USERS, headers=bearer(other)).status_code == 403


async def test_unknown_user_returns_404(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.patch(f"{USERS}/999999", headers=admin_headers, json={"name": "X"})
    assert (response.status_code, response.json()) == (404, {"detail": "user_not_found"})
