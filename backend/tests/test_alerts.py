from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.main import create_app
from app.models import Alert, AlertKind, Camera, CrowdStatus
from app.services.alerts import Observation, apply_observation

pytestmark = pytest.mark.anyio

KEY = "test-worker-key"
INGEST = "/api/v1/ingest/cameras/CAM-02"
WORKER = {"X-Worker-Key": KEY}
T0 = datetime(2026, 11, 27, 14, 0, tzinfo=timezone.utc)


def at(minute: int) -> datetime:
    return T0 + timedelta(minutes=minute)


def record(minute: int, count: int, status: str) -> dict:
    return {"timestamp": at(minute).isoformat(), "people_count": count, "crowd_status": status}


def forecast(minute: int, horizon: int, count: int, status: str) -> dict:
    return {
        "timestamp": at(minute).isoformat(),
        "horizon_minutes": horizon,
        "predicted_count": count,
        "predicted_status": status,
        "model_name": "linear",
    }


@pytest.fixture
def worker_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("WORKER_API_KEY", KEY)
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


@pytest.fixture
async def camera(db_session: AsyncSession) -> Camera:
    camera = Camera(
        code="CAM-02", name="Kabukicho", location="Kabukicho", source="v.mp4",
        threshold_normal=4, threshold_ramai=12,
    )
    db_session.add(camera)
    await db_session.commit()
    return camera


async def stored_alerts(session: AsyncSession) -> list[Alert]:
    session.expire_all()
    return list((await session.scalars(select(Alert).order_by(Alert.id))).all())


def test_apply_observation_ignores_older_observations() -> None:
    alert, _ = apply_observation(
        None, Observation(at(5), 13, CrowdStatus.RAMAI), 1, AlertKind.CROWDED, None
    )
    assert alert is not None
    same, changed = apply_observation(
        alert, Observation(at(4), 3, CrowdStatus.SEPI), 1, AlertKind.CROWDED, None
    )
    assert same is alert and not changed and alert.ended_at is None


def test_apply_observation_does_nothing_without_crowd() -> None:
    assert apply_observation(
        None, Observation(at(0), 2, CrowdStatus.NORMAL), 1, AlertKind.CROWDED, None
    ) == (None, False)


async def test_ramai_records_open_one_alert_and_normal_closes_it(
    worker_client: TestClient, db_session: AsyncSession, camera: Camera
) -> None:
    first = {"records": [record(0, 8, "Normal"), record(1, 13, "Ramai")]}
    assert worker_client.post(f"{INGEST}/records", headers=WORKER, json=first).status_code == 200
    again = {"records": [record(2, 17, "Ramai"), record(3, 14, "Ramai")]}
    worker_client.post(f"{INGEST}/records", headers=WORKER, json=again)

    [alert] = await stored_alerts(db_session)
    assert (alert.kind, alert.horizon_minutes) == (AlertKind.CROWDED, None)
    assert (alert.started_at, alert.last_seen_at, alert.peak_count) == (at(1), at(3), 17)
    assert alert.ended_at is None

    worker_client.post(f"{INGEST}/records", headers=WORKER, json={"records": [record(4, 9, "Normal")]})
    [alert] = await stored_alerts(db_session)
    assert alert.ended_at == at(4)


async def test_retried_records_do_not_duplicate_or_close(
    worker_client: TestClient, db_session: AsyncSession, camera: Camera
) -> None:
    body = {"records": [record(0, 13, "Ramai")]}
    worker_client.post(f"{INGEST}/records", headers=WORKER, json=body)
    worker_client.post(f"{INGEST}/records", headers=WORKER, json=body)
    worker_client.post(f"{INGEST}/records", headers=WORKER, json={"records": [record(0, 9, "Normal")]})

    [alert] = await stored_alerts(db_session)
    assert alert.ended_at is None


async def test_new_crowd_after_close_opens_second_alert_in_one_batch(
    worker_client: TestClient, db_session: AsyncSession, camera: Camera
) -> None:
    body = {"records": [record(0, 13, "Ramai"), record(1, 5, "Normal"), record(2, 15, "Ramai")]}
    worker_client.post(f"{INGEST}/records", headers=WORKER, json=body)

    first, second = await stored_alerts(db_session)
    assert first.ended_at == at(1)
    assert (second.started_at, second.ended_at) == (at(2), None)


async def test_forecast_alerts_are_tracked_per_horizon(
    worker_client: TestClient, db_session: AsyncSession, camera: Camera
) -> None:
    body = {"predictions": [
        forecast(0, 5, 9, "Normal"), forecast(0, 15, 13, "Ramai"), forecast(0, 30, 16, "Ramai"),
    ]}
    worker_client.post(f"{INGEST}/predictions", headers=WORKER, json=body)
    worker_client.post(f"{INGEST}/predictions", headers=WORKER, json={"predictions": [
        forecast(1, 15, 8, "Normal"), forecast(1, 30, 18, "Ramai"),
    ]})

    alerts = await stored_alerts(db_session)
    assert [(a.kind, a.horizon_minutes, a.ended_at, a.peak_count) for a in alerts] == [
        (AlertKind.FORECAST_CROWDED, 15, at(1), 13),
        (AlertKind.FORECAST_CROWDED, 30, None, 18),
    ]


async def test_list_and_acknowledge_alerts(
    worker_client: TestClient,
    db_session: AsyncSession,
    camera: Camera,
    operator_headers: dict[str, str],
) -> None:
    worker_client.post(f"{INGEST}/records", headers=WORKER, json={"records": [
        record(0, 13, "Ramai"), record(1, 5, "Normal"), record(2, 14, "Ramai"),
    ]})
    worker_client.post(f"{INGEST}/predictions", headers=WORKER, json={"predictions": [
        forecast(3, 15, 20, "Ramai"),
    ]})

    response = worker_client.get("/api/v1/alerts", headers=operator_headers)
    assert response.status_code == 200
    body = response.json()
    assert [a["kind"] for a in body] == ["forecast_crowded", "crowded", "crowded"]
    assert body[0]["target_time"] == "2026-11-27T21:18:00+07:00"
    newest = body[1]
    assert newest["camera_id"] == "CAM-02"
    assert newest["is_active"] is True
    assert newest["started_at"] == "2026-11-27T21:02:00+07:00"
    assert newest["target_time"] is None
    assert body[2]["is_active"] is False

    active = worker_client.get(
        "/api/v1/alerts", headers=operator_headers, params={"active": "true", "camera_id": "CAM-02"}
    ).json()
    assert len(active) == 2

    ack = worker_client.post(f"/api/v1/alerts/{newest['id']}/ack", headers=operator_headers)
    assert ack.status_code == 200
    assert ack.json()["acknowledged_by"] == "Operator"
    first_ack_time = ack.json()["acknowledged_at"]
    again = worker_client.post(f"/api/v1/alerts/{newest['id']}/ack", headers=operator_headers)
    assert again.json()["acknowledged_at"] == first_ack_time


async def test_alert_errors(
    worker_client: TestClient, camera: Camera, operator_headers: dict[str, str]
) -> None:
    assert worker_client.get("/api/v1/alerts").status_code == 401
    missing = worker_client.post("/api/v1/alerts/999/ack", headers=operator_headers)
    assert (missing.status_code, missing.json()["detail"]) == (404, "alert_not_found")
    unknown = worker_client.get("/api/v1/alerts", headers=operator_headers, params={"camera_id": "CAM-99"})
    assert unknown.json()["detail"] == "camera_not_found"
    naive = worker_client.get(
        "/api/v1/alerts", headers=operator_headers, params={"start": "2026-11-27T10:00:00"}
    )
    assert naive.status_code == 422
