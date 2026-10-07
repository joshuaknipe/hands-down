"""Open the webcam with an explicit OpenCV backend per OS, and tell real frames from empty ones."""

import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

import cv2
import numpy as np


@dataclass(frozen=True)
class Backend:
    name: str
    api: int


DSHOW = Backend("dshow", cv2.CAP_DSHOW)
MSMF = Backend("msmf", cv2.CAP_MSMF)
AVFOUNDATION = Backend("avfoundation", cv2.CAP_AVFOUNDATION)
ANY = Backend("any", cv2.CAP_ANY)
_BY_NAME = {b.name: b for b in (DSHOW, MSMF, AVFOUNDATION, ANY)}


def backends_for_platform(platform: str = sys.platform) -> list[Backend]:
    """Backends to try, best first. DirectShow opens faster than Media Foundation on most Windows webcams."""
    if platform == "win32":
        return [DSHOW, MSMF]
    if platform == "darwin":
        return [AVFOUNDATION]
    return [ANY]


def backend_by_name(name: str) -> Backend:
    try:
        return _BY_NAME[name]
    except KeyError:
        raise ValueError(f"Unknown camera backend {name!r}; expected one of {sorted(_BY_NAME)}") from None


# Busy or warming-up cameras often deliver black frames instead of failing the read,
# so a frame darker than this on average counts as black.
BLACK_MEAN_THRESHOLD = 8.0


def is_black(frame: np.ndarray | None) -> bool:
    return frame is None or frame.size == 0 or float(frame.mean()) < BLACK_MEAN_THRESHOLD


def classify(ok: bool, frame: np.ndarray | None) -> str:
    """Classify one read as "good", "black" or "failed"."""
    if not ok or frame is None:
        return "failed"
    return "black" if is_black(frame) else "good"


# Reads allowed for a newly opened camera to deliver its first non-black frame.
WARMUP_READS = 30


@dataclass
class OpenResult:
    backend: str
    ok: bool
    seconds: float  # from the open call to the first good frame, or to giving up
    capture: Any = None  # the opened capture or frame source, when ok
    error: str = ""


def open_camera(
    index: int,
    backend: Backend,
    width: int = 640,
    height: int = 480,
    capture_factory: Callable[[int, int], Any] = cv2.VideoCapture,
    clock: Callable[[], float] = time.monotonic,
) -> OpenResult:
    """Open camera `index` with `backend` and wait for a real frame. Never raises."""
    start = clock()
    try:
        capture = capture_factory(index, backend.api)
    except Exception as exc:  # some backends raise instead of returning a closed capture
        return OpenResult(backend.name, False, clock() - start, error=f"open raised: {exc}")
    if not capture.isOpened():
        capture.release()
        return OpenResult(backend.name, False, clock() - start, error="camera did not open")
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    for _ in range(WARMUP_READS):
        ok, frame = capture.read()
        if classify(ok, frame) == "good":
            return OpenResult(backend.name, True, clock() - start, capture=capture)
    capture.release()
    return OpenResult(
        backend.name, False, clock() - start,
        error=f"opened, but no non-black frame in {WARMUP_READS} reads",
    )


class OpenCvSource:
    """Adapts an OpenCV capture to the read_status() interface used by reader threads."""

    def __init__(self, capture):
        self.capture = capture

    def read_status(self) -> str:
        ok, frame = self.capture.read()
        return classify(ok, frame)

    def close(self) -> None:
        self.capture.release()


@dataclass(frozen=True)
class FlowStats:
    good: int = 0
    black: int = 0
    failed: int = 0
    max_gap_s: float = 0.0  # longest stretch without a good frame, including one still running


class FrameMonitor:
    """Thread-safe tally of reads. A read that hangs shows up as a growing gap, since snapshot() measures to now."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._counts = {"good": 0, "black": 0, "failed": 0}
        self._last_good = clock()
        self._max_gap = 0.0

    def record(self, status: str) -> None:
        now = self._clock()
        with self._lock:
            self._counts[status] += 1
            self._max_gap = max(self._max_gap, now - self._last_good)
            if status == "good":
                self._last_good = now

    def snapshot(self) -> FlowStats:
        now = self._clock()
        with self._lock:
            gap = max(self._max_gap, now - self._last_good)
            return FlowStats(self._counts["good"], self._counts["black"], self._counts["failed"], gap)


def start_reader(source, monitor: FrameMonitor, stop: threading.Event) -> threading.Thread:
    """Read from `source` on a daemon thread until `stop` is set, recording each read in `monitor`."""

    def loop() -> None:
        while not stop.is_set():
            try:
                status = source.read_status()
            except Exception:
                status = "failed"
            if status is None:
                stop.wait(0.01)  # no new frame yet
                continue
            monitor.record(status)
            if status == "failed":
                stop.wait(0.05)

    thread = threading.Thread(target=loop, name="camera-reader", daemon=True)
    thread.start()
    return thread


def stop_reader(thread: threading.Thread, stop: threading.Event, source, timeout: float = 3.0) -> bool:
    """Stop the reader and close the source. Returns False if a read is stuck in the driver.

    A stuck source is left open: releasing a capture while another thread is blocked
    inside its read() can crash the process.
    """
    stop.set()
    thread.join(timeout)
    if thread.is_alive():
        return False
    source.close()
    return True
