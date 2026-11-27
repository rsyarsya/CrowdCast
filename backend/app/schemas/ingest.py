"""Request and response bodies of the worker ingest API."""

from datetime import datetime

from pydantic import AwareDatetime, BaseModel, Field

from app.models import Camera, CrowdStatus


class WorkerCameraConfig(BaseModel):
    """Counting configuration the worker needs. Includes `source`, so worker-only."""

    camera_id: str
    source: str
    roi: list[list[float]] | None
    threshold_normal: int
    threshold_ramai: int

    @classmethod
    def from_model(cls, camera: Camera) -> "WorkerCameraConfig":
        return cls(
            camera_id=camera.code,
            source=camera.source,
            roi=camera.roi,
            threshold_normal=camera.threshold_normal,
            threshold_ramai=camera.threshold_ramai,
        )


class RecordIn(BaseModel):
    timestamp: AwareDatetime
    people_count: int = Field(ge=0)
    crowd_status: CrowdStatus


class RecordsIn(BaseModel):
    records: list[RecordIn] = Field(min_length=1, max_length=2000)


class RecordsAccepted(BaseModel):
    received: int


class PredictionIn(BaseModel):
    timestamp: AwareDatetime  # last observed minute; target time = timestamp + horizon
    horizon_minutes: int = Field(gt=0, le=1440)
    predicted_count: int = Field(ge=0)
    predicted_status: CrowdStatus
    model_name: str = Field(min_length=1, max_length=50)


class PredictionsIn(BaseModel):
    predictions: list[PredictionIn] = Field(min_length=1, max_length=100)


class LiveIn(BaseModel):
    timestamp: AwareDatetime
    raw_count: int = Field(ge=0)
    smoothed_count: float = Field(ge=0)
    crowd_status: CrowdStatus


class LiveAccepted(BaseModel):
    received_at: datetime
