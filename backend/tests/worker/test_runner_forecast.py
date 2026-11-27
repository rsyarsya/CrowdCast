from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.forecast.baselines import MovingAverageForecaster
from app.services.vision.classifier import StatusThresholds
from app.services.vision.pipeline import CountingPipeline
from app.services.vision.types import Box
from app.worker.forecasting import ForecastRunner
from app.worker.runner import VisionWorker

T0 = datetime(2026, 11, 25, 16, 0, tzinfo=timezone.utc)
TH = StatusThresholds(4, 12)
FRAME = SimpleNamespace(shape=(100, 100, 3))


def minute(i: int) -> datetime:
    return T0 + timedelta(minutes=i)


def test_runner_waits_for_enough_history_then_forecasts_all_horizons():
    runner = ForecastRunner(MovingAverageForecaster(3), TH)
    assert runner.on_record(minute(0), 2) == []
    assert runner.on_record(minute(1), 4) == []
    points = runner.on_record(minute(2), 12)
    assert [(p.horizon_minutes, p.predicted_count, p.predicted_status) for p in points] == [
        (5, 6, "Normal"),
        (15, 6, "Normal"),
        (30, 6, "Normal"),
    ]
    assert points[0].timestamp == minute(2)
    assert points[0].model_name == "moving_average_3"


def test_long_gap_restarts_history():
    runner = ForecastRunner(MovingAverageForecaster(3), TH)
    runner.seed([(minute(0), 5), (minute(1), 5), (minute(2), 5)])
    assert runner.on_record(minute(20), 9) == []  # 18-minute gap: history starts over
    assert runner.history_length == 1


def test_short_gap_repeats_previous_value():
    runner = ForecastRunner(MovingAverageForecaster(4), TH)
    runner.seed([(minute(0), 0), (minute(1), 4)])
    points = runner.on_record(minute(3), 8)  # minute 2 missing -> filled with 4
    assert points[0].predicted_count == round((0 + 4 + 4 + 8) / 4)


def test_duplicate_minutes_are_ignored():
    runner = ForecastRunner(MovingAverageForecaster(2), TH)
    runner.seed([(minute(0), 1), (minute(1), 3), (minute(1), 99)])
    assert runner.history_length == 2


class Sender:
    def __init__(self) -> None:
        self.records, self.predictions = [], []

    def put_frame(self, jpeg):  # pragma: no cover - not used here
        pass

    def put_live(self, live):
        pass

    def post_records(self, records):
        self.records.extend(records)

    def post_predictions(self, predictions):
        self.predictions.extend(predictions)


def test_worker_sends_forecasts_after_each_minute_record():
    sender = Sender()
    clock = SimpleNamespace(value=T0)
    counts = iter([6] * 4 + [8] * 4)
    worker = VisionWorker(
        detector=lambda _f: [Box(i, 60, i + 1, 80) for i in range(next(counts))],
        encoder=lambda *_: b"",
        sender=sender,
        pipeline=CountingPipeline(TH, smoothing_window_s=1, status_dwell_s=0),
        thresholds=TH,
        now=lambda: clock.value,
        forecast=ForecastRunner(MovingAverageForecaster(1), TH),
    )
    for _ in range(8):
        worker.detect_once(FRAME)
        clock.value += timedelta(seconds=15)
    worker.flush_pipeline()
    worker.send_pending()

    assert [r.people_count for r, _ in sender.records] == [6, 8]
    assert [(p.timestamp, p.horizon_minutes, p.predicted_count) for p in sender.predictions] == [
        (minute(0), 5, 6), (minute(0), 15, 6), (minute(0), 30, 6),
        (minute(1), 5, 8), (minute(1), 15, 8), (minute(1), 30, 8),
    ]
    assert worker.stats.predictions_sent == 6
