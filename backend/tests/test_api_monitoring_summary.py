from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Camera, CrowdRecord, CrowdStatus

pytestmark = pytest.mark.anyio

URL = "/api/v1/cameras/CAM-02/monitoring/summary"
WIB_MIDNIGHT = datetime(2026, 11, 26, 17, 0, tzinfo=timezone.utc)


async def add_records(session: AsyncSession, rows: list[tuple[int, int, CrowdStatus]]) -> None:
    camera = Camera(
        code="CAM-02", name="Kabukicho", location="Kabukicho", source="v.mp4",
        threshold_normal=4, threshold_ramai=12,
    )
    session.add(camera)
    await session.flush()
    session.add_all(
        CrowdRecord(
            camera_id=camera.id,
            timestamp=WIB_MIDNIGHT + timedelta(minutes=minute),
            people_count=count,
            crowd_status=status,
        )
        for minute, count, status in rows
    )
    await session.commit()


async def test_summary_groups_records_per_bucket(
    client: TestClient, db_session: AsyncSession, operator_headers: dict[str, str]
) -> None:
    await add_records(db_session, [
        (0, 2, CrowdStatus.SEPI),
        (5, 6, CrowdStatus.NORMAL),
        (10, 13, CrowdStatus.RAMAI),
        (14, 3, CrowdStatus.SEPI),
        (15, 14, CrowdStatus.RAMAI),
        (75, 5, CrowdStatus.NORMAL),
    ])
    response = client.get(URL, headers=operator_headers, params={
        "bucket": "15m",
        "start": "2026-11-27T00:00:00+07:00",
        "end": "2026-11-27T02:00:00+07:00",
    })
    assert response.status_code == 200
    body = response.json()
    assert (body["camera_id"], body["bucket"]) == ("CAM-02", "15m")
    assert body["start"] == "2026-11-27T00:00:00+07:00"
    first, second, third = body["points"]
    assert first == {
        "bucket_start": "2026-11-27T00:00:00+07:00",
        "avg_count": 6.0,
        "min_count": 2,
        "max_count": 13,
        "records": 4,
        "status_counts": {"Sepi": 2, "Normal": 1, "Ramai": 1},
        "crowd_status": "Sepi",
    }
    assert (second["bucket_start"], second["crowd_status"]) == ("2026-11-27T00:15:00+07:00", "Ramai")
    assert third["bucket_start"] == "2026-11-27T01:15:00+07:00"


async def test_daily_buckets_align_to_local_midnight_and_ties_go_busier(
    client: TestClient, db_session: AsyncSession, operator_headers: dict[str, str]
) -> None:
    await add_records(db_session, [
        (-60, 1, CrowdStatus.SEPI),
        (0, 4, CrowdStatus.NORMAL),
        (30, 13, CrowdStatus.RAMAI),
    ])
    body = client.get(URL, headers=operator_headers, params={
        "bucket": "1d",
        "start": "2026-11-26T00:00:00+07:00",
        "end": "2026-11-28T00:00:00+07:00",
    }).json()
    assert [(p["bucket_start"], p["records"], p["crowd_status"]) for p in body["points"]] == [
        ("2026-11-26T00:00:00+07:00", 1, "Sepi"),
        ("2026-11-27T00:00:00+07:00", 2, "Ramai"),
    ]


async def test_summary_defaults_to_last_24_hours(
    client: TestClient, db_session: AsyncSession, operator_headers: dict[str, str]
) -> None:
    await add_records(db_session, [])
    body = client.get(URL, headers=operator_headers).json()
    start = datetime.fromisoformat(body["start"])
    end = datetime.fromisoformat(body["end"])
    assert (end - start, body["bucket"], body["points"]) == (timedelta(hours=24), "15m", [])


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        ({"start": "2026-11-27T02:00:00+07:00", "end": "2026-11-27T01:00:00+07:00"}, "start must be before end"),
        ({"bucket": "5m", "start": "2026-01-01T00:00:00+07:00", "end": "2026-11-27T00:00:00+07:00"}, "too_many_buckets"),
        ({"start": "2026-11-27T00:00:00"}, "start must include a timezone offset"),
    ],
)
async def test_summary_validation(
    client: TestClient,
    db_session: AsyncSession,
    operator_headers: dict[str, str],
    params: dict,
    detail: str,
) -> None:
    await add_records(db_session, [])
    response = client.get(URL, headers=operator_headers, params=params)
    assert (response.status_code, response.json()["detail"]) == (422, detail)


async def test_summary_rejects_unknown_bucket_and_requires_login(
    client: TestClient, db_session: AsyncSession, operator_headers: dict[str, str]
) -> None:
    await add_records(db_session, [])
    assert client.get(URL, headers=operator_headers, params={"bucket": "2h"}).status_code == 422
    assert client.get(URL).status_code == 401
    missing = client.get("/api/v1/cameras/CAM-99/monitoring/summary", headers=operator_headers)
    assert missing.json()["detail"] == "camera_not_found"
