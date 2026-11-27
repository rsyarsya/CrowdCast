"""In-memory live state, latest video frame, and event fan-out per camera.

The vision worker pushes the current count/status and annotated JPEG frames
through the ingest API; dashboards read them back. Nothing here is persisted:
it only describes "now", while CrowdRecord rows in the database hold history.

The hub lives in one API process. Running uvicorn with several worker
processes would give each process its own hub, so the API must run as a
single process (the default for `uvicorn app.main:app`).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
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


ALERTS_TOPIC = "alerts"
EVENT_QUEUE_SIZE = 100


@dataclass(frozen=True, slots=True)
class Event:
    name: str
    data: str

    def encode(self) -> str:
        return f"event: {self.name}\ndata: {self.data}\n\n"


@dataclass(slots=True)
class _CameraChannel:
    live: LiveState | None = None
    frame: bytes | None = None
    frame_version: int = 0
    frame_changed: asyncio.Condition = field(default_factory=asyncio.Condition)


class LiveHub:
    def __init__(self) -> None:
        self._channels: dict[str, _CameraChannel] = {}
        self._subscribers: dict[str, set[asyncio.Queue[Event]]] = {}

    def publish(self, topic: str, name: str, data: str) -> None:
        """Send an event to every subscriber of `topic`.

        A subscriber that falls behind loses its oldest events instead of
        slowing down the publisher.
        """
        event = Event(name, data)
        for queue in self._subscribers.get(topic, ()):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)

    @asynccontextmanager
    async def subscribe(self, topic: str) -> AsyncIterator[asyncio.Queue[Event]]:
        queue: asyncio.Queue[Event] = asyncio.Queue(EVENT_QUEUE_SIZE)
        subscribers = self._subscribers.setdefault(topic, set())
        subscribers.add(queue)
        try:
            yield queue
        finally:
            subscribers.discard(queue)
            if not subscribers:
                self._subscribers.pop(topic, None)

    def subscriber_count(self, topic: str) -> int:
        return len(self._subscribers.get(topic, ()))

    async def event_stream(
        self, topic: str, initial: Iterable[Event], heartbeat: float
    ) -> AsyncIterator[str]:
        """Server-sent events for `topic`, starting with `initial`.

        A comment line is sent after `heartbeat` idle seconds so proxies do not
        close the connection.
        """
        async with self.subscribe(topic) as queue:
            for event in initial:
                yield event.encode()
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), heartbeat)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield event.encode()

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
