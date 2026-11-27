"""Open and close crowd alerts from stored records and forecasts."""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Alert, AlertKind, Camera, CrowdStatus, User


@dataclass(frozen=True, slots=True)
class Observation:
    timestamp: datetime
    count: int
    status: CrowdStatus


def apply_observation(
    alert: Alert | None,
    observation: Observation,
    camera_id: int,
    kind: AlertKind,
    horizon_minutes: int | None,
) -> tuple[Alert | None, bool]:
    """Advance one alert track by one observation.

    Returns the alert that is open afterwards and whether anything changed.
    Observations older than what the open alert has already seen are ignored,
    so retried or out-of-order uploads cannot close an alert by mistake.
    """
    crowded = observation.status is CrowdStatus.RAMAI
    if alert is None:
        if not crowded:
            return None, False
        return Alert(
            camera_id=camera_id,
            kind=kind,
            horizon_minutes=horizon_minutes,
            started_at=observation.timestamp,
            last_seen_at=observation.timestamp,
            peak_count=observation.count,
        ), True
    if observation.timestamp <= alert.last_seen_at:
        if crowded and observation.count > alert.peak_count:
            alert.peak_count = observation.count
            return alert, True
        return alert, False
    if crowded:
        alert.last_seen_at = observation.timestamp
        alert.peak_count = max(alert.peak_count, observation.count)
        return alert, True
    alert.ended_at = observation.timestamp
    return None, True


async def _open_alert(
    session: AsyncSession, camera: Camera, kind: AlertKind, horizon_minutes: int | None
) -> Alert | None:
    horizon_filter = (
        Alert.horizon_minutes.is_(None)
        if horizon_minutes is None
        else Alert.horizon_minutes == horizon_minutes
    )
    return await session.scalar(
        select(Alert).where(
            Alert.camera_id == camera.id,
            Alert.kind == kind,
            horizon_filter,
            Alert.ended_at.is_(None),
        )
    )


async def _track(
    session: AsyncSession,
    camera: Camera,
    kind: AlertKind,
    horizon_minutes: int | None,
    observations: Iterable[Observation],
) -> list[Alert]:
    alert = await _open_alert(session, camera, kind, horizon_minutes)
    changed: list[Alert] = []
    for observation in sorted(observations, key=lambda o: o.timestamp):
        previous = alert
        alert, did_change = apply_observation(
            alert, observation, camera.id, kind, horizon_minutes
        )
        if not did_change:
            continue
        if alert is not None and alert is not previous:
            session.add(alert)
        await session.flush()
        touched = alert if alert is not None else previous
        if touched is not None and touched not in changed:
            changed.append(touched)
    return changed


async def track_records(
    session: AsyncSession, camera: Camera, observations: Iterable[Observation]
) -> list[Alert]:
    """Update the camera's actual-crowd alert. The caller commits."""
    return await _track(session, camera, AlertKind.CROWDED, None, observations)


async def track_forecasts(
    session: AsyncSession, camera: Camera, forecasts: Iterable[tuple[int, Observation]]
) -> list[Alert]:
    """Update one forecast alert per horizon from (horizon_minutes, observation) pairs."""
    by_horizon: dict[int, list[Observation]] = defaultdict(list)
    for horizon, observation in forecasts:
        by_horizon[horizon].append(observation)
    changed: list[Alert] = []
    for horizon in sorted(by_horizon):
        changed += await _track(
            session, camera, AlertKind.FORECAST_CROWDED, horizon, by_horizon[horizon]
        )
    return changed


async def list_alerts(
    session: AsyncSession,
    camera: Camera | None,
    active: bool | None,
    start: datetime | None,
    end: datetime | None,
    limit: int,
) -> Sequence[Alert]:
    query = select(Alert).options(
        selectinload(Alert.camera), selectinload(Alert.acknowledged_by)
    )
    if camera is not None:
        query = query.where(Alert.camera_id == camera.id)
    if active is True:
        query = query.where(Alert.ended_at.is_(None))
    elif active is False:
        query = query.where(Alert.ended_at.is_not(None))
    if start is not None:
        query = query.where(Alert.started_at >= start)
    if end is not None:
        query = query.where(Alert.started_at <= end)
    query = query.order_by(Alert.started_at.desc(), Alert.id.desc()).limit(limit)
    return (await session.scalars(query)).all()


async def get_alert(session: AsyncSession, alert_id: int) -> Alert | None:
    return await session.scalar(
        select(Alert)
        .where(Alert.id == alert_id)
        .options(selectinload(Alert.camera), selectinload(Alert.acknowledged_by))
    )


async def acknowledge(session: AsyncSession, alert: Alert, user: User) -> Alert:
    """Mark the alert as seen. Acknowledging twice keeps the first acknowledgement."""
    if alert.acknowledged_at is None:
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.acknowledged_by = user
        await session.commit()
    return alert
