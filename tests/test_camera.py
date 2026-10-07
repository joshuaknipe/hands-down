import threading

import numpy as np
import pytest

from handsdown import camera
from handsdown.camera import FlowStats, FrameMonitor
from tests.helpers import FakeCapture, FakeClock

BLACK = np.zeros((480, 640, 3), np.uint8)
GREY = np.full((480, 640, 3), 128, np.uint8)


@pytest.mark.parametrize("platform, names", [
    ("win32", ["dshow", "msmf"]),
    ("darwin", ["avfoundation"]),
    ("linux", ["any"]),
])
def test_backends_for_platform(platform, names):
    assert [b.name for b in camera.backends_for_platform(platform)] == names


def test_backend_by_name_rejects_unknown():
    assert camera.backend_by_name("msmf") is camera.MSMF
    with pytest.raises(ValueError, match="v4l"):
        camera.backend_by_name("v4l")


def test_is_black_and_classify():
    assert camera.is_black(BLACK)
    assert camera.is_black(None)
    assert camera.is_black(np.zeros((0, 0, 3), np.uint8))
    assert not camera.is_black(GREY)
    assert camera.classify(True, GREY) == "good"
    assert camera.classify(True, BLACK) == "black"
    assert camera.classify(False, None) == "failed"
    assert camera.classify(True, None) == "failed"


def test_open_camera_waits_through_black_warmup_frames():
    cap = FakeCapture(reads=[(True, BLACK)] * 5 + [(True, GREY)])
    result = camera.open_camera(0, camera.DSHOW, capture_factory=lambda i, api: cap)
    assert result.ok and result.capture is cap and result.backend == "dshow"
    assert not cap.released


def test_open_camera_reports_a_camera_that_does_not_open():
    cap = FakeCapture(opened=False)
    result = camera.open_camera(0, camera.MSMF, capture_factory=lambda i, api: cap)
    assert not result.ok and result.error == "camera did not open"
    assert cap.released


def test_open_camera_fails_when_every_frame_is_black():
    cap = FakeCapture(reads=[(True, BLACK)] * camera.WARMUP_READS)
    result = camera.open_camera(0, camera.DSHOW, capture_factory=lambda i, api: cap)
    assert not result.ok and "no non-black frame" in result.error
    assert cap.released


def test_open_camera_never_raises():
    def explode(index, api):
        raise RuntimeError("driver error")

    result = camera.open_camera(0, camera.DSHOW, capture_factory=explode)
    assert not result.ok and "driver error" in result.error


def test_open_camera_times_until_first_good_frame():
    clock = FakeClock()

    class SlowCapture(FakeCapture):
        def read(self):
            clock.now += 0.5
            return super().read()

    cap = SlowCapture(reads=[(True, BLACK), (True, GREY)])
    result = camera.open_camera(0, camera.DSHOW, capture_factory=lambda i, api: cap, clock=clock)
    assert result.seconds == pytest.approx(1.0)


def test_monitor_counts_and_tracks_longest_gap():
    clock = FakeClock()
    monitor = FrameMonitor(clock)
    clock.now = 0.1
    monitor.record("good")
    clock.now = 0.2
    monitor.record("black")
    clock.now = 2.1
    monitor.record("good")
    clock.now = 2.2
    monitor.record("failed")
    stats = monitor.snapshot()
    assert (stats.good, stats.black, stats.failed) == (2, 1, 1)
    assert stats.max_gap_s == pytest.approx(2.0)


def test_monitor_snapshot_counts_a_hung_read_as_a_gap():
    clock = FakeClock()
    monitor = FrameMonitor(clock)
    clock.now = 0.5
    monitor.record("good")
    clock.now = 10.5  # no reads since: the reader is blocked inside the driver
    assert monitor.snapshot().max_gap_s == pytest.approx(10.0)


class CountingSource:
    def __init__(self):
        self.closed = False

    def read_status(self):
        threading.Event().wait(0.001)
        return "good"

    def close(self):
        self.closed = True


def test_reader_thread_feeds_monitor_and_closes_source():
    source = CountingSource()
    monitor = FrameMonitor()
    stop = threading.Event()
    thread = camera.start_reader(source, monitor, stop)
    threading.Event().wait(0.05)
    assert camera.stop_reader(thread, stop, source)
    assert monitor.snapshot().good > 0
    assert source.closed


def test_stop_reader_gives_up_on_a_hung_read_without_closing():
    release = threading.Event()

    class HungSource(CountingSource):
        def read_status(self):
            release.wait()
            return "good"

    source = HungSource()
    stop = threading.Event()
    thread = camera.start_reader(source, FrameMonitor(), stop)
    assert not camera.stop_reader(thread, stop, source, timeout=0.1)
    assert not source.closed
    release.set()
    thread.join(1)


def test_opencv_source_classifies_reads():
    source = camera.OpenCvSource(FakeCapture(reads=[(True, GREY), (True, BLACK)]))
    assert [source.read_status() for _ in range(3)] == ["good", "black", "failed"]
    source.close()
    assert source.capture.released


def test_probe_line_formats_rates():
    from feasibility.probe import probe_line

    line = probe_line("dshow", 0.84, "640x480", FlowStats(good=90, black=2, failed=1, max_gap_s=0.3), 3.0)
    assert line == "dshow         opened in 0.8 s at 640x480, 30 fps good, 2 black, 1 failed, longest gap 0.3 s"
