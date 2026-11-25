from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Camera, CrowdRecord, CrowdStatus
from app.scripts.backfill_records import backfill, read_minutes, shift_to_end
from app.scripts.register_camera import CameraSpec, register_camera
from app.services.vision.roi import Roi

pytestmark = pytest.mark.anyio

SPEC = CameraSpec(
    code="CAM-02",
    name="Kabukicho",
    location="Kabukicho, Shinjuku",
    source="data/videos/kabukicho.mp4",
    threshold_normal=4,
    threshold_ramai=8,
    roi=Roi.from_points([(0.1, 0.1), (0.9, 0.1), (0.5, 0.9)]),
)


async def test_register_camera_creates_then_updates(db_session: AsyncSession) -> None:
    created = await register_camera(db_session, SPEC)
    assert created.roi == [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]]

    updated = await register_camera(
        db_session, CameraSpec(**{**SPEC.__dict__, "threshold_ramai": 10, "roi": None})
    )
    assert (updated.threshold_ramai, updated.roi) == (10, None)
    assert await db_session.scalar(select(func.count()).select_from(Camera)) == 1


def test_camera_spec_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError):
        CameraSpec(**{**SPEC.__dict__, "threshold_normal": 8, "threshold_ramai": 4})


def write_csv(path: Path) -> Path:
    path.write_text(
        "camera_id,timestamp,people_count,n_samples,crowd_status\n"
        "kabukicho,2026-08-25 18:01:00+09:00,9,60,Ramai\n"
        "kabukicho,2026-08-25 18:00:00+09:00,2,60,Sepi\n"
        "kabukicho,2026-08-25 18:02:00+09:00,5,60,Normal\n",
        encoding="utf-8",
    )
    return path


def test_shift_puts_last_row_before_end(tmp_path: Path) -> None:
    rows = read_minutes(write_csv(tmp_path / "minutes.csv"))
    end = datetime(2026, 11, 25, 16, 30, 42, tzinfo=timezone.utc)
    shifted = shift_to_end(rows, end)
    assert [r.timestamp for r in shifted] == [
        datetime(2026, 11, 25, 16, 27, tzinfo=timezone.utc),
        datetime(2026, 11, 25, 16, 28, tzinfo=timezone.utc),
        datetime(2026, 11, 25, 16, 29, tzinfo=timezone.utc),
    ]
    assert [r.people_count for r in shifted] == [2, 9, 5]


async def test_backfill_uses_camera_thresholds_and_skips_duplicates(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    await register_camera(db_session, SPEC)
    rows = shift_to_end(read_minutes(write_csv(tmp_path / "m.csv")), datetime.now(timezone.utc))

    assert await backfill(db_session, "CAM-02", rows) == 3
    assert await backfill(db_session, "CAM-02", rows) == 0

    stored = (await db_session.scalars(select(CrowdRecord).order_by(CrowdRecord.timestamp))).all()
    assert [r.crowd_status for r in stored] == [CrowdStatus.SEPI, CrowdStatus.RAMAI, CrowdStatus.NORMAL]
    assert stored[-1].timestamp > datetime.now(timezone.utc) - timedelta(minutes=2)


async def test_backfill_requires_registered_camera(db_session: AsyncSession, tmp_path: Path) -> None:
    rows = read_minutes(write_csv(tmp_path / "m.csv"))
    with pytest.raises(LookupError):
        await backfill(db_session, "CAM-99", rows)
