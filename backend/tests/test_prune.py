from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Camera, CrowdRecord, CrowdStatus, Prediction
from app.scripts.prune import prune_predictions

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)


async def test_prune_removes_only_old_predictions(db_session: AsyncSession) -> None:
    camera = Camera(
        code="CAM-02", name="K", location="K", source="v.mp4", threshold_normal=4, threshold_ramai=12
    )
    db_session.add(camera)
    await db_session.flush()
    for days in (40, 31, 29, 0):
        db_session.add(Prediction(
            camera_id=camera.id, timestamp=NOW - timedelta(days=days), horizon_minutes=5,
            predicted_count=1, predicted_status=CrowdStatus.SEPI, model_name="linear",
        ))
    db_session.add(CrowdRecord(
        camera_id=camera.id, timestamp=NOW - timedelta(days=90), people_count=1,
        crowd_status=CrowdStatus.SEPI,
    ))
    await db_session.commit()

    assert await prune_predictions(db_session, NOW - timedelta(days=30)) == 2
    remaining = (await db_session.scalars(select(Prediction.timestamp).order_by(Prediction.timestamp))).all()
    assert remaining == [NOW - timedelta(days=29), NOW]
    assert len((await db_session.scalars(select(CrowdRecord))).all()) == 1
