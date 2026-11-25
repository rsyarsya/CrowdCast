"""Timestamps for frames of a recorded video.

`dataset` mode: real time of the recording (video start time + frame offset).
    Used to build the time series for forecasting.
`replay` mode: the video plays as if it were a live CCTV camera, so the time is
    "now" when processing started + frame offset. Used for the dashboard demo.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

ClockMode = Literal["dataset", "replay"]


def frame_timestamp(
    frame_index: int,
    fps: float,
    mode: ClockMode,
    video_start: datetime | None = None,
    replay_start: datetime | None = None,
) -> datetime:
    if fps <= 0:
        raise ValueError("fps must be positive")
    if mode == "dataset":
        base = video_start
    elif mode == "replay":
        base = replay_start
    else:
        raise ValueError(f"Unknown clock mode: {mode}")
    if base is None:
        raise ValueError(f"A start time is required for {mode} mode")
    if base.tzinfo is None:
        raise ValueError("Start time must include a timezone")
    return base + timedelta(seconds=frame_index / fps)
