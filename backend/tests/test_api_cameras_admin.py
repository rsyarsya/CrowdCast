import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Camera

pytestmark = pytest.mark.anyio

CAMERAS = "/api/v1/cameras"
RTSP = "rtsp://admin:rahasia@192.168.1.20:554/stream1"
NEW_CAMERA = {
    "camera_id": "CAM-02",
    "name": "Kamera Kantin",
    "location": "Kantin Gedung B",
    "source": RTSP,
    "threshold_normal": 5,
    "threshold_ramai": 15,
    "roi": [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]],
}


async def test_operator_cannot_manage_cameras(
    client: TestClient, operator_headers: dict[str, str]
) -> None:
    requests = [
        ("POST", CAMERAS),
        ("PATCH", f"{CAMERAS}/CAM-01"),
        ("GET", f"{CAMERAS}/CAM-01/config"),
    ]
    for method, path in requests:
        response = client.request(method, path, headers=operator_headers, json=NEW_CAMERA)
        assert (response.status_code, response.json()) == (403, {"detail": "forbidden"})


async def test_admin_creates_camera_with_masked_source(
    client: TestClient, db_session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    created = client.post(CAMERAS, headers=admin_headers, json=NEW_CAMERA)

    assert created.status_code == 201
    body = created.json()
    assert body["source"] == "rtsp://admin:***@192.168.1.20:554/stream1"
    assert "rahasia" not in created.text
    assert body["roi"] == NEW_CAMERA["roi"]

    # The real credentials are stored for the worker.
    stored = await db_session.get(Camera, 1)
    assert stored is not None and stored.source == RTSP

    config = client.get(f"{CAMERAS}/CAM-02/config", headers=admin_headers)
    assert config.json() == body

    public = client.get(CAMERAS, headers=admin_headers).json()
    assert public == [
        {
            "camera_id": "CAM-02",
            "name": "Kamera Kantin",
            "location": "Kantin Gedung B",
            "is_active": True,
        }
    ]


async def test_duplicate_camera_code_conflicts(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    assert client.post(CAMERAS, headers=admin_headers, json=NEW_CAMERA).status_code == 201
    again = client.post(CAMERAS, headers=admin_headers, json=NEW_CAMERA)
    assert (again.status_code, again.json()) == (409, {"detail": "camera_code_exists"})


@pytest.mark.parametrize(
    "change",
    [
        {"camera_id": "cam 02"},
        {"threshold_normal": 15, "threshold_ramai": 5},
        {"threshold_normal": 0},
        {"roi": [[0.1, 0.1], [0.9, 0.1]]},
        {"roi": [[0.1, 0.1], [1.5, 0.1], [0.5, 0.9]]},
    ],
)
async def test_invalid_camera_payload(
    client: TestClient, admin_headers: dict[str, str], change: dict
) -> None:
    response = client.post(CAMERAS, headers=admin_headers, json={**NEW_CAMERA, **change})
    assert response.status_code == 422


async def test_admin_updates_and_deactivates_camera(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    client.post(CAMERAS, headers=admin_headers, json=NEW_CAMERA)

    updated = client.patch(
        f"{CAMERAS}/CAM-02",
        headers=admin_headers,
        json={"threshold_ramai": 20, "roi": None, "is_active": False},
    )

    assert updated.status_code == 200
    body = updated.json()
    assert (body["threshold_ramai"], body["roi"], body["is_active"]) == (20, None, False)
    # History endpoints still work for a deactivated camera.
    history = client.get(f"{CAMERAS}/CAM-02/monitoring", headers=admin_headers)
    assert history.status_code == 200


async def test_update_rejects_threshold_order_against_stored_value(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    client.post(CAMERAS, headers=admin_headers, json=NEW_CAMERA)

    response = client.patch(
        f"{CAMERAS}/CAM-02", headers=admin_headers, json={"threshold_normal": 15}
    )

    assert (response.status_code, response.json()) == (422, {"detail": "invalid_thresholds"})
    config = client.get(f"{CAMERAS}/CAM-02/config", headers=admin_headers).json()
    assert config["threshold_normal"] == 5


async def test_unknown_camera_returns_404(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.patch(f"{CAMERAS}/CAM-99", headers=admin_headers, json={"name": "X"})
    assert (response.status_code, response.json()) == (404, {"detail": "camera_not_found"})
