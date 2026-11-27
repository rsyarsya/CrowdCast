"""Routes a browser opens directly: MJPEG video and server-sent events.

`<img>` and `EventSource` cannot send an Authorization header, so these routes
also accept a short-lived `?ticket=` issued by the matching ticket route.
"""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import CurrentUser, LiveHubDep, get_viewer
from app.api.v1.cameras import NO_STREAM, NOT_FOUND_DOC, CameraDep
from app.core.config import get_settings
from app.core.security import create_ticket
from app.schemas.monitoring import LiveStateOut
from app.services.live import ALERTS_TOPIC, Event

STREAM_BOUNDARY = "crowdcastframe"
SSE_HEADERS = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
SSE_DOC = {
    200: {"content": {"text/event-stream": {}}},
    401: {"description": "not_authenticated, invalid_token, or invalid_ticket"},
}

router = APIRouter(tags=["realtime"])


class TicketOut(BaseModel):
    ticket: str
    expires_in: int


def issue_ticket(user_id: int, scope: str) -> TicketOut:
    return TicketOut(
        ticket=create_ticket(user_id, scope),
        expires_in=get_settings().STREAM_TICKET_SECONDS,
    )


@router.post("/cameras/{camera_id}/ticket", response_model=TicketOut, responses=NOT_FOUND_DOC)
async def create_camera_ticket(user: CurrentUser, camera: CameraDep) -> TicketOut:
    """Ticket for `/stream` and `/events` of this camera. Valid only when connecting."""
    return issue_ticket(user.id, f"camera:{camera.code}")


@router.post("/alerts/ticket", response_model=TicketOut)
async def create_alerts_ticket(user: CurrentUser) -> TicketOut:
    """Ticket for `/alerts/events`. Valid only when connecting."""
    return issue_ticket(user.id, ALERTS_TOPIC)


@router.get(
    "/cameras/{camera_id}/stream",
    response_class=StreamingResponse,
    dependencies=[Depends(get_viewer)],
    responses={200: {"content": {"multipart/x-mixed-replace": {}}}, **NOT_FOUND_DOC},
)
async def get_stream(camera: CameraDep, hub: LiveHubDep) -> StreamingResponse:
    """MJPEG stream of the annotated video, usable as an `<img>` source with `?ticket=`."""
    if not hub.has_frame(camera.code):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NO_STREAM)

    async def parts() -> AsyncIterator[bytes]:
        async for jpeg in hub.frames(camera.code):
            yield (
                b"--" + STREAM_BOUNDARY.encode() + b"\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n"
            )

    return StreamingResponse(
        parts(),
        media_type=f"multipart/x-mixed-replace; boundary={STREAM_BOUNDARY}",
        headers={"Cache-Control": "no-store"},
    )


@router.get(
    "/cameras/{camera_id}/events",
    response_class=StreamingResponse,
    dependencies=[Depends(get_viewer)],
    responses={**NOT_FOUND_DOC, **SSE_DOC},
)
async def get_camera_events(camera: CameraDep, hub: LiveHubDep) -> StreamingResponse:
    """Server-sent events for one camera: `live`, `record`, `prediction`, and `alert`.

    The current live state, when known, is sent first.
    """
    state = hub.get_live(camera.code)
    initial = (
        [Event("live", LiveStateOut.from_state(camera.code, state).model_dump_json())]
        if state is not None
        else []
    )
    stream = hub.event_stream(camera.code, initial, get_settings().SSE_HEARTBEAT_SECONDS)
    return StreamingResponse(stream, media_type="text/event-stream", headers=SSE_HEADERS)


@router.get(
    "/alerts/events",
    response_class=StreamingResponse,
    dependencies=[Depends(get_viewer)],
    responses=SSE_DOC,
)
async def get_alert_events(hub: LiveHubDep) -> StreamingResponse:
    """Server-sent `alert` events for every camera, for a notification badge."""
    stream = hub.event_stream(ALERTS_TOPIC, [], get_settings().SSE_HEARTBEAT_SECONDS)
    return StreamingResponse(stream, media_type="text/event-stream", headers=SSE_HEADERS)
