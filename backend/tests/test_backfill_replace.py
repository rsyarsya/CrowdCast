from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CrowdRecord, CrowdStatus
from app.scripts.backfill_records import MinuteRow, backfill
from app.scripts.register_camera import CameraSpec, register_camera

pytestmark = pytest.mark.anyio

T0 = datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc)
SPEC = CameraSpec("CAM-02", "Kabukicho", "Kabukicho", "data/videos/k.mp4", 3, 10)


def minutes(counts: list[int], start: datetime = T0) -> list[MinuteRow]:
    return [MinuteRow(start + timedelta(minutes=i), c) for i, c in enumerate(counts)]


async def test_replace_deletes_old_records_of_the_camera(db_session: AsyncSession) -> None:
    await register_camera(db_session, SPEC)
    await backfill(db_session, "CAM-02", minutes([1, 2, 3, 4]))

    inserted = await backfill(
        db_session, "CAM-02", minutes([12, 5], start=T0 + timedelta(minutes=2)), replace=True
    )

    assert inserted == 2
    stored = (await db_session.scalars(select(CrowdRecord).order_by(CrowdRecord.timestamp))).all()
    assert [(r.people_count, r.crowd_status) for r in stored] == [
        (12, CrowdStatus.RAMAI),
        (5, CrowdStatus.NORMAL),
    ]


async def test_without_replace_existing_rows_are_kept(db_session: AsyncSession) -> None:
    await register_camera(db_session, SPEC)
    await backfill(db_session, "CAM-02", minutes([1, 2]))
    assert await backfill(db_session, "CAM-02", minutes([9, 9, 9])) == 1
    counts = (await db_session.scalars(select(CrowdRecord.people_count).order_by(CrowdRecord.timestamp))).all()
    assert counts == [1, 2, 9]
