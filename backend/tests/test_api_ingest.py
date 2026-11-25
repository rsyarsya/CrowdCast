import asyncio
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.main import create_app
from app.models import Camera, CrowdRecord, CrowdStatus
from app.services.live import LiveHub

pytestmark = pytest.mark.anyio

KEY = "test-worker-key"
INGEST = "/api/v1/ingest/cameras"
API = "/api/v1/cameras"
AUTH = {"X-Worker-Key": KEY}


@pytest.fixture
def worker_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("WORKER_API_KEY", KEY)
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


async def add_camera(session: AsyncSession) -> Camera:
    camera = Camera(
        code="CAM-02",
        name="Kabukicho",
        location="Kabukicho, Tokyo",
        source="data/videos/kabukicho.mp4",
        threshold_normal=4,
        threshold_ramai=8,
        roi=[[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]],
    )
    session.add(camera)
    await session.commit()
    return camera


def record(minute: int, count: int, status: str = "Normal") -> dict:
    return {
        "timestamp": f"2026-11-25T23:{minute:02d}:00+07:00",
        "people_count": count,
        "crowd_status": status,
    }


async def test_ingest_disabled_without_configured_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An empty environment variable overrides any key set in backend/.env.
    monkeypatch.setenv("WORKER_API_KEY", "")
    get_settings.cache_clear()
    response = client.get(f"{INGEST}/CAM-02/config", headers=AUTH)
    assert (response.status_code, response.json()) == (503, {"detail": "ingest_disabled"})


@pytest.mark.parametrize("headers", [{}, {"X-Worker-Key": "wrong"}])
async def test_ingest_rejects_missing_or_wrong_key(
    worker_client: TestClient, headers: dict
) -> None:
    # The key check runs before the camera lookup, so unknown cameras are not revealed.
    response = worker_client.get(f"{INGEST}/CAM-99/config", headers=headers)
    assert (response.status_code, response.json()) == (401, {"detail": "invalid_worker_key"})


async def test_worker_config_includes_source_and_roi(
    worker_client: TestClient, db_session: AsyncSession
) -> None:
    await add_camera(db_session)
    response = worker_client.get(f"{INGEST}/CAM-02/config", headers=AUTH)
    assert response.status_code == 200
    assert response.json() == {
        "camera_id": "CAM-02",
        "source": "data/videos/kabukicho.mp4",
        "roi": [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]],
        "threshold_normal": 4,
        "threshold_ramai": 8,
    }


async def test_records_upsert_is_idempotent(
    worker_client: TestClient, db_session: AsyncSession
) -> None:
    await add_camera(db_session)
    first = worker_client.post(
        f"{INGEST}/CAM-02/records", headers=AUTH, json={"records": [record(0, 3, "Sepi"), record(1, 5)]}
    )
    retry = worker_client.post(
        f"{INGEST}/CAM-02/records", headers=AUTH, json={"records": [record(1, 9, "Ramai")]}
    )
    assert first.json() == {"received": 2}
    assert retry.status_code == 200

    rows = (await db_session.scalars(select(CrowdRecord).order_by(CrowdRecord.timestamp))).all()
    assert [(r.people_count, r.crowd_status) for r in rows] == [
        (3, CrowdStatus.SEPI),
        (9, CrowdStatus.RAMAI),
    ]
    latest = worker_client.get(f"{API}/CAM-02/monitoring/latest").json()
    assert latest["timestamp"] == "2026-11-25T23:01:00+07:00"


@pytest.mark.parametrize(
    "bad",
    [
        {"records": []},
        {"records": [{**record(0, 3), "people_count": -1}]},
        {"records": [{**record(0, 3), "timestamp": "2026-11-25T23:00:00"}]},
        {"records": [{**record(0, 3), "crowd_status": "Padat"}]},
    ],
)
async def test_records_validation(
    worker_client: TestClient, db_session: AsyncSession, bad: dict
) -> None:
    await add_camera(db_session)
    response = worker_client.post(f"{INGEST}/CAM-02/records", headers=AUTH, json=bad)
    assert response.status_code == 422


async def test_live_state_roundtrip_and_staleness(
    worker_client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await add_camera(db_session)
    assert worker_client.get(f"{API}/CAM-02/live").json() == {"detail": "no_live_data"}

    sent = worker_client.put(
        f"{INGEST}/CAM-02/live",
        headers=AUTH,
        json={
            "timestamp": "2026-11-25T16:00:05Z",
            "raw_count": 7,
            "smoothed_count": 6.5,
            "crowd_status": "Normal",
        },
    )
    assert sent.status_code == 200

    live = worker_client.get(f"{API}/CAM-02/live")
    assert live.status_code == 200
    assert live.json() == {
        "camera_id": "CAM-02",
        "timestamp": "2026-11-25T23:00:05+07:00",
        "people_count": 7,
        "smoothed_count": 6.5,
        "crowd_status": "Normal",
        "is_stale": False,
    }

    monkeypatch.setenv("LIVE_STALE_SECONDS", "-1")
    get_settings.cache_clear()
    assert worker_client.get(f"{API}/CAM-02/live").json()["is_stale"] is True


async def test_frame_upload_and_stream_not_found(
    worker_client: TestClient, db_session: AsyncSession
) -> None:
    await add_camera(db_session)
    assert worker_client.get(f"{API}/CAM-02/stream").json() == {"detail": "no_stream"}

    wrong_type = worker_client.put(
        f"{INGEST}/CAM-02/frame", headers={**AUTH, "Content-Type": "image/png"}, content=b"x"
    )
    assert wrong_type.status_code == 415
    empty = worker_client.put(
        f"{INGEST}/CAM-02/frame", headers={**AUTH, "Content-Type": "image/jpeg"}, content=b""
    )
    assert empty.status_code == 413
    ok = worker_client.put(
        f"{INGEST}/CAM-02/frame", headers={**AUTH, "Content-Type": "image/jpeg"}, content=b"\xff\xd8jpeg"
    )
    assert ok.status_code == 204
    assert worker_client.app.state.live_hub.has_frame("CAM-02")


async def test_hub_streams_current_then_new_frames() -> None:
    hub = LiveHub()
    await hub.publish_frame("CAM-02", b"one")
    frames = hub.frames("CAM-02", timeout=1)

    assert await anext(frames) == b"one"
    waiting = asyncio.create_task(anext(frames))
    await asyncio.sleep(0.01)
    assert not waiting.done()  # waits for a new frame instead of busy-looping
    await hub.publish_frame("CAM-02", b"two")
    assert await asyncio.wait_for(waiting, 1) == b"two"
    await frames.aclose()


async def test_hub_resends_last_frame_after_timeout() -> None:
    hub = LiveHub()
    await hub.publish_frame("CAM-02", b"one")
    frames = hub.frames("CAM-02", timeout=0.05)
    assert await anext(frames) == b"one"
    assert await asyncio.wait_for(anext(frames), 1) == b"one"
    await frames.aclose()


async def test_hub_live_state() -> None:
    hub = LiveHub()
    assert hub.get_live("CAM-02") is None
    ts = datetime(2026, 11, 25, 16, 0, tzinfo=timezone.utc)
    hub.set_live("CAM-02", ts, 3, 3.0, CrowdStatus.SEPI)
    assert hub.get_live("CAM-02").raw_count == 3
