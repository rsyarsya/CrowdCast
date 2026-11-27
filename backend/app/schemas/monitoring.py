from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel, field_serializer

from app.core.config import get_settings
from app.models import Camera, CrowdRecord, CrowdStatus, Prediction
from app.services.live import LiveState
from app.services.monitoring import RecordBucket


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

    @classmethod
    def from_state(cls, camera_code: str, state: LiveState) -> "LiveStateOut":
        age = (datetime.now(timezone.utc) - state.received_at).total_seconds()
        return cls(
            camera_id=camera_code,
            timestamp=state.timestamp,
            people_count=state.raw_count,
            smoothed_count=state.smoothed_count,
            crowd_status=state.crowd_status,
            is_stale=age > get_settings().LIVE_STALE_SECONDS,
        )


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



STATUS_SEVERITY = {CrowdStatus.SEPI: 0, CrowdStatus.NORMAL: 1, CrowdStatus.RAMAI: 2}


class SummaryPointOut(BaseModel):
    """`crowd_status` is the most frequent status in the bucket; ties go to the busier one."""

    bucket_start: datetime
    avg_count: float
    min_count: int
    max_count: int
    records: int
    status_counts: dict[CrowdStatus, int]
    crowd_status: CrowdStatus

    @field_serializer("bucket_start")
    def serialize_bucket_start(self, value: datetime) -> str:
        return to_local_time(value).isoformat()

    @classmethod
    def from_bucket(cls, bucket: RecordBucket) -> "SummaryPointOut":
        dominant = max(
            bucket.status_counts, key=lambda s: (bucket.status_counts[s], STATUS_SEVERITY[s])
        )
        return cls(
            bucket_start=bucket.start,
            avg_count=round(bucket.avg_count, 1),
            min_count=bucket.min_count,
            max_count=bucket.max_count,
            records=bucket.records,
            status_counts=bucket.status_counts,
            crowd_status=dominant,
        )


class MonitoringSummaryOut(BaseModel):
    camera_id: str
    location: str
    bucket: str
    start: datetime
    end: datetime
    points: list[SummaryPointOut]

    @field_serializer("start", "end")
    def serialize_range(self, value: datetime) -> str:
        return to_local_time(value).isoformat()
