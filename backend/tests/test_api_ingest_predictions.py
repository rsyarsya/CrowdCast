from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.main import create_app
from app.models import Camera, CrowdRecord, CrowdStatus, Prediction

pytestmark = pytest.mark.anyio

KEY = "test-worker-key"
INGEST = "/api/v1/ingest/cameras/CAM-02"
AUTH = {"X-Worker-Key": KEY}
T0 = datetime(2026, 11, 25, 16, 0, tzinfo=timezone.utc)


@pytest.fixture
def worker_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("WORKER_API_KEY", KEY)
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


async def add_camera_with_records(session: AsyncSession, counts: list[int]) -> Camera:
    camera = Camera(
        code="CAM-02", name="Kabukicho", location="Kabukicho", source="v.mp4",
        threshold_normal=4, threshold_ramai=12,
    )
    session.add(camera)
    await session.flush()
    for minute, count in enumerate(counts):
        session.add(CrowdRecord(camera_id=camera.id, timestamp=T0 + timedelta(minutes=minute),
                                people_count=count, crowd_status=CrowdStatus.NORMAL))
    await session.commit()
    return camera


def prediction(horizon: int, count: int, model: str = "moving_average_5") -> dict:
    return {
        "timestamp": "2026-11-25T23:10:00+07:00",
        "horizon_minutes": horizon,
        "predicted_count": count,
        "predicted_status": "Normal",
        "model_name": model,
    }


async def test_recent_records_returns_latest_in_ascending_order(
    worker_client: TestClient, db_session: AsyncSession
) -> None:
    await add_camera_with_records(db_session, [1, 2, 3, 4, 5])
    response = worker_client.get(f"{INGEST}/records/recent", headers=AUTH, params={"limit": 3})
    assert response.status_code == 200
    assert [r["people_count"] for r in response.json()] == [3, 4, 5]


async def test_recent_records_requires_worker_key(worker_client: TestClient) -> None:
    assert worker_client.get(f"{INGEST}/records/recent").status_code == 401


async def test_predictions_are_idempotent_and_served_as_latest(
    worker_client: TestClient, db_session: AsyncSession
) -> None:
    await add_camera_with_records(db_session, [5])
    body = {"predictions": [prediction(5, 6), prediction(15, 7), prediction(30, 8)]}
    assert worker_client.post(f"{INGEST}/predictions", headers=AUTH, json=body).json() == {"received": 3}
    retry = {"predictions": [prediction(5, 9)]}
    assert worker_client.post(f"{INGEST}/predictions", headers=AUTH, json=retry).status_code == 200

    assert await db_session.scalar(select(func.count()).select_from(Prediction)) == 3
    stored = (
        await db_session.execute(
            select(Prediction.horizon_minutes, Prediction.predicted_count, Prediction.is_simulation)
            .order_by(Prediction.horizon_minutes)
        )
    ).all()
    assert stored == [(5, 9, False), (15, 7, False), (30, 8, False)]


@pytest.mark.parametrize(
    "bad",
    [
        {"predictions": []},
        {"predictions": [{**prediction(5, 1), "horizon_minutes": 0}]},
        {"predictions": [{**prediction(5, 1), "predicted_count": -1}]},
        {"predictions": [{**prediction(5, 1), "timestamp": "2026-11-25T23:10:00"}]},
    ],
)
async def test_predictions_validation(
    worker_client: TestClient, db_session: AsyncSession, bad: dict
) -> None:
    await add_camera_with_records(db_session, [])
    assert worker_client.post(f"{INGEST}/predictions", headers=AUTH, json=bad).status_code == 422
