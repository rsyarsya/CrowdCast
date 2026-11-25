from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Camera, CrowdRecord, CrowdStatus, Prediction

pytestmark = pytest.mark.anyio

API = "/api/v1/cameras"
UTC = timezone.utc
T0 = datetime(2026, 9, 23, 3, 0, tzinfo=UTC)  # 10:00 WIB


@pytest.fixture(autouse=True)
def logged_in(client: TestClient, operator_headers: dict[str, str]) -> None:
    """Monitoring routes need a login; every request here is an operator."""
    client.headers.update(operator_headers)


async def add_camera(session: AsyncSession, code: str = "CAM-01") -> Camera:
    camera = Camera(
        code=code,
        name="Kamera Lobi",
        location="Lobi Gedung A",
        source="rtsp://user:secret@10.0.0.5/stream",
        threshold_normal=10,
        threshold_ramai=30,
    )
    session.add(camera)
    await session.commit()
    return camera


async def add_records(session: AsyncSession, camera: Camera, counts: list[int]) -> None:
    for minute, count in enumerate(counts):
        status = (
            CrowdStatus.RAMAI
            if count >= 30
            else CrowdStatus.NORMAL if count >= 10 else CrowdStatus.SEPI
        )
        session.add(
            CrowdRecord(
                camera_id=camera.id,
                timestamp=T0 + timedelta(minutes=minute),
                people_count=count,
                crowd_status=status,
            )
        )
    await session.commit()


async def test_list_cameras_hides_source(
    client: TestClient, db_session: AsyncSession
) -> None:
    await add_camera(db_session)
    response = client.get(API)
    assert response.status_code == 200
    assert response.json() == [
        {
            "camera_id": "CAM-01",
            "name": "Kamera Lobi",
            "location": "Lobi Gedung A",
            "is_active": True,
        }
    ]
    assert "secret" not in response.text


async def test_latest_monitoring_matches_frontend_contract(
    client: TestClient, db_session: AsyncSession
) -> None:
    camera = await add_camera(db_session)
    await add_records(db_session, camera, [0, 18, 37])

    response = client.get(f"{API}/CAM-01/monitoring/latest")

    assert response.status_code == 200
    assert response.json() == {
        "camera_id": "CAM-01",
        "location": "Lobi Gedung A",
        "timestamp": "2026-09-23T10:02:00+07:00",
        "people_count": 37,
        "crowd_status": "Ramai",
    }


async def test_unknown_camera_returns_camera_not_found(client: TestClient) -> None:
    for path in ("monitoring/latest", "monitoring", "predictions/latest"):
        response = client.get(f"{API}/CAM-99/{path}")
        assert response.status_code == 404
        assert response.json() == {"detail": "camera_not_found"}


async def test_camera_without_data_returns_specific_codes(
    client: TestClient, db_session: AsyncSession
) -> None:
    await add_camera(db_session)

    latest = client.get(f"{API}/CAM-01/monitoring/latest")
    predictions = client.get(f"{API}/CAM-01/predictions/latest")
    history = client.get(f"{API}/CAM-01/monitoring")

    assert (latest.status_code, latest.json()) == (
        404,
        {"detail": "no_monitoring_data"},
    )
    assert (predictions.status_code, predictions.json()) == (
        404,
        {"detail": "no_prediction"},
    )
    assert (history.status_code, history.json()) == (200, [])


async def test_history_filters_range_in_ascending_order(
    client: TestClient, db_session: AsyncSession
) -> None:
    camera = await add_camera(db_session)
    await add_records(db_session, camera, [0, 5, 18, 25, 37])

    response = client.get(
        f"{API}/CAM-01/monitoring",
        params={
            "start": "2026-09-23T10:01:00+07:00",
            "end": "2026-09-23T03:03:00Z",  # same instant as 10:03 WIB
        },
    )

    assert response.status_code == 200
    assert [row["people_count"] for row in response.json()] == [5, 18, 25]


async def test_history_without_start_returns_latest_window(
    client: TestClient, db_session: AsyncSession
) -> None:
    camera = await add_camera(db_session)
    await add_records(db_session, camera, [0, 5, 18, 25, 37])

    response = client.get(f"{API}/CAM-01/monitoring", params={"limit": 2})

    assert [row["people_count"] for row in response.json()] == [25, 37]


@pytest.mark.parametrize(
    ("params", "fragment"),
    [
        (
            {"start": "2026-09-23T10:05:00+07:00", "end": "2026-09-23T10:00:00+07:00"},
            "start must not be after end",
        ),
        ({"start": "2026-09-23T10:00:00"}, "timezone"),
        ({"limit": 0}, "limit"),
        ({"limit": 5000}, "limit"),
    ],
)
async def test_history_rejects_invalid_queries(
    client: TestClient, db_session: AsyncSession, params: dict, fragment: str
) -> None:
    await add_camera(db_session)
    response = client.get(f"{API}/CAM-01/monitoring", params=params)
    assert response.status_code == 422
    assert fragment in response.text


async def test_latest_predictions_one_per_horizon(
    client: TestClient, db_session: AsyncSession
) -> None:
    camera = await add_camera(db_session)
    for made_at, count in ((T0, 10), (T0 + timedelta(minutes=1), 20)):
        for horizon in (30, 5, 15):
            db_session.add(
                Prediction(
                    camera_id=camera.id,
                    timestamp=made_at,
                    horizon_minutes=horizon,
                    predicted_count=count + horizon,
                    predicted_status=CrowdStatus.RAMAI,
                    model_name="moving_average",
                )
            )
    await db_session.commit()

    response = client.get(f"{API}/CAM-01/predictions/latest")

    assert response.status_code == 200
    body = response.json()
    assert [p["horizon_minutes"] for p in body] == [5, 15, 30]
    assert [p["predicted_count"] for p in body] == [25, 35, 50]
    assert body[1] == {
        "camera_id": "CAM-01",
        "timestamp": "2026-09-23T10:01:00+07:00",
        "horizon_minutes": 15,
        "target_time": "2026-09-23T10:16:00+07:00",
        "predicted_count": 35,
        "predicted_status": "Ramai",
        "model_name": "moving_average",
        "is_simulation": False,
    }


@pytest.mark.parametrize(
    ("authorization", "code"),
    [
        (None, "not_authenticated"),
        ("Bearer not-a-jwt", "invalid_token"),
    ],
)
async def test_monitoring_requires_login(
    client: TestClient, db_session: AsyncSession, authorization: str | None, code: str
) -> None:
    await add_camera(db_session)
    del client.headers["Authorization"]
    headers = {"Authorization": authorization} if authorization else {}

    for path in ("", "/CAM-01/monitoring/latest", "/CAM-01/live", "/CAM-01/stream"):
        response = client.get(f"{API}{path}", headers=headers)
        assert response.status_code == 401
        assert response.json() == {"detail": code}
        assert response.headers["www-authenticate"] == "Bearer"
