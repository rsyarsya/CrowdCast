from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Camera, CrowdRecord, CrowdStatus, Prediction

pytestmark = pytest.mark.anyio

WIB = timezone(timedelta(hours=7))


def make_camera(**overrides: object) -> Camera:
    values: dict[str, object] = {
        "code": "CAM-01",
        "name": "Kamera Lobi",
        "location": "Lobi Gedung A",
        "source": "data/videos/sample.mp4",
        "threshold_normal": 10,
        "threshold_ramai": 30,
    }
    values.update(overrides)
    return Camera(**values)


async def add_camera(session: AsyncSession, **overrides: object) -> Camera:
    camera = make_camera(**overrides)
    session.add(camera)
    await session.commit()
    return camera


async def test_record_keeps_absolute_time_and_status(db_session: AsyncSession) -> None:
    camera = await add_camera(db_session)
    observed = datetime(2026, 9, 23, 10, 0, tzinfo=WIB)
    db_session.add(
        CrowdRecord(
            camera_id=camera.id,
            timestamp=observed,
            people_count=18,
            crowd_status=CrowdStatus.NORMAL,
        )
    )
    await db_session.commit()
    db_session.expunge_all()

    record = (await db_session.execute(select(CrowdRecord))).scalar_one()
    assert record.timestamp == observed  # same instant, returned as UTC
    assert record.timestamp.utcoffset() == timedelta(0)
    assert record.crowd_status is CrowdStatus.NORMAL
    stored = await db_session.scalar(text("SELECT crowd_status FROM crowd_records"))
    assert stored == "Normal"  # the value, not the Python member name


async def test_negative_people_count_is_rejected(db_session: AsyncSession) -> None:
    camera = await add_camera(db_session)
    db_session.add(
        CrowdRecord(
            camera_id=camera.id,
            timestamp=datetime.now(timezone.utc),
            people_count=-1,
            crowd_status=CrowdStatus.SEPI,
        )
    )
    with pytest.raises(IntegrityError, match="people_count_nonnegative"):
        await db_session.commit()


async def test_unknown_status_is_rejected_by_database(
    db_session: AsyncSession,
) -> None:
    camera = await add_camera(db_session)
    with pytest.raises(IntegrityError, match="crowd_status"):
        await db_session.execute(
            text(
                "INSERT INTO crowd_records (camera_id, timestamp, people_count, "
                "crowd_status) VALUES (:camera_id, now(), 5, 'Padat')"
            ),
            {"camera_id": camera.id},
        )


async def test_duplicate_observation_is_rejected(db_session: AsyncSession) -> None:
    camera = await add_camera(db_session)
    observed = datetime.now(timezone.utc)
    for _ in range(2):
        db_session.add(
            CrowdRecord(
                camera_id=camera.id,
                timestamp=observed,
                people_count=3,
                crowd_status=CrowdStatus.SEPI,
            )
        )
    with pytest.raises(IntegrityError, match="uq_crowd_records_camera_id_timestamp"):
        await db_session.commit()


async def test_threshold_order_is_enforced(db_session: AsyncSession) -> None:
    db_session.add(make_camera(threshold_normal=30, threshold_ramai=10))
    with pytest.raises(IntegrityError, match="threshold_order"):
        await db_session.commit()


async def test_camera_code_is_unique(db_session: AsyncSession) -> None:
    await add_camera(db_session)
    db_session.add(make_camera())
    with pytest.raises(IntegrityError, match="uq_cameras_code"):
        await db_session.commit()


async def test_deleting_camera_removes_its_history(db_session: AsyncSession) -> None:
    camera = await add_camera(db_session)
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            CrowdRecord(
                camera_id=camera.id,
                timestamp=now,
                people_count=40,
                crowd_status=CrowdStatus.RAMAI,
            ),
            Prediction(
                camera_id=camera.id,
                timestamp=now,
                horizon_minutes=5,
                predicted_count=45,
                predicted_status=CrowdStatus.RAMAI,
                model_name="moving_average",
            ),
        ]
    )
    await db_session.commit()

    await db_session.delete(camera)
    await db_session.commit()

    for model in (CrowdRecord, Prediction):
        count = await db_session.scalar(select(func.count()).select_from(model))
        assert count == 0
