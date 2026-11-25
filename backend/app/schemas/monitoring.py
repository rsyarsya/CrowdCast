from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel, field_serializer

from app.core.config import get_settings
from app.models import Camera, CrowdRecord, CrowdStatus, Prediction


def to_local_time(value: datetime) -> datetime:
    """Convert a UTC timestamp from the database to the configured zone (WIB)."""
    return value.astimezone(ZoneInfo(get_settings().TIMEZONE))


class CameraOut(BaseModel):
    """Public camera info. `source` (file path or RTSP URL) is never exposed."""

    camera_id: str
    name: str
    location: str
    is_active: bool

    @classmethod
    def from_model(cls, camera: Camera) -> "CameraOut":
        return cls(
            camera_id=camera.code,
            name=camera.name,
            location=camera.location,
            is_active=camera.is_active,
        )


class MonitoringRecordOut(BaseModel):
    """Matches `MonitoringRecord` in frontend/src/lib/monitoring/types.ts."""

    camera_id: str
    location: str
    timestamp: datetime
    people_count: int
    crowd_status: CrowdStatus

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        return to_local_time(value).isoformat()

    @classmethod
    def from_model(cls, camera: Camera, record: CrowdRecord) -> "MonitoringRecordOut":
        return cls(
            camera_id=camera.code,
            location=camera.location,
            timestamp=record.timestamp,
            people_count=record.people_count,
            crowd_status=record.crowd_status,
        )


class LiveStateOut(BaseModel):
    """Current count and status from the vision worker (not stored in history).

    `crowd_status` uses the dwell time, so it changes less often than the
    per-minute records. `is_stale` is true when the worker stopped sending.
    """

    camera_id: str
    timestamp: datetime
    people_count: int
    smoothed_count: float
    crowd_status: CrowdStatus
    is_stale: bool

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        return to_local_time(value).isoformat()


class PredictionOut(BaseModel):
    camera_id: str
    timestamp: datetime
    horizon_minutes: int
    target_time: datetime
    predicted_count: int
    predicted_status: CrowdStatus
    model_name: str
    is_simulation: bool

    @field_serializer("timestamp", "target_time")
    def serialize_times(self, value: datetime) -> str:
        return to_local_time(value).isoformat()

    @classmethod
    def from_model(cls, camera: Camera, prediction: Prediction) -> "PredictionOut":
        return cls(
            camera_id=camera.code,
            timestamp=prediction.timestamp,
            horizon_minutes=prediction.horizon_minutes,
            target_time=prediction.timestamp
            + timedelta(minutes=prediction.horizon_minutes),
            predicted_count=prediction.predicted_count,
            predicted_status=prediction.predicted_status,
            model_name=prediction.model_name,
            is_simulation=prediction.is_simulation,
        )
