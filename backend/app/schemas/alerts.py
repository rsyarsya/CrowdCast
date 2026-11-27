from datetime import datetime, timedelta

from pydantic import BaseModel, field_serializer

from app.models import Alert, AlertKind
from app.schemas.monitoring import to_local_time


class AlertOut(BaseModel):
    """`target_time` is when a forecast alert expects the crowd; null for actual alerts."""

    id: int
    camera_id: str
    location: str
    kind: AlertKind
    horizon_minutes: int | None
    started_at: datetime
    last_seen_at: datetime
    ended_at: datetime | None
    target_time: datetime | None
    is_active: bool
    peak_count: int
    acknowledged_at: datetime | None
    acknowledged_by: str | None

    @field_serializer("started_at", "last_seen_at", "ended_at", "target_time", "acknowledged_at")
    def serialize_times(self, value: datetime | None) -> str | None:
        return to_local_time(value).isoformat() if value is not None else None

    @classmethod
    def from_model(cls, alert: Alert) -> "AlertOut":
        target = (
            alert.last_seen_at + timedelta(minutes=alert.horizon_minutes)
            if alert.horizon_minutes is not None
            else None
        )
        return cls(
            id=alert.id,
            camera_id=alert.camera.code,
            location=alert.camera.location,
            kind=alert.kind,
            horizon_minutes=alert.horizon_minutes,
            started_at=alert.started_at,
            last_seen_at=alert.last_seen_at,
            ended_at=alert.ended_at,
            target_time=target,
            is_active=alert.ended_at is None,
            peak_count=alert.peak_count,
            acknowledged_at=alert.acknowledged_at,
            acknowledged_by=alert.acknowledged_by.name if alert.acknowledged_by else None,
        )
