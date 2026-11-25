"""Crowd status classification: Sepi / Normal / Ramai.

This is rule-based business logic on top of the model output, not deep learning.
The threshold values are configuration per camera; the final numbers are
decided in Phase 3 from observed data or the area capacity.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.vision.types import CrowdStatus

_LEVELS: tuple[CrowdStatus, ...] = ("Sepi", "Normal", "Ramai")


@dataclass(frozen=True, slots=True)
class StatusThresholds:
    """`normal_from`: lowest count that is Normal. `ramai_from`: lowest count that is Ramai.

    `margin`: how far the count must fall below a threshold before the status goes
    down again (hysteresis). 0 disables hysteresis.
    """

    normal_from: float
    ramai_from: float
    margin: float = 0.0

    def __post_init__(self) -> None:
        if not 0 < self.normal_from < self.ramai_from:
            raise ValueError("Thresholds must satisfy 0 < normal_from < ramai_from")
        if self.margin < 0:
            raise ValueError("margin must not be negative")
        if self.margin >= self.normal_from or self.margin >= self.ramai_from - self.normal_from:
            raise ValueError("margin must be smaller than the gaps between thresholds")


def classify(count: float, th: StatusThresholds) -> CrowdStatus:
    """Stateless classification without hysteresis."""
    if count >= th.ramai_from:
        return "Ramai"
    if count >= th.normal_from:
        return "Normal"
    return "Sepi"


class HysteresisClassifier:
    """Classification that does not flicker around a threshold.

    Going up uses the normal thresholds. Going down requires the count to drop
    below `threshold - margin`. Example with ramai_from=30, margin=3: 29 -> 30
    switches to Ramai, but it only goes back to Normal below 27.
    """

    def __init__(self, thresholds: StatusThresholds) -> None:
        self.th = thresholds
        self.status: CrowdStatus | None = None

    def update(self, count: float) -> CrowdStatus:
        target = classify(count, self.th)
        if self.status is None or _LEVELS.index(target) > _LEVELS.index(self.status):
            self.status = target
            return target

        # Only step down when the count is clearly below the current level's lower bound.
        lowered = classify(count + self.th.margin, self.th)
        if _LEVELS.index(lowered) < _LEVELS.index(self.status):
            self.status = lowered
        return self.status
