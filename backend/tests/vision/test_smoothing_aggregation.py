from datetime import datetime, timedelta, timezone

import pytest

from app.services.vision.aggregation import IntervalAggregator
from app.services.vision.smoothing import RollingMedian

WIB = timezone(timedelta(hours=7))
T0 = datetime(2026, 11, 25, 10, 0, 0, tzinfo=WIB)


def test_rolling_median_ignores_single_spike():
    smoother = RollingMedian(window_s=5)
    values = [smoother.update(t * 0.5, c) for t, c in enumerate([10, 10, 30, 10, 10])]
    assert max(values) == 10


def test_rolling_median_drops_old_samples():
    smoother = RollingMedian(window_s=2)
    smoother.update(0, 100)
    smoother.update(1, 100)
    assert smoother.update(5, 3) == 3  # both old samples are outside the window


def test_rolling_median_rejects_out_of_order():
    smoother = RollingMedian()
    smoother.update(10, 1)
    with pytest.raises(ValueError):
        smoother.update(5, 1)


def test_aggregator_emits_record_when_minute_changes():
    agg = IntervalAggregator(60)
    assert agg.add(T0, 10) is None
    assert agg.add(T0 + timedelta(seconds=30), 13) is None
    record = agg.add(T0 + timedelta(seconds=61), 99)
    assert record is not None
    assert record.start == T0
    assert record.people_count == 12  # mean 11.5 rounds half up
    assert record.n_samples == 2


def test_aggregator_aligns_to_interval_boundaries():
    agg = IntervalAggregator(60)
    agg.add(T0 + timedelta(seconds=45), 5)
    record = agg.flush()
    assert record is not None
    assert record.start == T0


def test_aggregator_flush_empty_returns_none():
    assert IntervalAggregator().flush() is None
