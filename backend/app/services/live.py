"""In-memory live state and latest video frame per camera.

The vision worker pushes the current count/status and annotated JPEG frames
through the ingest API; dashboards read them back. Nothing here is persisted:
it only describes "now", while CrowdRecord rows in the database hold history.

The hub lives in one API process. Running uvicorn with several worker
processes would give each process its own hub, so the API must run as a
single process (the default for `uvicorn app.main:app`).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.models import CrowdStatus


@dataclass(frozen=True, slots=True)
class LiveState:
    timestamp: datetime
    raw_count: int
    smoothed_count: float
    crowd_status: CrowdStatus
    received_at: datetime


@dataclass(slots=True)
class _CameraChannel:
    live: LiveState | None = None
    frame: bytes | None = None
    frame_version: int = 0
    frame_changed: asyncio.Condition = field(default_factory=asyncio.Condition)


class LiveHub:
    def __init__(self) -> None:
        self._channels: dict[str, _CameraChannel] = {}

    def _channel(self, camera_code: str) -> _CameraChannel:
        return self._channels.setdefault(camera_code, _CameraChannel())

    def set_live(
        self,
        camera_code: str,
        timestamp: datetime,
        raw_count: int,
        smoothed_count: float,
        crowd_status: CrowdStatus,
    ) -> LiveState:
        state = LiveState(
            timestamp, raw_count, smoothed_count, crowd_status, datetime.now(timezone.utc)
        )
        self._channel(camera_code).live = state
        return state

    def get_live(self, camera_code: str) -> LiveState | None:
        channel = self._channels.get(camera_code)
        return channel.live if channel else None

    async def publish_frame(self, camera_code: str, jpeg: bytes) -> None:
        channel = self._channel(camera_code)
        async with channel.frame_changed:
            channel.frame = jpeg
            channel.frame_version += 1
            channel.frame_changed.notify_all()

    def has_frame(self, camera_code: str) -> bool:
        channel = self._channels.get(camera_code)
        return channel is not None and channel.frame is not None

    async def frames(self, camera_code: str, timeout: float = 5.0) -> AsyncIterator[bytes]:
        """Yield the current frame, then every new one.

        If no new frame arrives within `timeout` seconds, the last frame is sent
        again so the connection stays alive and the browser keeps showing it.
        """
        channel = self._channel(camera_code)
        seen = -1
        while True:
            async with channel.frame_changed:
                if channel.frame_version == seen:
                    try:
                        await asyncio.wait_for(
                            channel.frame_changed.wait_for(
                                lambda: channel.frame_version != seen
                            ),
                            timeout,
                        )
                    except TimeoutError:
                        pass
                seen = channel.frame_version
                frame = channel.frame
            if frame is not None:
                yield frame
