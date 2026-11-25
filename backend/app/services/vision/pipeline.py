"""Counting pipeline: detections -> ROI count -> smoothing -> status + interval records.

The pipeline does not know about YOLO. It receives a list of `Box` objects, so
the detector can be replaced, or faked in tests, without changing this code.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from app.services.vision.aggregation import IntervalAggregator
from app.services.vision.classifier import HysteresisClassifier, StatusThresholds
from app.services.vision.roi import Roi, count_in_roi
from app.services.vision.smoothing import RollingMedian
from app.services.vision.types import AnchorMode, Box, IntervalRecord, LiveState


class CountingPipeline:
    def __init__(
        self,
        thresholds: StatusThresholds,
        roi: Roi | None = None,
        anchor: AnchorMode = "foot",
        smoothing_window_s: float = 5.0,
        interval_s: int = 60,
        status_dwell_s: float = 30.0,
    ) -> None:
        self.roi = roi
        self.anchor = anchor
        self.smoother = RollingMedian(smoothing_window_s)
        self.aggregator = IntervalAggregator(interval_s)
        self.live_classifier = HysteresisClassifier(thresholds, dwell_s=status_dwell_s)
        self.thresholds = thresholds

    def process(
        self, timestamp: datetime, boxes: Iterable[Box], frame_w: int, frame_h: int
    ) -> tuple[LiveState, IntervalRecord | None]:
        """Handle one detection sample.

        Returns the live state and, when an interval just closed, its record.
        """
        raw = count_in_roi(boxes, self.roi, frame_w, frame_h, self.anchor)
        t = timestamp.timestamp()
        smoothed = self.smoother.update(t, raw)
        status = self.live_classifier.update(smoothed, t)
        record = self.aggregator.add(timestamp, smoothed)
        return LiveState(timestamp, raw, smoothed, status), record

    def flush(self) -> IntervalRecord | None:
        return self.aggregator.flush()
