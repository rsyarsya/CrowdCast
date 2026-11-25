"""Read queries for monitoring data. Pure database access, no HTTP concerns."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Camera, CrowdRecord, Prediction


async def list_cameras(session: AsyncSession) -> Sequence[Camera]:
    return (await session.scalars(select(Camera).order_by(Camera.code))).all()


async def get_camera_by_code(session: AsyncSession, code: str) -> Camera | None:
    return await session.scalar(select(Camera).where(Camera.code == code))


async def get_latest_record(
    session: AsyncSession, camera: Camera
) -> CrowdRecord | None:
    # Served by the unique (camera_id, timestamp) index.
    return await session.scalar(
        select(CrowdRecord)
        .where(CrowdRecord.camera_id == camera.id)
        .order_by(CrowdRecord.timestamp.desc())
        .limit(1)
    )


async def list_records(
    session: AsyncSession,
    camera: Camera,
    start: datetime | None,
    end: datetime | None,
    limit: int,
) -> Sequence[CrowdRecord]:
    """Records in ascending time order.

    Without `start`, the most recent `limit` records are returned so the
    History chart shows the latest window rather than the oldest data.
    """
    query = select(CrowdRecord).where(CrowdRecord.camera_id == camera.id)
    if start is not None:
        query = query.where(CrowdRecord.timestamp >= start)
    if end is not None:
        query = query.where(CrowdRecord.timestamp <= end)

    if start is None:
        latest_first = query.order_by(CrowdRecord.timestamp.desc()).limit(limit)
        return list(reversed((await session.scalars(latest_first)).all()))
    return (
        await session.scalars(query.order_by(CrowdRecord.timestamp).limit(limit))
    ).all()


async def get_latest_predictions(
    session: AsyncSession, camera: Camera
) -> Sequence[Prediction]:
    """The newest prediction for each horizon, ordered by horizon."""
    # PostgreSQL DISTINCT ON keeps the first row per horizon after ordering,
    # served by the (camera_id, horizon_minutes, timestamp) index.
    query = (
        select(Prediction)
        .where(Prediction.camera_id == camera.id)
        .ext(distinct_on(Prediction.horizon_minutes))
        .order_by(Prediction.horizon_minutes, Prediction.timestamp.desc())
    )
    return (await session.scalars(query)).all()
