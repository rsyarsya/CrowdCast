import asyncio
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_ticket
from app.main import create_app
from app.models import Camera, User
from app.services.live import ALERTS_TOPIC, Event, LiveHub
from tests.conftest import bearer

pytestmark = pytest.mark.anyio

KEY = "test-worker-key"
WORKER = {"X-Worker-Key": KEY}
INGEST = "/api/v1/ingest/cameras/CAM-02"
API = "/api/v1"


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


def drain(queue: asyncio.Queue[Event]) -> list[Event]:
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


async def test_ticket_opens_stream_route_without_header(
    worker_client: TestClient, camera: Camera, operator_headers: dict[str, str]
) -> None:
    issued = worker_client.post(f"{API}/cameras/CAM-02/ticket", headers=operator_headers)
    assert issued.status_code == 200
    assert issued.json()["expires_in"] == 60

    response = worker_client.get(
        f"{API}/cameras/CAM-02/stream", params={"ticket": issued.json()["ticket"]}
    )
    assert response.json() == {"detail": "no_stream"}


async def test_ticket_rejections(
    worker_client: TestClient,
    db_session: AsyncSession,
    camera: Camera,
    operator_user: User,
    operator_headers: dict[str, str],
) -> None:
    db_session.add(Camera(
        code="CAM-03", name="Lain", location="Lain", source="w.mp4",
        threshold_normal=1, threshold_ramai=2,
    ))
    await db_session.commit()
    other = worker_client.post(f"{API}/cameras/CAM-03/ticket", headers=operator_headers).json()
    alerts = worker_client.post(f"{API}/alerts/ticket", headers=operator_headers).json()

    def stream(**kwargs: object) -> dict:
        return worker_client.get(f"{API}/cameras/CAM-02/stream", **kwargs).json()

    assert stream() == {"detail": "not_authenticated"}
    assert stream(params={"ticket": other["ticket"]}) == {"detail": "invalid_ticket"}
    assert stream(params={"ticket": alerts["ticket"]}) == {"detail": "invalid_ticket"}
    assert stream(params={"ticket": "garbage"}) == {"detail": "invalid_ticket"}
    as_bearer = worker_client.get(
        f"{API}/cameras", headers={"Authorization": f"Bearer {other['ticket']}"}
    )
    assert as_bearer.json() == {"detail": "invalid_token"}

    operator_user.is_active = False
    await db_session.commit()
    stale = create_ticket(operator_user.id, "camera:CAM-02")
    assert stream(params={"ticket": stale}) == {"detail": "invalid_token"}


async def test_expired_ticket_is_rejected(
    worker_client: TestClient,
    camera: Camera,
    operator_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STREAM_TICKET_SECONDS", "-1")
    get_settings.cache_clear()
    expired = create_ticket(operator_user.id, "camera:CAM-02")
    response = worker_client.get(f"{API}/cameras/CAM-02/events", params={"ticket": expired})
    assert response.json() == {"detail": "invalid_ticket"}


async def test_event_routes_require_login(worker_client: TestClient, camera: Camera) -> None:
    assert worker_client.get(f"{API}/cameras/CAM-02/events").status_code == 401
    assert worker_client.get(f"{API}/alerts/events").status_code == 401
    assert worker_client.post(f"{API}/alerts/ticket").status_code == 401


async def test_hub_event_stream_sends_initial_events_heartbeat_and_published() -> None:
    hub = LiveHub()
    stream = hub.event_stream("CAM-02", [Event("live", '{"a":1}')], heartbeat=0.05)
    assert await anext(stream) == 'event: live\ndata: {"a":1}\n\n'
    assert hub.subscriber_count("CAM-02") == 1
    assert await anext(stream) == ": ping\n\n"
    hub.publish("CAM-02", "record", "{}")
    hub.publish("CAM-03", "record", "{}")
    assert await anext(stream) == "event: record\ndata: {}\n\n"
    await stream.aclose()
    assert hub.subscriber_count("CAM-02") == 0


async def test_slow_subscriber_drops_oldest_events() -> None:
    hub = LiveHub()
    async with hub.subscribe("CAM-02") as queue:
        for i in range(150):
            hub.publish("CAM-02", "live", str(i))
        events = drain(queue)
    assert len(events) == 100
    assert events[0].data == "50"


async def test_ingest_publishes_live_record_prediction_and_alert_events(
    worker_client: TestClient, camera: Camera, operator_user: User
) -> None:
    hub: LiveHub = worker_client.app.state.live_hub
    async with hub.subscribe("CAM-02") as queue, hub.subscribe(ALERTS_TOPIC) as alert_queue:
        now = datetime(2026, 11, 27, 15, 0, tzinfo=timezone.utc).isoformat()
        worker_client.put(f"{INGEST}/live", headers=WORKER, json={
            "timestamp": now, "raw_count": 14, "smoothed_count": 13.5, "crowd_status": "Ramai",
        })
        worker_client.post(f"{INGEST}/records", headers=WORKER, json={"records": [
            {"timestamp": now, "people_count": 14, "crowd_status": "Ramai"},
        ]})
        worker_client.post(f"{INGEST}/predictions", headers=WORKER, json={"predictions": [
            {"timestamp": now, "horizon_minutes": h, "predicted_count": 9,
             "predicted_status": "Normal", "model_name": "linear"}
            for h in (30, 5, 15)
        ]})
        events = drain(queue)
        global_alerts = drain(alert_queue)

        assert [e.name for e in events] == ["live", "record", "alert", "prediction"]
        assert '"people_count":14' in events[1].data
        assert '"kind":"crowded"' in events[2].data
        assert '"horizon_minutes":5' in events[3].data.split("},")[0]
        assert [e.name for e in global_alerts] == ["alert"]

        alert_id = int(events[2].data.split('"id":')[1].split(",")[0])
        worker_client.post(f"{API}/alerts/{alert_id}/ack", headers=bearer(operator_user))
        worker_client.post(f"{API}/alerts/{alert_id}/ack", headers=bearer(operator_user))
        acked = drain(queue)
        assert len(acked) == 1 and '"acknowledged_by":"Operator"' in acked[0].data
