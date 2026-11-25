"""Recorded video played back as if it were a live CCTV camera."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class VideoReplaySource:
    """Yields `(frame, t)` at the video's own frame rate (real-time pacing).

    `t` is a monotonic time in seconds. Playback starts at `start_minute` and
    jumps back to the start of the file when it ends (if `loop`). When decoding
    falls behind real time, frames are skipped with `grab()` (no full decode)
    so the stream stays in sync with the clock.
    """

    def __init__(self, path: Path, start_minute: float = 0.0, loop: bool = True) -> None:
        import cv2

        self._cv2 = cv2
        self.path = path
        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            raise FileNotFoundError(f"Cannot open video {path}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.loop = loop
        start = int(start_minute * 60 * self.fps)
        if self.total_frames and start >= self.total_frames:
            raise ValueError(f"start_minute {start_minute} is beyond the video length")
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, start)
        self.position = start

    def __iter__(self) -> Iterator[tuple[Any, float]]:
        frame_period = 1.0 / self.fps
        next_due = time.monotonic()
        while True:
            now = time.monotonic()
            if now < next_due:
                time.sleep(next_due - now)
            # Skip (without decoding) frames we are already late for.
            while time.monotonic() - next_due > frame_period:
                if not self.cap.grab():
                    break
                self.position += 1
                next_due += frame_period
            ok, frame = self.cap.read()
            if not ok:
                if not self.loop:
                    return
                logger.info("End of video, looping to the start")
                self.cap.set(self._cv2.CAP_PROP_POS_FRAMES, 0)
                self.position = 0
                continue
            self.position += 1
            yield frame, next_due
            next_due += frame_period

    def close(self) -> None:
        self.cap.release()
