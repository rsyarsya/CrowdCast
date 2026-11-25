"""Camera management for administrators. Deactivating replaces deletion."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbSession, require_admin
from app.api.v1.cameras import CameraDep
from app.schemas.camera_admin import CameraConfigOut, CameraCreate, CameraUpdate
from app.services import cameras
from app.services.cameras import CameraError

router = APIRouter(
    prefix="/cameras",
    tags=["camera admin"],
    dependencies=[Depends(require_admin)],
)

ERROR_STATUS = {
    "camera_code_exists": status.HTTP_409_CONFLICT,
    "invalid_thresholds": status.HTTP_422_UNPROCESSABLE_CONTENT,
}


def to_http(error: CameraError) -> HTTPException:
    return HTTPException(ERROR_STATUS[error.code], detail=error.code)


@router.get("/{camera_id}/config", response_model=CameraConfigOut)
async def get_camera_config(camera: CameraDep) -> CameraConfigOut:
    """Thresholds, ROI, and the video source with any password masked."""
    return CameraConfigOut.from_model(camera)


@router.post("", response_model=CameraConfigOut, status_code=status.HTTP_201_CREATED)
async def create_camera(db: DbSession, body: CameraCreate) -> CameraConfigOut:
    try:
        return CameraConfigOut.from_model(await cameras.create_camera(db, body))
    except CameraError as error:
        raise to_http(error) from error


@router.patch("/{camera_id}", response_model=CameraConfigOut)
async def update_camera(db: DbSession, camera: CameraDep, body: CameraUpdate) -> CameraConfigOut:
    """Change any field. `is_active: false` stops the camera without losing history."""
    try:
        return CameraConfigOut.from_model(await cameras.update_camera(db, camera, body))
    except CameraError as error:
        raise to_http(error) from error
