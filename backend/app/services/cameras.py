"""Camera management rules. Raises `CameraError` with a stable code on violations."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Camera
from app.schemas.camera_admin import CameraCreate, CameraUpdate


class CameraError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def create_camera(session: AsyncSession, data: CameraCreate) -> Camera:
    camera = Camera(
        code=data.camera_id,
        name=data.name,
        location=data.location,
        source=data.source,
        threshold_normal=data.threshold_normal,
        threshold_ramai=data.threshold_ramai,
        roi=data.roi,
        is_active=True,
    )
    session.add(camera)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise CameraError("camera_code_exists") from exc
    return camera


async def update_camera(session: AsyncSession, camera: Camera, data: CameraUpdate) -> Camera:
    changes = data.model_dump(exclude_unset=True)
    # Fields that cannot be null in the database; null means "leave unchanged".
    for field in ("name", "location", "source", "is_active", "threshold_normal", "threshold_ramai"):
        if changes.get(field) is not None:
            setattr(camera, field, changes[field])
    if "roi" in changes:
        camera.roi = changes["roi"]

    if camera.threshold_ramai <= camera.threshold_normal:
        await session.rollback()
        raise CameraError("invalid_thresholds")
    await session.commit()
    return camera
