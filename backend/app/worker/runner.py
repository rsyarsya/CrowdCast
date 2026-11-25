"""Vision worker loop: video frames -> detection -> pipeline -> ingest API.

Three threads so the video stream keeps a steady rate while YOLO is busy:

1. Reader (`run`, main thread): takes paced frames from the source. Every
   stream tick it renders the latest boxes onto the frame and queues the JPEG.
   Every detection tick it puts the frame into a one-slot queue; an older
   frame still waiting there is replaced, so detection never falls behind.
2. Detector (`_detect_loop`): YOLO + CountingPipeline on the newest frame,
   updates the latest boxes and live state, and queues live state and records.
3. Sender (`_send_loop`): uploads frames, live state, and records. Records
   that fail to upload stay buffered and are retried; frames and live state
   are dropped on failure because a newer one follows soon.

The pieces only depend on small callables (detector, encoder, client), so the
loop can be tested with fakes and without torch, OpenCV, or a running API.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from app.services.vision.classifier import StatusThresholds, classify
from app.services.vision.pipeline import CountingPipeline
from app.services.vision.types import Box, CrowdStatus, IntervalRecord, LiveState

logger = logging.getLogger(__name__)

Frame = Any  # numpy array (H, W, 3) in production; anything with .shape in tests
Detector = Callable[[Frame], list[Box]]
Encoder = Callable[[Frame, list[Box], LiveState | None], bytes]


class Sender(Protocol):
    def post_records(self, records: list[tuple[IntervalRecord, CrowdStatus]]) -> None: ...
    def put_live(self, live: LiveState) -> None: ...
    def put_frame(self, jpeg: bytes) -> None: ...


@dataclass
class WorkerStats:
    frames_read: int = 0
    frames_sent: int = 0
    detections: int = 0
    records_sent: int = 0
    send_errors: int = 0
    last_error: str = ""
    started: float = field(default_factory=time.monotonic)


class VisionWorker:
    def __init__(
        self,
        detector: Detector,
        encoder: Encoder,
        sender: Sender,
        pipeline: CountingPipeline,
        thresholds: StatusThresholds,
        detect_interval_s: float = 0.5,
        stream_interval_s: float = 0.1,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.detector = detector
        self.encoder = encoder
        self.sender = sender
        self.pipeline = pipeline
        self.thresholds = thresholds
        self.detect_interval_s = detect_interval_s
        self.stream_interval_s = stream_interval_s
        self.now = now
        self.stats = WorkerStats()

        self._lock = threading.Lock()
        self._boxes: list[Box] = []
        self._live: LiveState | None = None
        self._detect_slot: queue.Queue[Frame] = queue.Queue(maxsize=1)
        # Frames and live state: bounded, oldest dropped. Records: unbounded, never dropped.
        self._outbox: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=20)
        self._records: queue.Queue[IntervalRecord] = queue.Queue()
        self._pending_records: list[tuple[IntervalRecord, CrowdStatus]] = []
        self._next_detect = 0.0
        self._next_stream = 0.0
        self._stop = threading.Event()

    # Reader side -----------------------------------------------------------

    def handle_frame(self, frame: Frame, t: float) -> None:
        """Called for every source frame at video time `t` (seconds, monotonic)."""
        self.stats.frames_read += 1
        if t >= self._next_detect:
            self._next_detect = t + self.detect_interval_s
            _put_latest(self._detect_slot, frame)
        if t >= self._next_stream:
            self._next_stream = t + self.stream_interval_s
            with self._lock:
                boxes, live = list(self._boxes), self._live
            self._enqueue(("frame", self.encoder(frame, boxes, live)))

    # Detector side ---------------------------------------------------------

    def detect_once(self, frame: Frame) -> None:
        boxes = self.detector(frame)
        h, w = frame.shape[:2]
        live, record = self.pipeline.process(self.now(), boxes, w, h)
        self.stats.detections += 1
        with self._lock:
            self._boxes, self._live = boxes, live
        self._enqueue(("live", live))
        if record is not None:
            self._records.put(record)

    def flush_pipeline(self) -> None:
        """Send the unfinished interval, e.g. when the worker stops."""
        record = self.pipeline.flush()
        if record is not None:
            self._records.put(record)

    # Sender side -----------------------------------------------------------

    def send_pending(self, max_items: int | None = None) -> None:
        """Upload queued items once. Called repeatedly by the sender thread."""
        handled = 0
        while max_items is None or handled < max_items:
            try:
                kind, payload = self._outbox.get_nowait()
            except queue.Empty:
                break
            handled += 1
            try:
                if kind == "frame":
                    self.sender.put_frame(payload)
                    self.stats.frames_sent += 1
                else:
                    self.sender.put_live(payload)
            except Exception as exc:  # network errors must not stop the worker
                self._note_error(exc)
        while True:
            try:
                record = self._records.get_nowait()
            except queue.Empty:
                break
            # Stored history uses the plain status of the interval mean (no dwell).
            self._pending_records.append((record, classify(record.people_count, self.thresholds)))
        if self._pending_records:
            try:
                self.sender.post_records(self._pending_records)
                self.stats.records_sent += len(self._pending_records)
                self._pending_records = []
            except Exception as exc:
                self._note_error(exc)

    @property
    def pending_records(self) -> int:
        return len(self._pending_records)

    # Threads ---------------------------------------------------------------

    def run(self, frames: Iterable[tuple[Frame, float]], log_every_s: float = 30.0) -> None:
        threads = [
            threading.Thread(target=self._detect_loop, name="detector", daemon=True),
            threading.Thread(target=self._send_loop, name="sender", daemon=True),
        ]
        for thread in threads:
            thread.start()
        next_log = time.monotonic() + log_every_s
        try:
            for frame, t in frames:
                if self._stop.is_set():
                    break
                self.handle_frame(frame, t)
                if time.monotonic() >= next_log:
                    next_log += log_every_s
                    self._log_stats()
        finally:
            self._stop.set()
            for thread in threads:
                thread.join(timeout=10)
            self.flush_pipeline()
            self.send_pending()
            if self._pending_records:
                logger.warning("%d records could not be sent", len(self._pending_records))

    def stop(self) -> None:
        self._stop.set()

    def _detect_loop(self) -> None:
        while not self._stop.is_set():
            try:
                frame = self._detect_slot.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self.detect_once(frame)
            except Exception:
                logger.exception("Detection failed")

    def _send_loop(self) -> None:
        while not self._stop.is_set():
            self.send_pending()
            # Back off while the API is unreachable; otherwise poll often.
            time.sleep(2.0 if self._pending_records else 0.02)

    def _enqueue(self, item: tuple[str, Any]) -> None:
        _put_latest(self._outbox, item)

    def _note_error(self, exc: Exception) -> None:
        self.stats.send_errors += 1
        message = f"{type(exc).__name__}: {exc}"
        if message != self.stats.last_error:
            logger.warning("Upload failed: %s", message)
        self.stats.last_error = message

    def _log_stats(self) -> None:
        elapsed = time.monotonic() - self.stats.started
        live = self._live
        logger.info(
            "read %.1f fps, detect %.1f/s, sent %d frames, %d records, %d errors, live=%s",
            self.stats.frames_read / elapsed,
            self.stats.detections / elapsed,
            self.stats.frames_sent,
            self.stats.records_sent,
            self.stats.send_errors,
            f"{live.raw_count} ({live.crowd_status})" if live else "-",
        )


def _put_latest(q: queue.Queue, item: Any) -> None:
    """Put without blocking; when full, drop the oldest item (single consumer)."""
    while True:
        try:
            q.put_nowait(item)
            return
        except queue.Full:
            try:
                q.get_nowait()
            except queue.Empty:
                pass
