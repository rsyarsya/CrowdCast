"""Camera management bodies for administrators."""

from typing import Annotated, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.security import mask_source
from app.models import Camera
from app.services.vision.roi import Roi

CameraCode = Annotated[str, Field(pattern=r"^[A-Z0-9-]{2,32}$", examples=["CAM-02"])]
# At least 1 so the counting classifier accepts the thresholds.
Threshold = Annotated[int, Field(ge=1)]
RoiPoints = list[Annotated[list[float], Field(min_length=2, max_length=2)]]


def validate_roi(points: RoiPoints | None) -> RoiPoints | None:
    """Same rules as the counting pipeline: >= 3 points inside 0..1."""
    if points is not None:
        Roi.from_points(points)
    return points


class CameraConfigOut(BaseModel):
    """Full camera configuration for administrators; credentials are masked."""

    camera_id: str
    name: str
    location: str
    source: str
    is_active: bool
    threshold_normal: int
    threshold_ramai: int
    roi: RoiPoints | None

    @classmethod
    def from_model(cls, camera: Camera) -> "CameraConfigOut":
        return cls(
            camera_id=camera.code,
            name=camera.name,
            location=camera.location,
            source=mask_source(camera.source),
            is_active=camera.is_active,
            threshold_normal=camera.threshold_normal,
            threshold_ramai=camera.threshold_ramai,
            roi=camera.roi,
        )


class CameraCreate(BaseModel):
    camera_id: CameraCode
    name: str = Field(min_length=1, max_length=100)
    location: str = Field(min_length=1, max_length=150)
    source: str = Field(
        min_length=1,
        max_length=500,
        description="Video path relative to backend/, or an RTSP URL",
    )
    threshold_normal: Threshold
    threshold_ramai: Threshold
    roi: RoiPoints | None = None

    _check_roi = field_validator("roi")(validate_roi)

    @model_validator(mode="after")
    def check_threshold_order(self) -> Self:
        if self.threshold_ramai <= self.threshold_normal:
            raise ValueError("threshold_ramai must be greater than threshold_normal")
        return self


class CameraUpdate(BaseModel):
    """Partial update. Send `"roi": null` to count the whole frame."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=150)
    source: str | None = Field(default=None, min_length=1, max_length=500)
    is_active: bool | None = None
    threshold_normal: Threshold | None = None
    threshold_ramai: Threshold | None = None
    roi: RoiPoints | None = None

    _check_roi = field_validator("roi")(validate_roi)
