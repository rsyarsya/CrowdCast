"""Shared data types for the vision counting pipeline.

These types are plain Python so that the counting logic can be tested in CI
without numpy, OpenCV, or torch. The detector (YOLO) only has to produce a list
of `Box` objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

# Must match CrowdStatus in frontend/src/lib/monitoring/types.ts.
CrowdStatus = Literal["Sepi", "Normal", "Ramai"]

# Which point of a bounding box decides whether a person is inside the ROI.
# "foot" (bottom-center) is the ground position and is used for real cameras.
# "head" (top-center) is only used to evaluate on the Mall Dataset, whose
# ground truth marks heads.
AnchorMode = Literal["foot", "head"]


@dataclass(frozen=True, slots=True)
class Box:
    """One person detection in pixel coordinates."""

    x1: float
    y1: float
    x2: float
    y2: float
    score: float = 1.0


@dataclass(frozen=True, slots=True)
class LiveState:
    """Latest per-sample state, used for the live dashboard."""

    timestamp: datetime
    raw_count: int
    smoothed_count: float
    crowd_status: CrowdStatus


@dataclass(frozen=True, slots=True)
class IntervalRecord:
    """One aggregated observation, stored as a CrowdRecord."""

    start: datetime
    people_count: int
    n_samples: int
