"""Crowd status classification: Sepi / Normal / Ramai.

This is rule-based business logic on top of the model output, not deep learning.
The threshold values are configuration per camera; the final numbers are
decided per camera from observed data or the area capacity.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import quantiles

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


def thresholds_from_percentiles(
    counts: Sequence[float], low_pct: float = 25, high_pct: float = 75, margin: float = 0
) -> StatusThresholds:
    """Derive thresholds from observed per-minute counts of one camera.

    With the defaults, the quietest quarter of the minutes is Sepi and the busiest
    quarter is Ramai. The margin is reduced when the gaps are too small for it.
    """
    if len(counts) < 2:
        raise ValueError("Need at least 2 counts")
    cuts = quantiles(counts, n=100, method="inclusive")
    normal_from = max(1.0, float(round(cuts[int(low_pct) - 1])))
    ramai_from = max(normal_from + 1, float(round(cuts[int(high_pct) - 1])))
    margin = max(0.0, min(margin, normal_from - 1, ramai_from - normal_from - 1))
    return StatusThresholds(normal_from, ramai_from, margin)


class HysteresisClassifier:
    """Classification that does not flicker around a threshold.

    Two mechanisms, both optional:
    - Margin (hysteresis): going up uses the normal thresholds, going down requires
      the count to drop below `threshold - margin`. Example with ramai_from=30,
      margin=3: 29 -> 30 switches to Ramai, but it only goes back to Normal below 27.
    - Dwell time: a new status must be proposed continuously for `dwell_s` seconds
      before it is accepted, so short peaks and dips do not change the status.
    """

    def __init__(self, thresholds: StatusThresholds, dwell_s: float = 0.0) -> None:
        if dwell_s < 0:
            raise ValueError("dwell_s must not be negative")
        self.th = thresholds
        self.dwell_s = dwell_s
        self.status: CrowdStatus | None = None
        self._pending: CrowdStatus | None = None
        self._pending_since = 0.0

    def _propose(self, count: float) -> CrowdStatus:
        target = classify(count, self.th)
        if self.status is None or _LEVELS.index(target) > _LEVELS.index(self.status):
            return target
        # Only step down when the count is clearly below the current level's lower bound.
        lowered = classify(count + self.th.margin, self.th)
        return lowered if _LEVELS.index(lowered) < _LEVELS.index(self.status) else self.status

    def update(self, count: float, t: float | None = None) -> CrowdStatus:
        """Classify one sample. `t` (seconds) is required when dwell_s > 0."""
        proposed = self._propose(count)
        if self.status is None or proposed == self.status:
            self.status, self._pending = proposed, None
            return proposed
        if self.dwell_s == 0:
            self.status, self._pending = proposed, None
            return proposed
        if t is None:
            raise ValueError("t is required when dwell_s > 0")
        if proposed != self._pending:
            self._pending, self._pending_since = proposed, t
        if t - self._pending_since >= self.dwell_s:
            self.status, self._pending = proposed, None
        return self.status
