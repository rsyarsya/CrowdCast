from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.vision.classifier import StatusThresholds
from app.services.vision.pipeline import CountingPipeline
from app.services.vision.types import Box
from app.worker.runner import VisionWorker

T0 = datetime(2026, 11, 25, 16, 0, tzinfo=timezone.utc)
FRAME = SimpleNamespace(shape=(100, 100, 3))


class FakeClock:
    def __init__(self) -> None:
        self.value = T0

    def __call__(self) -> datetime:
        return self.value


class FakeSender:
    def __init__(self) -> None:
        self.frames: list[bytes] = []
        self.live = []
        self.records = []
        self.fail = False

    def _check(self) -> None:
        if self.fail:
            raise ConnectionError("API down")

    def put_frame(self, jpeg: bytes) -> None:
        self._check()
        self.frames.append(jpeg)

    def put_live(self, live) -> None:
        self._check()
        self.live.append(live)

    def post_records(self, records) -> None:
        self._check()
        self.records.extend(records)


def make_worker(counts: list[int], sender: FakeSender, clock: FakeClock) -> VisionWorker:
    remaining = iter(counts)

    def detector(_frame) -> list[Box]:
        n = next(remaining)
        return [Box(i, 60, i + 1, 80) for i in range(n)]

    thresholds = StatusThresholds(4, 8)
    return VisionWorker(
        detector=detector,
        encoder=lambda _frame, boxes, live: f"{len(boxes)}".encode(),
        sender=sender,
        pipeline=CountingPipeline(thresholds, smoothing_window_s=1, interval_s=60, status_dwell_s=0),
        thresholds=thresholds,
        detect_interval_s=0.5,
        stream_interval_s=0.1,
        now=clock,
    )


def test_reader_throttles_detection_and_stream():
    worker = make_worker([], FakeSender(), FakeClock())
    for i in range(30):  # 1 second of 30 fps video
        worker.handle_frame(FRAME, i / 30)
    assert worker._detect_slot.qsize() == 1  # only the newest frame waits for YOLO
    assert worker._outbox.qsize() == 10  # 10 fps stream


def test_detection_produces_live_state_and_minute_records():
    sender, clock = FakeSender(), FakeClock()
    worker = make_worker([3] * 4 + [9] * 4, sender, clock)
    for _ in range(8):  # 4 samples in minute 0, 4 samples in minute 1
        worker.detect_once(FRAME)
        clock.value += timedelta(seconds=15)
    worker.flush_pipeline()
    worker.send_pending()

    assert [live.raw_count for live in sender.live][-1] == 9
    assert sender.live[-1].crowd_status == "Ramai"
    assert [(r.start, r.people_count, status) for r, status in sender.records] == [
        (T0, 3, "Sepi"),
        (T0 + timedelta(minutes=1), 9, "Ramai"),
    ]


def test_records_are_kept_and_retried_when_api_is_down():
    sender, clock = FakeSender(), FakeClock()
    worker = make_worker([5] * 5, sender, clock)
    sender.fail = True
    for _ in range(5):
        worker.detect_once(FRAME)
        clock.value += timedelta(seconds=20)  # crosses a minute boundary
    worker.send_pending()
    assert worker.pending_records == 1
    assert worker.stats.send_errors >= 1

    sender.fail = False
    worker.send_pending()
    assert worker.pending_records == 0
    assert [r.people_count for r, _ in sender.records] == [5]


def test_full_outbox_drops_oldest_frames():
    worker = make_worker([], FakeSender(), FakeClock())
    for i in range(100):
        worker._enqueue(("frame", str(i).encode()))
    assert worker._outbox.qsize() == 20
    assert worker._outbox.get_nowait() == ("frame", b"80")
