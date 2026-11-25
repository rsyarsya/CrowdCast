from datetime import datetime, timedelta, timezone

import pytest

from app.services.vision.classifier import StatusThresholds
from app.services.vision.clock import frame_timestamp
from app.services.vision.pipeline import CountingPipeline
from app.services.vision.roi import Roi
from app.services.vision.types import Box

JST = timezone(timedelta(hours=9))
START = datetime(2026, 8, 25, 18, 0, 0, tzinfo=JST)


def people(n: int, y: float = 80) -> list[Box]:
    """n boxes whose feet are at height y in a 100x100 frame."""
    return [Box(i, y - 20, i + 1, y) for i in range(n)]


def test_pipeline_produces_minute_records_and_status():
    pipeline = CountingPipeline(StatusThresholds(5, 10, margin=1), smoothing_window_s=2, interval_s=60)
    records = []
    # 2 samples per second for 2 minutes: 3 people in minute 0, 12 in minute 1.
    for i in range(240):
        ts = frame_timestamp(i, 2, "dataset", video_start=START)
        live, record = pipeline.process(ts, people(3 if i < 120 else 12), 100, 100)
        if record:
            records.append(record)
    records.append(pipeline.flush())

    assert [r.start for r in records] == [START, START + timedelta(minutes=1)]
    assert records[0].people_count == 3
    assert records[1].people_count == 12
    assert live.crowd_status == "Ramai"


def test_pipeline_applies_roi():
    roi = Roi.from_points([(0, 0.5), (1, 0.5), (1, 1), (0, 1)])  # bottom half
    pipeline = CountingPipeline(StatusThresholds(5, 10), roi=roi)
    boxes = people(4, y=80) + people(6, y=30)  # only the first 4 stand in the ROI
    live, _ = pipeline.process(START, boxes, 100, 100)
    assert live.raw_count == 4


def test_frame_timestamp_modes():
    replay_start = datetime(2026, 11, 25, 9, 0, tzinfo=timezone(timedelta(hours=7)))
    assert frame_timestamp(60, 30, "dataset", video_start=START) == START + timedelta(seconds=2)
    assert frame_timestamp(0, 30, "replay", replay_start=replay_start) == replay_start
    with pytest.raises(ValueError):
        frame_timestamp(0, 30, "dataset")
    with pytest.raises(ValueError):
        frame_timestamp(0, 30, "dataset", video_start=datetime(2026, 8, 25, 18, 0))
