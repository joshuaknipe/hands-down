# Milestone 1 (Feasibility) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A command-line tool, run from source on her Windows 11 laptop, that answers milestone 1's two go / no-go questions: does MediaPipe find her hand during real motions at her camera angle, and can Halo and the Teams desktop app use the camera at the same time?

**Architecture:** Two packages. `halo/` holds code that later milestones keep: resource paths, camera opening and frame-flow monitoring, and the MediaPipe tracker. `feasibility/` holds milestone-1-only tools behind `python -m feasibility <command>`: `probe` (camera backends), `coexist` (guided Teams test in both launch orders), `record` (labelled clips with live tracking) and `analyse` (hand-visibility stats and verdict). Anything that touches hardware is a thin wrapper around logic that is unit-tested with fakes.

**Tech Stack:** Python 3.12, MediaPipe 1.1.0 (Tasks API, VIDEO mode), OpenCV 5 (`opencv-contrib-python`, pulled in by MediaPipe), pywinrt 3.2.1 (Windows only, shared camera probe), pytest 9, GitHub Actions (windows-latest).

**Spec:** [plan.md](../../../plan.md), section "Milestones", item 1, plus "Camera sharing and calls" and "Privacy and testing".

## Global Constraints

- Python 3.12 on both the Mac and her laptop.
- `mediapipe==1.1.0`. It depends on `opencv-contrib-python`; never install `opencv-python` as well, because both provide the `cv2` module and conflict.
- Use only the MediaPipe Tasks API (`mediapipe.tasks.python.vision`). `mp.solutions` does not exist in MediaPipe 1.x.
- MediaPipe VIDEO mode raises `ValueError: Input timestamp must be monotonically increasing` on any repeated or backwards timestamp; every call goes through `TimestampGuard`.
- No network calls at runtime. Model files are committed under `models/` and loaded through `halo.paths.model_path`.
- Video files and reports are never committed. `.gitignore` covers `clips/`, `reports/` and video extensions.
- Nothing user-visible names the habit. Clip labels describe where the hand is (`hair_scalp`), not the behaviour.
- `halo/` never imports from `feasibility/`.
- pathlib everywhere; no hard-coded path separators.
- All timings in seconds or milliseconds of wall-clock time, never frame counts.

## Review Focus

1. **Camera opens but delivers only black frames** (common on DirectShow when Teams holds the camera). This must count as a failure, not a successful open. Test: `test_open_camera_fails_when_every_frame_is_black` (Task 2).
2. **A camera read blocks forever while Teams takes the camera.** The coexistence trial must still finish and report the stall as a long gap, not hang. Tests: `test_monitor_snapshot_counts_a_hung_read_as_a_gap` and `test_stop_reader_gives_up_on_a_hung_read_without_closing` (Task 2).
3. **Repeated or backwards frame timestamps** reach MediaPipe and crash analysis. They must be nudged forward. Tests: `test_guard_nudges_repeated_and_backwards_timestamps` and `test_tracker_accepts_repeated_timestamps` (Task 3).
4. **An interrupted recording or a crash leaves orphan or corrupt files** in `clips/`. Analysis must skip them with a warning, not crash. Tests: `test_load_clips_skips_orphans_and_corrupt_metadata` (Task 4), `test_short_recording_is_discarded` (Task 5).
5. **The video's frame count disagrees with the recorded timestamps** (writer dropped frames, or the camera changed resolution mid-clip). Analysis must use the shorter of the two and report the mismatch. Tests: `test_recorder_resizes_frames_to_writer_size` (Task 5), `test_analyse_clip_reports_extra_and_missing_frames` (Task 7).

---

## File structure

```
requirements.txt             pinned runtime dependencies
requirements-dev.txt         runtime + pytest
pyproject.toml               pytest configuration only
.gitattributes               mark model files as binary
models/
  hand_landmarker.task       MediaPipe hand model (committed)
  face_landmarker.task       MediaPipe face model (committed)
  SHA256SUMS                 expected hashes
  SOURCES.md                 where the models came from
halo/
  __init__.py
  paths.py                   resource_path / model_path, works from source and frozen builds
  camera.py                  backends per OS, open_camera, frame classification, FrameMonitor, reader thread
  landmarks.py               TimestampGuard, Observation, Tracker (hand + face, VIDEO mode)
feasibility/
  __init__.py
  __main__.py                argparse CLI: probe, coexist, record, analyse
  probe.py                   open each backend and report frame flow
  clips.py                   labels, clip metadata, saving and loading clips
  record.py                  ClipRecorder, preview overlay, interactive record loop
  stats.py                   per-clip stats and the go / no-go verdict
  analyse.py                 run the tracker over saved clips, print table, write report
  report.py                  write JSON reports to reports/
  coexist.py                 guided Teams coexistence trials and conclusion
  winrt_probe.py             Windows shared camera access via WinRT MediaCapture
tests/
  __init__.py
  helpers.py                 FakeClock, FakeCapture, ScriptedAsk shared by tests
  test_paths.py
  test_camera.py
  test_landmarks.py
  test_clips.py
  test_record.py
  test_stats.py
  test_analyse.py
  test_coexist.py
  test_winrt_probe.py
docs/milestone-1-runbook.md  step-by-step guide for running milestone 1 on her laptop
.github/workflows/tests.yml  run the test suite on windows-latest
```

---

### Task 1: Project scaffold, models and resource paths

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `.gitattributes`
- Create: `models/hand_landmarker.task`, `models/face_landmarker.task`, `models/SHA256SUMS`, `models/SOURCES.md`
- Create: `halo/__init__.py`, `halo/paths.py`
- Create: `tests/__init__.py`, `tests/helpers.py`, `tests/test_paths.py`
- Modify: `.gitignore` (add `reports/`)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `halo.paths.PROJECT_ROOT: Path`
  - `halo.paths.resource_path(relative: str) -> Path`
  - `halo.paths.model_path(name: str) -> Path` (raises `FileNotFoundError` naming the path)
  - `halo.paths.clips_dir() -> Path`, `halo.paths.reports_dir() -> Path`
  - `tests.helpers.FakeClock` (callable; set `.now` to move time)

- [ ] **Step 1: Add dependency and config files**

`requirements.txt`:

```
mediapipe==1.1.0
opencv-contrib-python==5.0.0.93
numpy==2.5.3
winrt-runtime==3.2.1; sys_platform == "win32"
winrt-Windows.Foundation==3.2.1; sys_platform == "win32"
winrt-Windows.Foundation.Collections==3.2.1; sys_platform == "win32"
winrt-Windows.Media.Capture==3.2.1; sys_platform == "win32"
winrt-Windows.Media.Capture.Frames==3.2.1; sys_platform == "win32"
```

`requirements-dev.txt`:

```
-r requirements.txt
pytest==9.1.1
```

`pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`.gitattributes`:

```
*.task binary
```

Append to `.gitignore`, under the "Recorded clips and logs" comment:

```
reports/
```

- [ ] **Step 2: Create the virtual environment and install**

Run:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -c "import mediapipe, cv2; print(mediapipe.__version__, cv2.__version__)"
```

Expected: `1.1.0 5.0.0`

- [ ] **Step 3: Download the models and record their hashes**

Run:

```bash
mkdir -p models
for m in hand_landmarker face_landmarker; do
  curl -sfL -o models/$m.task https://storage.googleapis.com/mediapipe-models/$m/$m/float16/latest/$m.task
done
cat > models/SHA256SUMS <<'EOF'
fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1  hand_landmarker.task
64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff  face_landmarker.task
EOF
(cd models && shasum -a 256 -c SHA256SUMS)
```

Expected: both lines end in `OK`. If a hash differs, Google has replaced the "latest" model since this plan was written; stop and tell your human partner rather than editing the hash.

`models/SOURCES.md`:

```markdown
# Model files

Downloaded 2026-10-07 from Google's MediaPipe model storage (float16, "latest").
They are committed so builds are reproducible and Halo makes no network calls.

| File | Source |
| --- | --- |
| hand_landmarker.task | https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task |
| face_landmarker.task | https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task |

Expected hashes are in `SHA256SUMS`; `tests/test_paths.py` checks them.
```

- [ ] **Step 4: Write the failing tests**

`tests/__init__.py`: empty file.

`tests/helpers.py`:

```python
"""Fakes shared by the test suite."""


class FakeClock:
    """A clock that only moves when a test sets `now`."""

    def __init__(self, now: float = 0.0):
        self.now = now

    def __call__(self) -> float:
        return self.now
```

`tests/test_paths.py`:

```python
import hashlib
import sys

import pytest

from halo import paths


def test_resource_path_from_source_is_under_project_root():
    assert paths.resource_path("models/hand_landmarker.task") == (
        paths.PROJECT_ROOT / "models" / "hand_landmarker.task"
    )


def test_resource_path_when_frozen_uses_pyinstaller_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert paths.resource_path("models/x.task") == tmp_path / "models" / "x.task"


def test_bundled_models_match_recorded_hashes():
    lines = (paths.PROJECT_ROOT / "models" / "SHA256SUMS").read_text().splitlines()
    assert len(lines) == 2
    for line in lines:
        expected, name = line.split()
        digest = hashlib.sha256(paths.model_path(name).read_bytes()).hexdigest()
        assert digest == expected, name


def test_missing_model_raises_with_path():
    with pytest.raises(FileNotFoundError, match="nope.task"):
        paths.model_path("nope.task")


def test_data_folders_are_under_project_root():
    assert paths.clips_dir() == paths.PROJECT_ROOT / "clips"
    assert paths.reports_dir() == paths.PROJECT_ROOT / "reports"
```

- [ ] **Step 5: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_paths.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'halo'`

- [ ] **Step 6: Implement `halo/paths.py`**

`halo/__init__.py`: empty file.

`halo/paths.py`:

```python
"""Locate bundled resources and developer data folders, from source or from a frozen build."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resource_root() -> Path:
    """Folder holding bundled files: PyInstaller's unpack folder when frozen, else the project root."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return PROJECT_ROOT


def resource_path(relative: str) -> Path:
    return resource_root() / relative


def model_path(name: str) -> Path:
    path = resource_path(f"models/{name}")
    if not path.is_file():
        raise FileNotFoundError(f"Model file not found: {path}")
    return path


def clips_dir() -> Path:
    return PROJECT_ROOT / "clips"


def reports_dir() -> Path:
    return PROJECT_ROOT / "reports"
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_paths.py -v`
Expected: 5 passed

- [ ] **Step 8: Commit**

```bash
git add requirements.txt requirements-dev.txt pyproject.toml .gitattributes .gitignore models halo tests
git commit -m "Add project scaffold, MediaPipe models and resource paths"
```

---

### Task 2: Camera opening, frame-flow monitoring and the probe command

**Files:**
- Create: `halo/camera.py`
- Create: `feasibility/__init__.py`, `feasibility/__main__.py`, `feasibility/probe.py`
- Modify: `tests/helpers.py` (add `FakeCapture`)
- Test: `tests/test_camera.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `halo.camera.Backend(name: str, api: int)` and constants `DSHOW`, `MSMF`, `AVFOUNDATION`, `ANY`
  - `halo.camera.backends_for_platform(platform: str = sys.platform) -> list[Backend]`
  - `halo.camera.backend_by_name(name: str) -> Backend` (raises `ValueError`)
  - `halo.camera.is_black(frame) -> bool`, `halo.camera.classify(ok: bool, frame) -> str` returning `"good" | "black" | "failed"`
  - `halo.camera.OpenResult(backend: str, ok: bool, seconds: float, capture: Any = None, error: str = "")`
  - `halo.camera.open_camera(index, backend, width=640, height=480, capture_factory=cv2.VideoCapture, clock=time.monotonic) -> OpenResult` (`capture` is the raw `cv2.VideoCapture`)
  - `halo.camera.OpenCvSource(capture)` with `read_status() -> str` and `close()`
  - `halo.camera.FlowStats(good: int, black: int, failed: int, max_gap_s: float)` (frozen dataclass)
  - `halo.camera.FrameMonitor(clock=time.monotonic)` with `record(status: str)` and `snapshot() -> FlowStats`
  - `halo.camera.start_reader(source, monitor, stop: threading.Event) -> threading.Thread`
  - `halo.camera.stop_reader(thread, stop, source, timeout: float = 3.0) -> bool`
  - A frame source is any object with `read_status() -> str | None` (`None` means no new frame yet) and `close()`.
  - CLI: `python -m feasibility probe [--camera N] [--seconds S]`

- [ ] **Step 1: Add `FakeCapture` to `tests/helpers.py`**

Append:

```python
class FakeCapture:
    """Stands in for cv2.VideoCapture: replays a list of (ok, frame) reads."""

    def __init__(self, opened: bool = True, reads=()):
        self.opened = opened
        self.reads = list(reads)
        self.released = False
        self.props = {}

    def isOpened(self) -> bool:
        return self.opened

    def set(self, prop, value) -> bool:
        self.props[prop] = value
        return True

    def read(self):
        if not self.reads:
            return False, None
        return self.reads.pop(0)

    def release(self) -> None:
        self.released = True
```

- [ ] **Step 2: Write the failing tests**

`tests/test_camera.py`:

```python
import threading

import numpy as np
import pytest

from halo import camera
from halo.camera import FlowStats, FrameMonitor
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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_camera.py -v`
Expected: FAIL with `ImportError: cannot import name 'camera' from 'halo'`

- [ ] **Step 4: Implement `halo/camera.py`**

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_camera.py -v`
Expected: all passed

- [ ] **Step 6: Implement the probe command**

`feasibility/__init__.py`: empty file.

`feasibility/probe.py`:

```python
"""Open the camera with each backend for this OS and report how well frames flow."""

import threading
import time

import cv2

from halo.camera import Backend, FlowStats, FrameMonitor, OpenCvSource, open_camera, start_reader, stop_reader


def probe_line(name: str, open_seconds: float, size: str, flow: FlowStats, seconds: float) -> str:
    return (
        f"{name:<13} opened in {open_seconds:.1f} s at {size}, {flow.good / seconds:.0f} fps good, "
        f"{flow.black} black, {flow.failed} failed, longest gap {flow.max_gap_s:.1f} s"
    )


def run_probe(camera_index: int, backends: list[Backend], seconds: float, say=print) -> int:
    any_ok = False
    for backend in backends:
        result = open_camera(camera_index, backend)
        if not result.ok:
            say(f"{backend.name:<13} FAILED after {result.seconds:.1f} s: {result.error}")
            continue
        any_ok = True
        capture = result.capture
        size = f"{int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))}"
        source = OpenCvSource(capture)
        monitor = FrameMonitor()
        stop = threading.Event()
        thread = start_reader(source, monitor, stop)
        time.sleep(seconds)
        flow = monitor.snapshot()
        if not stop_reader(thread, stop, source):
            say(f"{backend.name:<13} warning: camera read is stuck; restart before trying again")
        say(probe_line(backend.name, result.seconds, size, flow, seconds))
    return 0 if any_ok else 1
```

Add one test to `tests/test_camera.py`:

```python
def test_probe_line_formats_rates():
    from feasibility.probe import probe_line

    line = probe_line("dshow", 0.84, "640x480", FlowStats(good=90, black=2, failed=1, max_gap_s=0.3), 3.0)
    assert line == "dshow         opened in 0.8 s at 640x480, 30 fps good, 2 black, 1 failed, longest gap 0.3 s"
```

`feasibility/__main__.py`:

```python
"""Milestone 1 feasibility tools. Run: python -m feasibility <command> --help"""

import argparse
import os
import sys

os.environ.setdefault("GLOG_minloglevel", "2")  # quieten MediaPipe's C++ logging

from halo.camera import backends_for_platform


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m feasibility", description="Halo milestone 1 feasibility tools")
    sub = parser.add_subparsers(dest="command", required=True)

    probe = sub.add_parser("probe", help="Open the camera with each backend and report frame flow")
    probe.add_argument("--camera", type=int, default=0, help="camera index (default 0)")
    probe.add_argument("--seconds", type=float, default=3.0, help="how long to read from each backend")

    args = parser.parse_args(argv)

    if args.command == "probe":
        from feasibility.probe import run_probe

        return run_probe(args.camera, backends_for_platform(), args.seconds)
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7: Run all tests, then probe the Mac webcam**

Run: `.venv/bin/python -m pytest -v`
Expected: all passed

Run: `.venv/bin/python -m feasibility probe`
Expected: one `avfoundation` line showing it opened, a resolution, and a frame rate above 10 fps. macOS may ask for camera permission for your terminal or IDE the first time; allow it and run again.

- [ ] **Step 8: Commit**

```bash
git add halo/camera.py feasibility tests
git commit -m "Add camera opening, frame-flow monitoring and probe command"
```

---

### Task 3: Hand and face tracker

**Files:**
- Create: `halo/landmarks.py`
- Test: `tests/test_landmarks.py`

**Interfaces:**
- Consumes: `halo.paths.model_path(name) -> Path`
- Produces:
  - `halo.landmarks.Observation(timestamp_ms: int, hands: tuple[tuple[tuple[float, float], ...], ...], face_found: bool)` (frozen) with property `hand_found -> bool`. Each hand is a tuple of normalised `(x, y)` landmarks, 0–1 across the frame.
  - `halo.landmarks.TimestampGuard()` with `next(timestamp_ms: int) -> int`
  - `halo.landmarks.Tracker(num_hands: int = 2)`: context manager with `process(frame_bgr: np.ndarray, timestamp_ms: int) -> Observation` and `close()`

- [ ] **Step 1: Write the failing tests**

`tests/test_landmarks.py`:

```python
import numpy as np

from halo.landmarks import Observation, TimestampGuard, Tracker


def test_guard_passes_increasing_timestamps():
    guard = TimestampGuard()
    assert [guard.next(t) for t in (0, 33, 66)] == [0, 33, 66]


def test_guard_nudges_repeated_and_backwards_timestamps():
    guard = TimestampGuard()
    assert [guard.next(t) for t in (100, 100, 90, 200)] == [100, 101, 102, 200]


def test_observation_hand_found():
    assert Observation(0, (((0.1, 0.2),),), False).hand_found
    assert not Observation(0, (), True).hand_found


def test_tracker_finds_nothing_in_a_blank_frame():
    with Tracker() as tracker:
        observation = tracker.process(np.zeros((480, 640, 3), np.uint8), 0)
    assert not observation.hand_found
    assert not observation.face_found


def test_tracker_accepts_repeated_timestamps():
    frame = np.zeros((480, 640, 3), np.uint8)
    with Tracker() as tracker:
        tracker.process(frame, 0)
        second = tracker.process(frame, 0)  # MediaPipe alone would raise ValueError here
    assert second.timestamp_ms == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_landmarks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'halo.landmarks'`

- [ ] **Step 3: Implement `halo/landmarks.py`**

```python
"""Run MediaPipe's hand and face landmarkers on video frames."""

from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core.base_options import BaseOptions

from halo.paths import model_path

Point = tuple[float, float]


@dataclass(frozen=True)
class Observation:
    timestamp_ms: int
    hands: tuple[tuple[Point, ...], ...]  # per hand, normalised (x, y) landmarks
    face_found: bool

    @property
    def hand_found(self) -> bool:
        return len(self.hands) > 0


class TimestampGuard:
    """MediaPipe VIDEO mode rejects timestamps that do not strictly increase; nudge them forward."""

    def __init__(self):
        self._last: int | None = None

    def next(self, timestamp_ms: int) -> int:
        if self._last is not None and timestamp_ms <= self._last:
            timestamp_ms = self._last + 1
        self._last = timestamp_ms
        return timestamp_ms


class Tracker:
    """Hand and face landmarkers in VIDEO mode, which tracks between frames instead of re-detecting.

    Use one Tracker per video stream: VIDEO mode keeps state between frames.
    """

    def __init__(self, num_hands: int = 2):
        self._hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path("hand_landmarker.task"))),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=num_hands,
        ))
        self._face = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path("face_landmarker.task"))),
            running_mode=vision.RunningMode.VIDEO,
        ))
        self._guard = TimestampGuard()

    def process(self, frame_bgr: np.ndarray, timestamp_ms: int) -> Observation:
        timestamp_ms = self._guard.next(int(timestamp_ms))
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        hands = self._hands.detect_for_video(image, timestamp_ms)
        face = self._face.detect_for_video(image, timestamp_ms)
        return Observation(
            timestamp_ms,
            tuple(tuple((lm.x, lm.y) for lm in hand) for hand in hands.hand_landmarks),
            bool(face.face_landmarks),
        )

    def close(self) -> None:
        self._hands.close()
        self._face.close()

    def __enter__(self) -> "Tracker":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_landmarks.py -v`
Expected: 5 passed (MediaPipe prints some INFO and W lines; ignore them)

- [ ] **Step 5: Commit**

```bash
git add halo/landmarks.py tests/test_landmarks.py
git commit -m "Add hand and face tracker with timestamp guard"
```

---

### Task 4: Clip labels, metadata and storage

**Files:**
- Create: `feasibility/clips.py`
- Test: `tests/test_clips.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `TRUE_POSITIVE_LABELS`, `FALSE_POSITIVE_LABELS`, `LABELS` (tuples of str), `SPLITS = ("dev", "holdout")`, `HOLDOUT_EVERY = 4`
  - `ClipMeta(label: str, split: str, recorded_at: str, backend: str, width: int, height: int, timestamps_ms: list[int])` with `to_json() -> str` and classmethod `from_json(text) -> ClipMeta` (raises `ValueError` or `TypeError` on bad data)
  - `Clip(video: Path, meta: ClipMeta)` (frozen)
  - `assign_split(existing_count: int) -> str`
  - `new_clip_paths(clips_dir: Path, label: str, now: datetime) -> tuple[Path, Path]` (video `.mp4`, metadata `.json`; same stem)
  - `count_clips(clips_dir: Path, label: str) -> int`
  - `save_meta(path: Path, meta: ClipMeta) -> None`
  - `load_clips(clips_dir: Path, warn=print) -> list[Clip]`

- [ ] **Step 1: Write the failing tests**

`tests/test_clips.py`:

```python
from datetime import datetime
from pathlib import Path

import pytest

from feasibility import clips
from feasibility.clips import ClipMeta


def make_meta(label="hair_scalp", split="dev"):
    return ClipMeta(label, split, "2026-10-07T12:00:00", "dshow", 640, 480, [0, 33, 66])


def write_clip(clips_dir: Path, name: str, meta: ClipMeta, video=True, meta_text=None):
    folder = clips_dir / meta.label
    folder.mkdir(parents=True, exist_ok=True)
    if video:
        (folder / f"{name}.mp4").write_bytes(b"video")
    (folder / f"{name}.json").write_text(meta_text if meta_text is not None else meta.to_json())


def test_labels_describe_hand_position_only():
    assert set(clips.TRUE_POSITIVE_LABELS).isdisjoint(clips.FALSE_POSITIVE_LABELS)
    for label in clips.LABELS:
        assert "pull" not in label and "trich" not in label


def test_every_fourth_clip_of_a_label_is_held_out():
    assert [clips.assign_split(n) for n in range(8)] == ["dev", "dev", "dev", "holdout"] * 2


def test_meta_round_trips_through_json():
    meta = make_meta()
    assert ClipMeta.from_json(meta.to_json()) == meta


@pytest.mark.parametrize("change, error", [
    ({"label": "waving"}, ValueError),
    ({"split": "train"}, ValueError),
    ({"timestamps_ms": [0, "x"]}, ValueError),
    ({"surprise": 1}, TypeError),
])
def test_meta_rejects_bad_data(change, error):
    import json

    data = json.loads(make_meta().to_json()) | change
    with pytest.raises(error):
        ClipMeta.from_json(json.dumps(data))


def test_new_clip_paths_share_a_stem_inside_the_label_folder(tmp_path):
    video, meta = clips.new_clip_paths(tmp_path, "hair_crown", datetime(2026, 10, 7, 9, 5, 3, 120000))
    assert video == tmp_path / "hair_crown" / "20261007-090503-120000.mp4"
    assert meta == tmp_path / "hair_crown" / "20261007-090503-120000.json"


def test_count_and_load_clips(tmp_path):
    write_clip(tmp_path, "a", make_meta())
    write_clip(tmp_path, "b", make_meta("chin_rest"))
    assert clips.count_clips(tmp_path, "hair_scalp") == 1
    assert clips.count_clips(tmp_path, "hair_crown") == 0
    loaded = clips.load_clips(tmp_path)
    assert [c.meta.label for c in loaded] == ["chin_rest", "hair_scalp"]
    assert loaded[1].video == tmp_path / "hair_scalp" / "a.mp4"


def test_load_clips_skips_orphans_and_corrupt_metadata(tmp_path):
    write_clip(tmp_path, "good", make_meta())
    write_clip(tmp_path, "no-video", make_meta(), video=False)
    write_clip(tmp_path, "corrupt", make_meta(), meta_text="{not json")
    (tmp_path / "hair_scalp" / "no-meta.mp4").write_bytes(b"video")  # recording crashed before metadata
    warnings = []
    loaded = clips.load_clips(tmp_path, warn=warnings.append)
    assert [c.video.name for c in loaded] == ["good.mp4"]
    assert len(warnings) == 2
    assert any("no-video" in w and "missing" in w for w in warnings)
    assert any("corrupt" in w and "unreadable" in w for w in warnings)


def test_load_clips_from_a_missing_folder_is_empty(tmp_path):
    assert clips.load_clips(tmp_path / "nothing-here") == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_clips.py -v`
Expected: FAIL with `ImportError: cannot import name 'clips' from 'feasibility'`

- [ ] **Step 3: Implement `feasibility/clips.py`**

```python
"""Clip labels, metadata and where clips live on disk.

A clip is a video plus a JSON sidecar with the same stem, in clips/<label>/.
The sidecar is written last, so a clip without one is an interrupted recording.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

# Where the hand is, not what it is doing: nothing user-visible names the behaviour.
TRUE_POSITIVE_LABELS = ("hair_scalp", "hair_crown", "hair_side", "hair_long", "ear_tuck")
FALSE_POSITIVE_LABELS = ("chin_rest", "cheek_rest", "glasses", "drinking", "phone")
LABELS = TRUE_POSITIVE_LABELS + FALSE_POSITIVE_LABELS
SPLITS = ("dev", "holdout")
HOLDOUT_EVERY = 4  # every 4th clip of a label is kept back for evaluation only


@dataclass
class ClipMeta:
    label: str
    split: str
    recorded_at: str  # ISO 8601, local time
    backend: str
    width: int
    height: int
    timestamps_ms: list[int]  # one per written frame, from the start of the recording

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, text: str) -> "ClipMeta":
        meta = cls(**json.loads(text))
        if meta.label not in LABELS:
            raise ValueError(f"unknown label {meta.label!r}")
        if meta.split not in SPLITS:
            raise ValueError(f"unknown split {meta.split!r}")
        if not all(isinstance(t, int) for t in meta.timestamps_ms):
            raise ValueError("timestamps_ms must be whole milliseconds")
        return meta


@dataclass(frozen=True)
class Clip:
    video: Path
    meta: ClipMeta


def assign_split(existing_count: int) -> str:
    return "holdout" if existing_count % HOLDOUT_EVERY == HOLDOUT_EVERY - 1 else "dev"


def new_clip_paths(clips_dir: Path, label: str, now: datetime) -> tuple[Path, Path]:
    stem = now.strftime("%Y%m%d-%H%M%S-%f")
    folder = clips_dir / label
    return folder / f"{stem}.mp4", folder / f"{stem}.json"


def count_clips(clips_dir: Path, label: str) -> int:
    return len(list((clips_dir / label).glob("*.json")))


def save_meta(path: Path, meta: ClipMeta) -> None:
    path.write_text(meta.to_json(), encoding="utf-8")


def load_clips(clips_dir: Path, warn: Callable[[str], None] = print) -> list[Clip]:
    """Every complete clip, sorted by path. Broken clips are skipped with a warning."""
    clips = []
    if not clips_dir.is_dir():
        return clips
    for meta_path in sorted(clips_dir.glob("*/*.json")):
        video = meta_path.with_suffix(".mp4")
        if not video.is_file():
            warn(f"Skipping {meta_path.parent.name}/{meta_path.name}: its video is missing")
            continue
        try:
            meta = ClipMeta.from_json(meta_path.read_text(encoding="utf-8"))
        except (ValueError, TypeError) as exc:  # json.JSONDecodeError is a ValueError
            warn(f"Skipping {meta_path.parent.name}/{meta_path.name}: unreadable metadata ({exc})")
            continue
        clips.append(Clip(video, meta))
    return clips
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_clips.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add feasibility/clips.py tests/test_clips.py
git commit -m "Add clip labels, metadata and storage"
```

---

### Task 5: Clip recorder with live tracking preview

**Files:**
- Create: `feasibility/record.py`
- Modify: `feasibility/__main__.py` (add the `record` command)
- Test: `tests/test_record.py`

**Interfaces:**
- Consumes:
  - `halo.camera.open_camera`, `halo.camera.Backend`, `halo.camera.backend_by_name`, `halo.camera.backends_for_platform`
  - `halo.landmarks.Tracker`, `halo.landmarks.Observation`
  - `feasibility.clips.LABELS`, `ClipMeta`, `Clip`, `assign_split`, `new_clip_paths`, `count_clips`, `save_meta`
  - `halo.paths.clips_dir`
- Produces:
  - `feasibility.record.MIN_CLIP_FRAMES = 15`
  - `feasibility.record.ClipRecorder(clips_dir, label, backend, size, writer_factory=open_writer, clock=time.monotonic, now=datetime.now)` with property `recording -> bool`, attribute `saved: int`, and methods `start()`, `add(frame)`, `stop() -> Clip | None`
  - `feasibility.record.draw_overlay(frame, observation, recording, label, saved) -> np.ndarray`
  - `feasibility.record.run_record(label, camera_index, backend, clips_dir) -> int`
  - CLI: `python -m feasibility record --label LABEL [--camera N] [--backend NAME]`

- [ ] **Step 1: Write the failing tests**

`tests/test_record.py`:

```python
from datetime import datetime, timedelta

import numpy as np
import pytest

from feasibility.clips import load_clips
from feasibility.record import MIN_CLIP_FRAMES, ClipRecorder, draw_overlay
from halo.landmarks import Observation
from tests.helpers import FakeClock

SIZE = (64, 48)


class FakeWriter:
    def __init__(self, path, fps, size):
        self.path, self.size, self.frames, self.released = path, size, [], False
        path.write_bytes(b"video")

    def write(self, frame):
        self.frames.append(frame)

    def release(self):
        self.released = True


def make_recorder(tmp_path, clock, label="hair_scalp"):
    writers = []
    stamp = [datetime(2026, 10, 7, 12, 0, 0)]

    def now():
        stamp[0] += timedelta(seconds=1)
        return stamp[0]

    def factory(path, fps, size):
        writers.append(FakeWriter(path, fps, size))
        return writers[-1]

    recorder = ClipRecorder(tmp_path, label, "dshow", SIZE, writer_factory=factory, clock=clock, now=now)
    return recorder, writers


def frame(value=128):
    return np.full((SIZE[1], SIZE[0], 3), value, np.uint8)


def record_clip(recorder, clock, frames):
    recorder.start()
    for _ in range(frames):
        recorder.add(frame())
        clock.now += 0.033
    return recorder.stop()


def test_recorder_saves_video_and_metadata(tmp_path):
    clock = FakeClock(100.0)
    recorder, writers = make_recorder(tmp_path, clock)
    clip = record_clip(recorder, clock, MIN_CLIP_FRAMES)
    assert clip is not None and clip.video.is_file()
    assert writers[0].released and len(writers[0].frames) == MIN_CLIP_FRAMES
    assert clip.meta.timestamps_ms[:3] == [0, 33, 66]
    assert (clip.meta.label, clip.meta.split, clip.meta.width, clip.meta.height) == ("hair_scalp", "dev", 64, 48)
    assert load_clips(tmp_path)[0].meta == clip.meta
    assert recorder.saved == 1 and not recorder.recording


def test_short_recording_is_discarded(tmp_path):
    clock = FakeClock()
    recorder, writers = make_recorder(tmp_path, clock)
    assert record_clip(recorder, clock, MIN_CLIP_FRAMES - 1) is None
    assert not writers[0].path.exists()
    assert load_clips(tmp_path) == []
    assert recorder.saved == 0


def test_fourth_clip_is_held_out(tmp_path):
    clock = FakeClock()
    recorder, _ = make_recorder(tmp_path, clock)
    splits = [record_clip(recorder, clock, MIN_CLIP_FRAMES).meta.split for _ in range(4)]
    assert splits == ["dev", "dev", "dev", "holdout"]


def test_add_does_nothing_when_not_recording(tmp_path):
    recorder, writers = make_recorder(tmp_path, FakeClock())
    recorder.add(frame())
    assert writers == [] and recorder.stop() is None


def test_recorder_resizes_frames_to_writer_size(tmp_path):
    recorder, writers = make_recorder(tmp_path, FakeClock())
    recorder.start()
    recorder.add(np.full((480, 640, 3), 128, np.uint8))
    assert writers[0].frames[0].shape == (48, 64, 3)


def test_unknown_label_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="waving"):
        make_recorder(tmp_path, FakeClock(), label="waving")


def test_overlay_marks_landmarks_and_recording():
    image = np.zeros((480, 640, 3), np.uint8)
    observation = Observation(0, (((0.5, 0.5),),), True)
    out = draw_overlay(image, observation, recording=True, label="hair_scalp", saved=2)
    assert tuple(out[240, 320]) == (0, 255, 0)  # landmark dot at the centre
    assert tuple(out[25, 615]) == (0, 0, 255)  # red recording dot top right


def test_overlay_without_observation_or_recording():
    out = draw_overlay(np.zeros((480, 640, 3), np.uint8), None, recording=False, label="chin_rest", saved=0)
    assert tuple(out[25, 615]) == (0, 0, 0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_record.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'feasibility.record'`

- [ ] **Step 3: Implement `feasibility/record.py`**

```python
"""Record labelled clips while showing live hand and face tracking.

The preview shows landmarks; the saved video is the raw camera frames.
"""

import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from feasibility.clips import LABELS, Clip, ClipMeta, assign_split, count_clips, new_clip_paths, save_meta
from halo.camera import Backend, open_camera
from halo.landmarks import Observation, Tracker

MIN_CLIP_FRAMES = 15  # shorter recordings are accidental key presses and are discarded
NOMINAL_FPS = 30.0  # written into the file header only; real frame times are kept in the metadata
PREVIEW_TRACK_EVERY = 3  # track every 3rd frame so the preview keeps up on a laptop CPU
MAX_FAILED_READS = 50
WINDOW = "Halo - clip recorder"
FONT = cv2.FONT_HERSHEY_SIMPLEX


def open_writer(path: Path, fps: float, size: tuple[int, int]):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    if not writer.isOpened():
        raise RuntimeError(f"Could not open a video writer for {path}")
    return writer


class ClipRecorder:
    def __init__(self, clips_dir: Path, label: str, backend: str, size: tuple[int, int],
                 writer_factory=open_writer, clock=time.monotonic, now=datetime.now):
        if label not in LABELS:
            raise ValueError(f"Unknown label {label!r}; expected one of {', '.join(LABELS)}")
        self._clips_dir = clips_dir
        self._label = label
        self._backend = backend
        self._size = size
        self._writer_factory = writer_factory
        self._clock = clock
        self._now = now
        self._writer = None
        self.saved = count_clips(clips_dir, label)

    @property
    def recording(self) -> bool:
        return self._writer is not None

    def start(self) -> None:
        if self.recording:
            return
        stamp = self._now()
        self._video, self._meta_path = new_clip_paths(self._clips_dir, self._label, stamp)
        self._video.parent.mkdir(parents=True, exist_ok=True)
        self._recorded_at = stamp.isoformat(timespec="seconds")
        self._timestamps: list[int] = []
        self._started = self._clock()
        self._writer = self._writer_factory(self._video, NOMINAL_FPS, self._size)

    def add(self, frame: np.ndarray) -> None:
        if not self.recording:
            return
        if (frame.shape[1], frame.shape[0]) != self._size:
            # VideoWriter silently drops frames of the wrong size, which would desync the timestamps
            frame = cv2.resize(frame, self._size)
        self._writer.write(frame)
        self._timestamps.append(int(round((self._clock() - self._started) * 1000)))

    def stop(self) -> Clip | None:
        """Finish the clip. Returns None, and deletes the video, if it was too short to keep."""
        if not self.recording:
            return None
        self._writer.release()
        self._writer = None
        if len(self._timestamps) < MIN_CLIP_FRAMES:
            self._video.unlink(missing_ok=True)
            return None
        meta = ClipMeta(
            self._label, assign_split(self.saved), self._recorded_at, self._backend,
            self._size[0], self._size[1], list(self._timestamps),
        )
        save_meta(self._meta_path, meta)
        self.saved += 1
        return Clip(self._video, meta)


def draw_overlay(frame: np.ndarray, observation: Observation | None, recording: bool, label: str, saved: int) -> np.ndarray:
    h, w = frame.shape[:2]
    if observation is not None:
        for hand in observation.hands:
            for x, y in hand:
                cv2.circle(frame, (int(x * w), int(y * h)), 3, (0, 255, 0), -1)
        status = f"hand: {'yes' if observation.hand_found else 'no'}   face: {'yes' if observation.face_found else 'no'}"
        cv2.putText(frame, status, (10, h - 15), FONT, 0.6, (255, 255, 255), 2)
    cv2.putText(frame, f"{label}   saved: {saved}", (10, 25), FONT, 0.6, (255, 255, 255), 2)
    if recording:
        cv2.circle(frame, (w - 25, 25), 10, (0, 0, 255), -1)
    return frame


def _report(clip: Clip | None) -> None:
    if clip is None:
        print(f"  discarded (under {MIN_CLIP_FRAMES} frames)")
    else:
        seconds = clip.meta.timestamps_ms[-1] / 1000
        print(f"  saved {clip.video.name}: {len(clip.meta.timestamps_ms)} frames, {seconds:.1f} s, {clip.meta.split}")


def run_record(label: str, camera_index: int, backend: Backend, clips_dir: Path) -> int:
    result = open_camera(camera_index, backend)
    if not result.ok:
        print(f"Could not open camera {camera_index} with {backend.name}: {result.error}")
        return 1
    capture = result.capture
    ok, frame = capture.read()
    if not ok:
        print("The camera stopped delivering frames.")
        capture.release()
        return 1
    recorder = ClipRecorder(clips_dir, label, backend.name, (frame.shape[1], frame.shape[0]))
    print(f"Recording '{label}' ({recorder.saved} saved so far). SPACE starts and stops a clip; Q or Esc quits.")
    observation = None
    frame_no = 0
    failed = 0
    started = time.monotonic()
    try:
        with Tracker() as tracker:
            while True:
                ok, frame = capture.read()
                if not ok:
                    failed += 1
                    if failed >= MAX_FAILED_READS:
                        print("The camera stopped delivering frames.")
                        break
                    continue
                failed = 0
                recorder.add(frame)
                if frame_no % PREVIEW_TRACK_EVERY == 0:
                    observation = tracker.process(frame, int((time.monotonic() - started) * 1000))
                frame_no += 1
                cv2.imshow(WINDOW, draw_overlay(frame.copy(), observation, recorder.recording, label, recorder.saved))
                key = cv2.waitKey(1) & 0xFF
                if key == ord(" "):
                    if recorder.recording:
                        _report(recorder.stop())
                    else:
                        recorder.start()
                        print("  recording...")
                elif key in (ord("q"), 27):
                    break
                if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break  # window closed with the mouse
    finally:
        if recorder.recording:  # Q, a closed window, Ctrl+C or a crash mid-clip still finalises the file
            _report(recorder.stop())
        capture.release()
        cv2.destroyAllWindows()
    return 0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_record.py -v`
Expected: all passed

- [ ] **Step 5: Add the `record` command to `feasibility/__main__.py`**

Add this import below `from halo.camera import backends_for_platform`, changing that line to:

```python
from halo.camera import backend_by_name, backends_for_platform
```

Add this block after the `probe` subparser arguments, before `args = parser.parse_args(argv)`:

```python
    record = sub.add_parser("record", help="Record labelled clips with live tracking")
    record.add_argument("--label", required=True, help="where the hand is, e.g. hair_scalp or chin_rest")
    record.add_argument("--camera", type=int, default=0, help="camera index (default 0)")
    record.add_argument("--backend", default=None, help="camera backend (default: the first for this OS)")
```

Add this block before `return 2`:

```python
    if args.command == "record":
        from feasibility.clips import LABELS
        from feasibility.record import run_record
        from halo.paths import clips_dir

        if args.label not in LABELS:
            parser.error(f"--label must be one of: {', '.join(LABELS)}")
        backend = backend_by_name(args.backend) if args.backend else backends_for_platform()[0]
        return run_record(args.label, args.camera, backend, clips_dir())
```

- [ ] **Step 6: Record a clip on the Mac**

Run: `.venv/bin/python -m feasibility record --label hair_scalp`
Expected: a window shows the camera with green dots on your hand when it is visible and a "hand: yes / face: yes" line. Press SPACE, hold your hand on your head for about 3 seconds, press SPACE again: the terminal prints `saved <name>.mp4: N frames, ...`. Press Q. Then run `ls clips/hair_scalp` and see one `.mp4` and one `.json` with the same stem. Run `git status` and confirm nothing under `clips/` is listed.

- [ ] **Step 7: Commit**

```bash
git add feasibility/record.py feasibility/__main__.py tests/test_record.py
git commit -m "Add clip recorder with live tracking preview"
```

---

### Task 6: Clip statistics and the go / no-go verdict

**Files:**
- Create: `feasibility/stats.py`
- Test: `tests/test_stats.py`

**Interfaces:**
- Consumes: `halo.landmarks.Observation`; `feasibility.clips.TRUE_POSITIVE_LABELS`
- Produces:
  - Constants `MIN_CLIP_HAND_RATE = 0.8`, `MIN_PASSING_SHARE = 0.8`, `MIN_CLIPS_PER_LABEL = 3`, `WEAK_LABEL_PASS_SHARE = 0.5`
  - `ClipStats(label, split, video: str, frames: int, duration_s: float, hand_rate: float, face_rate: float, longest_hand_gap_s: float, frame_count_mismatch: int)` (frozen) with property `passed -> bool`
  - `longest_gap_s(observations) -> float`
  - `clip_stats(label, split, video, observations, frame_count_mismatch=0) -> ClipStats`
  - `Verdict(status: str, passing_share: float, missing_labels: list[str], weak_labels: list[str])` with `lines() -> list[str]`; status is `"GO"`, `"NO-GO"` or `"INCOMPLETE"`
  - `evaluate(stats: list[ClipStats]) -> Verdict`

**Why these numbers:** the spec's go criterion is "her hand is found during most real motions". A clip passes when a hand is found in at least 80% of its frames; milestone 1 is GO when at least 80% of true-positive clips pass and every true-positive label has at least 3 clips. A label where under half its clips pass is a weak spot to look at (often the crown, if the webcam crops it), but does not block GO on its own. False-positive clips are reported but do not affect the verdict; they are for milestone 3.

- [ ] **Step 1: Write the failing tests**

`tests/test_stats.py`:

```python
import pytest

from feasibility.clips import TRUE_POSITIVE_LABELS
from feasibility.stats import ClipStats, clip_stats, evaluate, longest_gap_s
from halo.landmarks import Observation


def obs(ts, hand, face=True):
    return Observation(ts, (((0.5, 0.5),),) if hand else (), face)


def sequence(flags, step=100):
    return [obs(i * step, flag) for i, flag in enumerate(flags)]


def test_longest_gap_runs_to_the_next_hand():
    assert longest_gap_s(sequence([True, True, False, False, False, True])) == pytest.approx(0.3)


def test_longest_gap_counts_a_trailing_run():
    assert longest_gap_s(sequence([True, False, False])) == pytest.approx(0.1)


def test_longest_gap_with_hand_throughout_is_zero():
    assert longest_gap_s(sequence([True] * 4)) == 0.0
    assert longest_gap_s([]) == 0.0


def test_clip_stats_rates_and_duration():
    observations = sequence([True, True, True, False])
    observations[3] = obs(300, False, face=False)
    s = clip_stats("hair_scalp", "dev", "a.mp4", observations, frame_count_mismatch=1)
    assert (s.frames, s.duration_s, s.hand_rate, s.face_rate) == (4, 0.3, 0.75, 0.75)
    assert s.frame_count_mismatch == 1
    assert not s.passed


def test_clip_stats_for_an_empty_clip():
    s = clip_stats("hair_scalp", "dev", "a.mp4", [])
    assert (s.frames, s.duration_s, s.hand_rate, s.face_rate, s.passed) == (0, 0.0, 0.0, 0.0, False)


def stat(label, hand_rate):
    return ClipStats(label, "dev", f"{label}.mp4", 30, 1.0, hand_rate, 1.0, 0.0, 0)


def full_set(failing=None):
    """Three clips per true-positive label, all passing except the (label, count) given."""
    stats = []
    for label in TRUE_POSITIVE_LABELS:
        fails = failing.get(label, 0) if failing else 0
        stats += [stat(label, 0.5 if i < fails else 0.95) for i in range(3)]
    return stats


def test_all_clips_passing_is_go():
    verdict = evaluate(full_set())
    assert (verdict.status, verdict.passing_share, verdict.weak_labels) == ("GO", 1.0, [])


def test_too_few_clips_for_a_label_is_incomplete():
    stats = [s for s in full_set() if s.label != "hair_crown"] + [stat("hair_crown", 0.95)] * 2
    verdict = evaluate(stats)
    assert verdict.status == "INCOMPLETE" and verdict.missing_labels == ["hair_crown"]


def test_no_clips_is_incomplete():
    verdict = evaluate([])
    assert verdict.status == "INCOMPLETE" and verdict.missing_labels == list(TRUE_POSITIVE_LABELS)


def test_too_many_failing_clips_is_no_go():
    verdict = evaluate(full_set({"hair_crown": 2, "hair_long": 2}))  # 11 of 15 pass
    assert verdict.status == "NO-GO"
    assert verdict.passing_share == pytest.approx(11 / 15)


def test_weak_label_is_reported_without_blocking_go():
    verdict = evaluate(full_set({"hair_crown": 2}))  # 13 of 15 pass
    assert verdict.status == "GO" and verdict.weak_labels == ["hair_crown"]


def test_false_positive_clips_do_not_affect_the_verdict():
    verdict = evaluate(full_set() + [stat("chin_rest", 0.0)] * 5)
    assert verdict.status == "GO" and verdict.passing_share == 1.0


def test_verdict_lines_explain_the_result():
    lines = evaluate(full_set({"hair_crown": 2})).lines()
    assert lines[0].startswith("Verdict: GO")
    assert any("hair_crown" in line for line in lines[1:])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_stats.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'feasibility.stats'`

- [ ] **Step 3: Implement `feasibility/stats.py`**

```python
"""Per-clip hand-visibility statistics and milestone 1's go / no-go verdict."""

from dataclasses import dataclass, field
from typing import Sequence

from feasibility.clips import TRUE_POSITIVE_LABELS
from halo.landmarks import Observation

MIN_CLIP_HAND_RATE = 0.8  # a clip passes when a hand is found in at least this share of frames
MIN_PASSING_SHARE = 0.8  # GO needs at least this share of true-positive clips to pass
MIN_CLIPS_PER_LABEL = 3  # each true-positive label needs this many clips before a verdict
WEAK_LABEL_PASS_SHARE = 0.5  # a label with fewer passing clips than this is flagged


@dataclass(frozen=True)
class ClipStats:
    label: str
    split: str
    video: str
    frames: int
    duration_s: float
    hand_rate: float
    face_rate: float
    longest_hand_gap_s: float
    frame_count_mismatch: int  # video frames minus recorded timestamps; 0 when they agree

    @property
    def passed(self) -> bool:
        return self.frames > 0 and self.hand_rate >= MIN_CLIP_HAND_RATE


def longest_gap_s(observations: Sequence[Observation]) -> float:
    """Longest stretch without a hand, from its first frame to the next frame with a hand (or the clip's end)."""
    longest = 0
    run_start = None
    for o in observations:
        if o.hand_found:
            if run_start is not None:
                longest = max(longest, o.timestamp_ms - run_start)
                run_start = None
        elif run_start is None:
            run_start = o.timestamp_ms
    if run_start is not None:
        longest = max(longest, observations[-1].timestamp_ms - run_start)
    return longest / 1000


def clip_stats(label: str, split: str, video: str, observations: Sequence[Observation],
               frame_count_mismatch: int = 0) -> ClipStats:
    frames = len(observations)
    if frames == 0:
        return ClipStats(label, split, video, 0, 0.0, 0.0, 0.0, 0.0, frame_count_mismatch)
    return ClipStats(
        label, split, video, frames,
        duration_s=(observations[-1].timestamp_ms - observations[0].timestamp_ms) / 1000,
        hand_rate=sum(o.hand_found for o in observations) / frames,
        face_rate=sum(o.face_found for o in observations) / frames,
        longest_hand_gap_s=longest_gap_s(observations),
        frame_count_mismatch=frame_count_mismatch,
    )


@dataclass
class Verdict:
    status: str  # "GO", "NO-GO" or "INCOMPLETE"
    passing_share: float
    missing_labels: list[str] = field(default_factory=list)
    weak_labels: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        out = [
            f"Verdict: {self.status}. {self.passing_share:.0%} of true-positive clips had a hand in at least "
            f"{MIN_CLIP_HAND_RATE:.0%} of frames; GO needs {MIN_PASSING_SHARE:.0%}."
        ]
        if self.missing_labels:
            out.append(f"Record at least {MIN_CLIPS_PER_LABEL} clips each for: {', '.join(self.missing_labels)}")
        if self.weak_labels:
            out.append(f"Weak spots (under {WEAK_LABEL_PASS_SHARE:.0%} of clips pass): {', '.join(self.weak_labels)}")
        return out


def evaluate(stats: list[ClipStats]) -> Verdict:
    true_positives = [s for s in stats if s.label in TRUE_POSITIVE_LABELS]
    missing, weak = [], []
    for label in TRUE_POSITIVE_LABELS:
        clips = [s for s in true_positives if s.label == label]
        if len(clips) < MIN_CLIPS_PER_LABEL:
            missing.append(label)
        if clips and sum(s.passed for s in clips) / len(clips) < WEAK_LABEL_PASS_SHARE:
            weak.append(label)
    share = sum(s.passed for s in true_positives) / len(true_positives) if true_positives else 0.0
    if missing:
        status = "INCOMPLETE"
    elif share >= MIN_PASSING_SHARE:
        status = "GO"
    else:
        status = "NO-GO"
    return Verdict(status, share, missing, weak)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_stats.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add feasibility/stats.py tests/test_stats.py
git commit -m "Add clip statistics and go/no-go verdict"
```

---

### Task 7: Analyse saved clips

**Files:**
- Create: `feasibility/analyse.py`, `feasibility/report.py`
- Modify: `feasibility/__main__.py` (add the `analyse` command)
- Test: `tests/test_analyse.py`

**Interfaces:**
- Consumes:
  - `feasibility.clips.Clip`, `ClipMeta`, `load_clips`, `TRUE_POSITIVE_LABELS`, `LABELS`
  - `feasibility.stats.ClipStats`, `clip_stats`, `evaluate`, `MIN_CLIP_HAND_RATE`
  - `halo.landmarks.Tracker`, `Observation`
  - `halo.paths.clips_dir`, `halo.paths.reports_dir`
- Produces:
  - `feasibility.report.write_report(reports_dir: Path, kind: str, payload: dict, now: datetime) -> Path`
  - `feasibility.analyse.read_frames(video: Path) -> Iterator[np.ndarray]`
  - `feasibility.analyse.analyse_clip(clip, tracker_factory=Tracker, frame_reader=read_frames) -> ClipStats`
  - `feasibility.analyse.format_table(stats: list[ClipStats]) -> list[str]`
  - `feasibility.analyse.run_analyse(clips_dir, reports_dir, now=datetime.now) -> int`
  - CLI: `python -m feasibility analyse`

- [ ] **Step 1: Write the failing tests**

`tests/test_analyse.py`:

```python
import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from feasibility.analyse import analyse_clip, format_table, read_frames, run_analyse
from feasibility.clips import Clip, ClipMeta, save_meta
from feasibility.report import write_report
from feasibility.stats import ClipStats
from halo.landmarks import Observation


class FakeTracker:
    """Reports a hand on frames whose first pixel is bright."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def process(self, frame, timestamp_ms):
        hand = (((0.5, 0.5),),) if frame[0, 0, 0] > 100 else ()
        return Observation(timestamp_ms, hand, True)


def frames(*values):
    return [np.full((4, 4, 3), v, np.uint8) for v in values]


def clip_with(timestamps, label="hair_scalp"):
    return Clip(Path(f"{label}.mp4"), ClipMeta(label, "dev", "2026-10-07T12:00:00", "dshow", 4, 4, timestamps))


def test_analyse_clip_uses_recorded_timestamps():
    stats = analyse_clip(clip_with([0, 100, 200, 300]), tracker_factory=FakeTracker,
                         frame_reader=lambda path: iter(frames(200, 200, 0, 200)))
    assert (stats.frames, stats.hand_rate, stats.duration_s) == (4, 0.75, 0.3)
    assert stats.longest_hand_gap_s == 0.1
    assert stats.frame_count_mismatch == 0


def test_analyse_clip_reports_extra_and_missing_frames():
    extra = analyse_clip(clip_with([0, 100]), tracker_factory=FakeTracker,
                         frame_reader=lambda path: iter(frames(200, 200, 200)))
    assert (extra.frames, extra.frame_count_mismatch) == (2, 1)
    missing = analyse_clip(clip_with([0, 100, 200]), tracker_factory=FakeTracker,
                           frame_reader=lambda path: iter(frames(200)))
    assert (missing.frames, missing.frame_count_mismatch) == (1, -2)


def test_read_frames_reads_an_mp4(tmp_path):
    path = tmp_path / "c.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (64, 48))
    for _ in range(20):
        writer.write(np.full((48, 64, 3), 128, np.uint8))
    writer.release()
    assert len(list(read_frames(path))) == 20


def test_format_table_flags_failing_true_positives_and_mismatches():
    rows = format_table([
        ClipStats("hair_scalp", "dev", "/x/a.mp4", 30, 1.0, 0.5, 1.0, 0.4, 0),
        ClipStats("chin_rest", "holdout", "/x/b.mp4", 30, 1.0, 0.1, 1.0, 0.9, 2),
    ])
    assert "below 80%" in rows[1] and "a.mp4" in rows[1]
    assert "below" not in rows[2]
    assert "frame count mismatch +2" in rows[2]


def test_write_report(tmp_path):
    path = write_report(tmp_path / "reports", "analyse", {"a": 1}, datetime(2026, 10, 7, 14, 30, 5))
    assert path.name == "analyse-20261007-143005.json"
    assert json.loads(path.read_text()) == {"a": 1}


def test_run_analyse_with_no_clips_returns_error(tmp_path, capsys):
    assert run_analyse(tmp_path / "clips", tmp_path / "reports") == 1
    assert "No clips found" in capsys.readouterr().out


def test_run_analyse_end_to_end_on_a_real_clip(tmp_path, capsys):
    folder = tmp_path / "clips" / "hair_scalp"
    folder.mkdir(parents=True)
    writer = cv2.VideoWriter(str(folder / "c.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 30, (64, 48))
    for _ in range(20):
        writer.write(np.zeros((48, 64, 3), np.uint8))
    writer.release()
    save_meta(folder / "c.json", ClipMeta("hair_scalp", "dev", "2026-10-07T12:00:00", "dshow", 64, 48,
                                          [i * 33 for i in range(20)]))
    assert run_analyse(tmp_path / "clips", tmp_path / "reports", now=lambda: datetime(2026, 10, 7)) == 0
    report = json.loads((tmp_path / "reports" / "analyse-20261007-000000.json").read_text())
    assert report["verdict"]["status"] == "INCOMPLETE"
    assert report["clips"][0]["frames"] == 20
    assert "Verdict: INCOMPLETE" in capsys.readouterr().out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_analyse.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'feasibility.analyse'`

- [ ] **Step 3: Implement `feasibility/report.py`**

```python
"""Write milestone 1 results as JSON. Reports hold numbers and labels only, never images."""

import json
from datetime import datetime
from pathlib import Path


def write_report(reports_dir: Path, kind: str, payload: dict, now: datetime) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{kind}-{now.strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
```

- [ ] **Step 4: Implement `feasibility/analyse.py`**

```python
"""Run the tracker over saved clips and report how often her hand is found."""

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

from feasibility.clips import LABELS, TRUE_POSITIVE_LABELS, Clip, load_clips
from feasibility.report import write_report
from feasibility.stats import MIN_CLIP_HAND_RATE, ClipStats, clip_stats, evaluate
from halo.landmarks import Tracker


def read_frames(video: Path) -> Iterator[np.ndarray]:
    capture = cv2.VideoCapture(str(video))
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                return
            yield frame
    finally:
        capture.release()


def analyse_clip(clip: Clip, tracker_factory=Tracker, frame_reader=read_frames) -> ClipStats:
    """Track every frame using the recorded timestamps. Uses the shorter of video and timestamps."""
    timestamps = clip.meta.timestamps_ms
    observations = []
    video_frames = 0
    with tracker_factory() as tracker:  # a fresh tracker per clip: VIDEO mode keeps state between frames
        for frame in frame_reader(clip.video):
            if video_frames < len(timestamps):
                observations.append(tracker.process(frame, timestamps[video_frames]))
            video_frames += 1
    return clip_stats(clip.meta.label, clip.meta.split, str(clip.video), observations,
                      frame_count_mismatch=video_frames - len(timestamps))


def format_table(stats: list[ClipStats]) -> list[str]:
    rows = [f"{'label':<11} {'split':<8} {'frames':>6} {'secs':>5} {'hand':>5} {'face':>5} {'gap s':>5}  clip"]
    for s in sorted(stats, key=lambda s: (LABELS.index(s.label), s.video)):
        row = (f"{s.label:<11} {s.split:<8} {s.frames:>6} {s.duration_s:>5.1f} {s.hand_rate:>5.0%} "
               f"{s.face_rate:>5.0%} {s.longest_hand_gap_s:>5.1f}  {Path(s.video).name}")
        if s.label in TRUE_POSITIVE_LABELS and not s.passed:
            row += f"  below {MIN_CLIP_HAND_RATE:.0%}"
        if s.frame_count_mismatch:
            row += f"  frame count mismatch {s.frame_count_mismatch:+d}"
        rows.append(row)
    return rows


def run_analyse(clips_dir: Path, reports_dir: Path, now=datetime.now) -> int:
    clips = load_clips(clips_dir)
    if not clips:
        print(f"No clips found in {clips_dir}. Record some first: python -m feasibility record --label hair_scalp")
        return 1
    stats = []
    for i, clip in enumerate(clips, 1):
        print(f"[{i}/{len(clips)}] {clip.meta.label}/{clip.video.name}")
        stats.append(analyse_clip(clip))
    print()
    for line in format_table(stats):
        print(line)
    verdict = evaluate(stats)
    print()
    for line in verdict.lines():
        print(line)
    payload = {"clips": [asdict(s) | {"passed": s.passed} for s in stats], "verdict": asdict(verdict)}
    print(f"Report written to {write_report(reports_dir, 'analyse', payload, now())}")
    return 0
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_analyse.py -v`
Expected: all passed

- [ ] **Step 6: Add the `analyse` command to `feasibility/__main__.py`**

Add after the `record` subparser arguments, before `args = parser.parse_args(argv)`:

```python
    sub.add_parser("analyse", help="Measure hand visibility in recorded clips and give a verdict")
```

Add before `return 2`:

```python
    if args.command == "analyse":
        from feasibility.analyse import run_analyse
        from halo.paths import clips_dir, reports_dir

        return run_analyse(clips_dir(), reports_dir())
```

- [ ] **Step 7: Analyse the clip recorded in Task 5**

Run: `.venv/bin/python -m feasibility analyse`
Expected: a table with your `hair_scalp` clip(s) showing a hand rate (high if your hand stayed in view), `Verdict: INCOMPLETE` with a list of labels still needing clips, and `Report written to .../reports/analyse-<time>.json`. Then delete your test clips: `rm -r clips reports`.

- [ ] **Step 8: Commit**

```bash
git add feasibility/analyse.py feasibility/report.py feasibility/__main__.py tests/test_analyse.py
git commit -m "Add clip analysis with hand-visibility verdict"
```

---

### Task 8: Guided Teams coexistence test

**Files:**
- Create: `feasibility/coexist.py`
- Modify: `tests/helpers.py` (add `ScriptedAsk`)
- Modify: `feasibility/__main__.py` (add the `coexist` command)
- Test: `tests/test_coexist.py`

**Interfaces:**
- Consumes:
  - `halo.camera.OpenResult`, `FlowStats`, `FrameMonitor`, `OpenCvSource`, `open_camera`, `backend_by_name`, `backends_for_platform`, `start_reader`, `stop_reader`
  - `feasibility.report.write_report`; `halo.paths.reports_dir`
- Produces:
  - Constants `ORDERS = ("halo_first", "teams_first")`, `OBSERVE_SECONDS = 15.0`, `MIN_GOOD_FRAMES = 30`, `MAX_GAP_S = 3.0`, `WINRT_SHARED = "winrt_shared"`
  - `TrialResult(backend, order, halo_opened, open_seconds, open_error, halo_flow: FlowStats | None, teams_video_ok: bool | None)` with properties `halo_kept_frames`, `coexisted` and method `to_dict() -> dict`
  - `ask_yes_no(ask, question) -> bool`
  - `run_trial(backend, order, opener, ask, say, observe_seconds=OBSERVE_SECONDS, sleep=time.sleep, monitor_factory=FrameMonitor) -> TrialResult`
  - `conclusion(trials) -> str`, `summary_lines(trials) -> list[str]`
  - `run_session(backends, opener, ask, say, observe_seconds=OBSERVE_SECONDS, sleep=time.sleep, monitor_factory=FrameMonitor) -> dict`
  - `make_opener(camera_index: int) -> Callable[[str], OpenResult]` (on success, `OpenResult.capture` is a frame source)
  - `default_backends() -> list[str]`
  - CLI: `python -m feasibility coexist [--camera N] [--backends a,b] [--observe S]`

**How a trial works.** "Halo first": Halo opens the camera and starts reading on a background thread; she starts a Teams meeting with her camera on; both run for `observe_seconds`; she says whether her own video shows in Teams. "Teams first": she starts the meeting first, then Halo tries to open the camera. A trial counts as coexisting only if Halo opened, Halo kept getting frames (at least `MIN_GOOD_FRAMES` good frames and no gap over `MAX_GAP_S`), and her Teams video showed. The conclusion maps onto the three outcomes in the spec's "Camera sharing and calls" section.

- [ ] **Step 1: Add `ScriptedAsk` to `tests/helpers.py`**

Append:

```python
class ScriptedAsk:
    """Stands in for input(): returns scripted answers in order and records each prompt."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.answers:
            raise AssertionError(f"Unexpected prompt: {prompt}")
        return self.answers.pop(0)
```

- [ ] **Step 2: Write the failing tests**

`tests/test_coexist.py`:

```python
import threading

import pytest

from feasibility import coexist
from feasibility.coexist import TrialResult, ask_yes_no, conclusion, run_session, run_trial
from halo.camera import FlowStats, OpenResult
from tests.helpers import ScriptedAsk

SMOOTH = FlowStats(good=400, black=0, failed=0, max_gap_s=0.1)
STALLED = FlowStats(good=400, black=0, failed=20, max_gap_s=6.0)


class FakeSource:
    def __init__(self):
        self.closed = False

    def read_status(self):
        threading.Event().wait(0.001)
        return "good"

    def close(self):
        self.closed = True


class StubMonitor:
    def __init__(self, stats):
        self.stats = stats

    def record(self, status):
        pass

    def snapshot(self):
        return self.stats


def opener_for(ok_backends):
    sources = {}

    def opener(name):
        if name in ok_backends:
            sources[name] = FakeSource()
            return OpenResult(name, True, 0.4, capture=sources[name])
        return OpenResult(name, False, 1.2, error="camera did not open")

    return opener, sources


def trial(backend, order, answers, ok_backends=("dshow",), flow=SMOOTH):
    opener, sources = opener_for(ok_backends)
    ask = ScriptedAsk(answers)
    result = run_trial(backend, order, opener, ask, say=lambda s: None, observe_seconds=0,
                       sleep=lambda s: None, monitor_factory=lambda: StubMonitor(flow))
    assert ask.answers == [], "not every scripted answer was used"
    return result, ask, sources


def test_halo_first_success_coexists_and_closes_the_camera():
    result, ask, sources = trial("dshow", "halo_first", ["", "", "y", ""])
    assert result.coexisted and result.halo_kept_frames and result.teams_video_ok
    assert "not using the camera" in ask.prompts[0]
    assert "Halo is now using the camera" in ask.prompts[1]
    assert sources["dshow"].closed


def test_teams_first_success_coexists():
    result, ask, _ = trial("dshow", "teams_first", ["", "y", ""])
    assert result.coexisted
    assert "Meet now" in ask.prompts[0]


def test_teams_first_when_halo_cannot_open():
    result, _, _ = trial("msmf", "teams_first", ["", "y", ""])
    assert not result.halo_opened and result.teams_video_ok is True and not result.coexisted
    assert result.open_error == "camera did not open" and result.halo_flow is None


def test_halo_first_when_halo_cannot_open_stops_early():
    result, ask, _ = trial("msmf", "halo_first", [""])
    assert not result.halo_opened and result.teams_video_ok is None


def test_teams_video_missing_is_not_coexisting():
    result, _, _ = trial("dshow", "halo_first", ["", "", "n", ""])
    assert result.halo_kept_frames and not result.coexisted


def test_halo_frames_stalling_is_not_coexisting():
    result, _, _ = trial("dshow", "halo_first", ["", "", "y", ""], flow=STALLED)
    assert not result.halo_kept_frames and not result.coexisted


def test_too_few_good_frames_is_not_coexisting():
    result, _, _ = trial("dshow", "halo_first", ["", "", "y", ""], flow=FlowStats(good=5, max_gap_s=0.1))
    assert not result.coexisted


def test_ask_yes_no_reprompts_until_answered():
    ask = ScriptedAsk(["maybe", "", " Y "])
    assert ask_yes_no(ask, "Video?") is True
    assert len(ask.prompts) == 3


def result_for(backend, order, ok):
    return TrialResult(backend, order, ok, 0.3, "", SMOOTH if ok else None, ok)


def test_conclusion_prefers_opencv_when_it_coexists_both_ways():
    trials = [result_for("dshow", o, True) for o in coexist.ORDERS] + [result_for("msmf", "halo_first", False)]
    assert "no special handling" in conclusion(trials) and "dshow" in conclusion(trials)


def test_conclusion_one_order_is_not_enough():
    trials = [result_for("dshow", "halo_first", True), result_for("dshow", "teams_first", False)]
    assert "release the camera" in conclusion(trials)


def test_conclusion_when_only_shared_capture_works():
    trials = [result_for("dshow", o, False) for o in coexist.ORDERS]
    trials += [result_for(coexist.WINRT_SHARED, o, True) for o in coexist.ORDERS]
    assert "MediaCapture" in conclusion(trials)


def test_trial_result_dict_includes_derived_fields():
    data = result_for("dshow", "halo_first", True).to_dict()
    assert data["coexisted"] is True and data["halo_kept_frames"] is True
    assert data["halo_flow"]["good"] == 400


def test_session_runs_every_backend_in_both_orders():
    opener, _ = opener_for(("dshow",))
    answers = ["off"]
    answers += ["", "", "y", ""]  # dshow, Halo first
    answers += ["", "y", ""]  # dshow, Teams first
    answers += [""]  # msmf, Halo first: cannot open
    answers += ["", "y", ""]  # msmf, Teams first: cannot open
    ask = ScriptedAsk(answers)
    report = run_session(["dshow", "msmf"], opener, ask, say=lambda s: None, observe_seconds=0,
                         sleep=lambda s: None, monitor_factory=lambda: StubMonitor(SMOOTH))
    assert ask.answers == []
    assert report["windows_multi_app_setting"] == "off"
    assert [(t["backend"], t["order"]) for t in report["trials"]] == [
        ("dshow", "halo_first"), ("dshow", "teams_first"), ("msmf", "halo_first"), ("msmf", "teams_first"),
    ]
    assert "dshow" in report["conclusion"]


def test_default_backends_on_this_platform_are_opencv_names():
    names = coexist.default_backends()
    assert names and all(name in ("dshow", "msmf", "avfoundation", "any", coexist.WINRT_SHARED) for name in names)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_coexist.py -v`
Expected: FAIL with `ImportError: cannot import name 'coexist' from 'feasibility'`

- [ ] **Step 4: Implement `feasibility/coexist.py`**

```python
"""Guided test of whether Halo and the Teams desktop app can use the camera at the same time.

Each backend is tried in both launch orders. The person at the laptop starts and leaves
Teams meetings when prompted and says whether their own video shows in Teams.
"""

import threading
import time
from dataclasses import asdict, dataclass
from typing import Callable

from halo.camera import (
    FlowStats, FrameMonitor, OpenCvSource, OpenResult,
    backend_by_name, backends_for_platform, open_camera, start_reader, stop_reader,
)

ORDERS = ("halo_first", "teams_first")
OBSERVE_SECONDS = 15.0  # how long both apps run together before asking about Teams
MIN_GOOD_FRAMES = 30  # Halo must keep getting real frames...
MAX_GAP_S = 3.0  # ...with no stall longer than this
WINRT_SHARED = "winrt_shared"

TEAMS_START = "Start a Teams 'Meet now' meeting (Calendar > Meet now) with your camera on."
MULTI_APP_QUESTION = (
    "Open Settings > Bluetooth & devices > Cameras and choose your webcam. If there is a setting about "
    "letting more than one app use the camera, type its name and whether it is on or off; otherwise type 'none': "
)


@dataclass
class TrialResult:
    backend: str
    order: str
    halo_opened: bool
    open_seconds: float
    open_error: str
    halo_flow: FlowStats | None
    teams_video_ok: bool | None  # None when Halo could not start the trial

    @property
    def halo_kept_frames(self) -> bool:
        flow = self.halo_flow
        return flow is not None and flow.good >= MIN_GOOD_FRAMES and flow.max_gap_s <= MAX_GAP_S

    @property
    def coexisted(self) -> bool:
        return self.halo_opened and self.halo_kept_frames and self.teams_video_ok is True

    def to_dict(self) -> dict:
        return asdict(self) | {"halo_kept_frames": self.halo_kept_frames, "coexisted": self.coexisted}


def ask_yes_no(ask: Callable[[str], str], question: str) -> bool:
    while True:
        answer = ask(f"{question} [y/n] ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False


def run_trial(backend: str, order: str, opener: Callable[[str], OpenResult], ask, say,
              observe_seconds: float = OBSERVE_SECONDS, sleep=time.sleep,
              monitor_factory=FrameMonitor) -> TrialResult:
    say(f"\n=== {backend}, {order.replace('_', ' ')} ===")
    if order == "teams_first":
        ask(f"{TEAMS_START} Press Enter when your video is showing in Teams.")
    else:
        ask("Make sure Teams is not using the camera (leave any meeting). Press Enter to continue.")

    result = opener(backend)
    if not result.ok:
        say(f"Halo could not open the camera: {result.error}")
        teams_ok = None
        if order == "teams_first":
            teams_ok = ask_yes_no(ask, "Is your own video still showing in Teams?")
            ask("Leave the Teams meeting, then press Enter.")
        return TrialResult(backend, order, False, result.seconds, result.error, None, teams_ok)

    say(f"Halo opened the camera in {result.seconds:.1f} s.")
    monitor = monitor_factory()
    stop = threading.Event()
    thread = start_reader(result.capture, monitor, stop)
    if order == "halo_first":
        ask(f"Halo is now using the camera. {TEAMS_START} "
            "Press Enter once Teams has had a few seconds to show your video.")
    say(f"Watching both apps for {observe_seconds:.0f} s...")
    sleep(observe_seconds)
    teams_ok = ask_yes_no(ask, "Is your own video showing in Teams?")
    flow = monitor.snapshot()
    if not stop_reader(thread, stop, result.capture):
        say("Warning: Halo's camera read is stuck. If the next backend fails to open, restart the tool.")
    ask("Leave the Teams meeting, then press Enter.")
    return TrialResult(backend, order, True, result.seconds, "", flow, teams_ok)


def coexisting_backends(trials: list[TrialResult]) -> list[str]:
    """Backends that coexisted with Teams in both launch orders, in the order tried."""
    names = list(dict.fromkeys(t.backend for t in trials))
    return [name for name in names
            if all(any(t.backend == name and t.order == order and t.coexisted for t in trials) for order in ORDERS)]


def conclusion(trials: list[TrialResult]) -> str:
    both = coexisting_backends(trials)
    opencv = [name for name in both if name != WINRT_SHARED]
    if opencv:
        return (f"OpenCV ({', '.join(opencv)}) works alongside Teams in both launch orders: "
                "no special handling needed beyond camera-busy retries.")
    if WINRT_SHARED in both:
        return ("Only Windows shared capture works alongside Teams in both launch orders: "
                "switch the Windows camera module to WinRT MediaCapture.")
    return ("No backend worked alongside Teams in both launch orders: "
            "Halo must release the camera for calls (pause for call).")


def summary_lines(trials: list[TrialResult]) -> list[str]:
    lines = ["", f"{'backend':<13} {'order':<12} {'result':<6} details"]
    for t in trials:
        if t.halo_opened:
            details = (f"Halo frames: {t.halo_flow.good} good, longest gap {t.halo_flow.max_gap_s:.1f} s; "
                       f"Teams video: {'yes' if t.teams_video_ok else 'no'}")
        else:
            details = f"Halo did not open: {t.open_error}"
        lines.append(f"{t.backend:<13} {t.order:<12} {'OK' if t.coexisted else 'FAIL':<6} {details}")
    return lines


def run_session(backends: list[str], opener, ask, say, observe_seconds: float = OBSERVE_SECONDS,
                sleep=time.sleep, monitor_factory=FrameMonitor) -> dict:
    setting = ask(MULTI_APP_QUESTION).strip()
    trials = [run_trial(backend, order, opener, ask, say, observe_seconds, sleep, monitor_factory)
              for backend in backends for order in ORDERS]
    for line in summary_lines(trials):
        say(line)
    verdict = conclusion(trials)
    say(f"\nConclusion: {verdict}")
    return {
        "windows_multi_app_setting": setting,
        "trials": [t.to_dict() for t in trials],
        "conclusion": verdict,
    }


def make_opener(camera_index: int) -> Callable[[str], OpenResult]:
    def opener(name: str) -> OpenResult:
        result = open_camera(camera_index, backend_by_name(name))
        if result.ok:
            result.capture = OpenCvSource(result.capture)
        return result

    return opener


def default_backends() -> list[str]:
    return [backend.name for backend in backends_for_platform()]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_coexist.py -v`
Expected: all passed

- [ ] **Step 6: Add the `coexist` command to `feasibility/__main__.py`**

Add after the `analyse` subparser, before `args = parser.parse_args(argv)`:

```python
    co = sub.add_parser("coexist", help="Test camera sharing with Teams in both launch orders")
    co.add_argument("--camera", type=int, default=0, help="camera index (default 0)")
    co.add_argument("--backends", default=None, help="comma-separated backends (default: all for this OS)")
    co.add_argument("--observe", type=float, default=15.0, help="seconds both apps run together per trial")
```

Add before `return 2`:

```python
    if args.command == "coexist":
        from datetime import datetime

        from feasibility.coexist import default_backends, make_opener, run_session
        from feasibility.report import write_report
        from halo.paths import reports_dir

        backends = args.backends.split(",") if args.backends else default_backends()
        report = run_session(backends, make_opener(args.camera), ask=input, say=print, observe_seconds=args.observe)
        print(f"Report written to {write_report(reports_dir(), 'coexist', report, datetime.now())}")
        return 0
```

- [ ] **Step 7: Dry-run the flow on the Mac**

macOS lets apps share the camera, so this is only a check that the prompts read well and the report is written, not a real result.

Run: `.venv/bin/python -m feasibility coexist --observe 3`
Expected: the multi-app question, then two `avfoundation` trials with prompts. Answer `none`, press Enter through the prompts (you can start a real Teams or FaceTime call if you have one), answer `y` to the video questions. A summary table, a conclusion line and `Report written to .../reports/coexist-<time>.json` follow. Then `rm -r reports`.

- [ ] **Step 8: Commit**

```bash
git add feasibility/coexist.py feasibility/__main__.py tests/helpers.py tests/test_coexist.py
git commit -m "Add guided Teams camera coexistence test"
```

---

### Task 9: Windows shared camera probe (WinRT)

**Files:**
- Create: `feasibility/winrt_probe.py`
- Modify: `feasibility/coexist.py` (`make_opener` and `default_backends`)
- Test: `tests/test_winrt_probe.py`

**Interfaces:**
- Consumes: `halo.camera.OpenResult`; `feasibility.coexist.WINRT_SHARED`
- Produces:
  - `feasibility.winrt_probe.winrt_available() -> bool`
  - `feasibility.winrt_probe.open_shared(clock=time.monotonic) -> OpenResult` (never raises; on success `capture` is a `WinrtSharedSource`)
  - `feasibility.winrt_probe.WinrtSharedSource` with `read_status() -> str | None` and `close()`

**Caution.** This module cannot run on the Mac and the CI runner has no camera, so its WinRT calls are only fully exercised on her laptop. It is kept small, and any failure is recorded as text in the coexist report rather than raised, so a mistake here costs one inconclusive row, not the session. The CI test does confirm that the packages import and that the first WinRT calls work up to "no colour camera found". Shared mode cannot change camera settings and ignores `--camera`; it uses the first colour camera Windows lists.

- [ ] **Step 1: Write the failing tests**

`tests/test_winrt_probe.py`:

```python
import os
import sys

import pytest

from feasibility import coexist, winrt_probe

on_windows = sys.platform == "win32"


@pytest.mark.skipif(on_windows, reason="checks the non-Windows fallback")
def test_shared_capture_is_unavailable_off_windows():
    assert not winrt_probe.winrt_available()
    result = winrt_probe.open_shared()
    assert not result.ok and "only available on Windows" in result.error
    assert coexist.WINRT_SHARED not in coexist.default_backends()


@pytest.mark.skipif(not on_windows, reason="Windows only")
def test_winrt_packages_import_on_windows():
    assert winrt_probe.winrt_available()
    assert coexist.default_backends()[-1] == coexist.WINRT_SHARED


@pytest.mark.skipif(not (on_windows and os.environ.get("CI")), reason="CI runners have no camera")
def test_open_shared_reports_missing_camera_without_raising():
    result = winrt_probe.open_shared()
    assert not result.ok and "no colour camera" in result.error


def test_opener_routes_shared_backend_to_winrt(monkeypatch):
    from halo.camera import OpenResult

    monkeypatch.setattr(winrt_probe, "open_shared", lambda: OpenResult("winrt_shared", False, 0.0, error="stub"))
    result = coexist.make_opener(0)(coexist.WINRT_SHARED)
    assert result.error == "stub"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_winrt_probe.py -v`
Expected: FAIL with `ImportError: cannot import name 'winrt_probe' from 'feasibility'`

- [ ] **Step 3: Implement `feasibility/winrt_probe.py`**

```python
"""Best-effort probe of Windows shared camera access (MediaCapture in SharedReadOnly mode) via pywinrt.

Shared mode lets Halo read frames while another app, such as Teams, controls the camera.
Windows-only and untestable on the Mac, so it stays small and never raises: any failure
becomes the error text of an OpenResult, and the coexist session carries on.
"""

import asyncio
import sys
import time

from halo.camera import OpenResult

BACKEND = "winrt_shared"


def winrt_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winrt.windows.media.capture  # noqa: F401
        import winrt.windows.media.capture.frames  # noqa: F401
    except ImportError:
        return False
    return True


class WinrtSharedSource:
    def __init__(self, capture, reader):
        self._capture = capture
        self._reader = reader

    def read_status(self) -> str | None:
        frame = self._reader.try_acquire_latest_frame()
        if frame is None:
            return None  # no new frame since the last call
        try:
            return "good" if frame.video_media_frame is not None else "failed"
        finally:
            frame.close()

    def close(self) -> None:
        try:
            asyncio.run(_stop(self._reader))
        finally:
            self._capture.close()


async def _stop(reader) -> None:
    await reader.stop_async()


async def _open():
    from winrt.windows.media.capture import (
        MediaCapture, MediaCaptureInitializationSettings, MediaCaptureMemoryPreference,
        MediaCaptureSharingMode, StreamingCaptureMode,
    )
    from winrt.windows.media.capture.frames import (
        MediaFrameReaderStartStatus, MediaFrameSourceGroup, MediaFrameSourceKind,
    )
    import winrt.windows.foundation.collections  # noqa: F401  (lets frame_sources behave as a mapping)

    groups = await MediaFrameSourceGroup.find_all_async()
    group = next((g for g in groups
                  if any(info.source_kind == MediaFrameSourceKind.COLOR for info in g.source_infos)), None)
    if group is None:
        raise RuntimeError("no colour camera found")

    settings = MediaCaptureInitializationSettings()
    settings.source_group = group
    settings.sharing_mode = MediaCaptureSharingMode.SHARED_READ_ONLY
    settings.streaming_capture_mode = StreamingCaptureMode.VIDEO
    settings.memory_preference = MediaCaptureMemoryPreference.CPU
    capture = MediaCapture()
    await capture.initialize_async(settings)

    source = next((s for s in capture.frame_sources.values()
                   if s.info.source_kind == MediaFrameSourceKind.COLOR), None)
    if source is None:
        capture.close()
        raise RuntimeError("camera has no colour stream")
    reader = await capture.create_frame_reader_async(source)
    status = await reader.start_async()
    if status != MediaFrameReaderStartStatus.SUCCESS:
        capture.close()
        raise RuntimeError(f"frame reader did not start: {status.name}")
    return capture, reader


def open_shared(clock=time.monotonic) -> OpenResult:
    start = clock()
    if not winrt_available():
        return OpenResult(BACKEND, False, 0.0, error="shared capture is only available on Windows with pywinrt installed")
    try:
        capture, reader = asyncio.run(_open())
    except Exception as exc:
        return OpenResult(BACKEND, False, clock() - start, error=f"{type(exc).__name__}: {exc}")
    return OpenResult(BACKEND, True, clock() - start, capture=WinrtSharedSource(capture, reader))
```

- [ ] **Step 4: Route `winrt_shared` through the coexist opener**

In `feasibility/coexist.py`, replace `make_opener` and `default_backends` with:

```python
def make_opener(camera_index: int) -> Callable[[str], OpenResult]:
    def opener(name: str) -> OpenResult:
        if name == WINRT_SHARED:
            from feasibility import winrt_probe

            return winrt_probe.open_shared()
        result = open_camera(camera_index, backend_by_name(name))
        if result.ok:
            result.capture = OpenCvSource(result.capture)
        return result

    return opener


def default_backends() -> list[str]:
    from feasibility.winrt_probe import winrt_available

    names = [backend.name for backend in backends_for_platform()]
    if winrt_available():
        names.append(WINRT_SHARED)
    return names
```

Note: `winrt_probe.open_shared` is looked up on the module at call time, which is what lets `test_opener_routes_shared_backend_to_winrt` stub it.

- [ ] **Step 5: Run all tests**

Run: `.venv/bin/python -m pytest -v`
Expected: all passed, with the two Windows-only tests in `test_winrt_probe.py` skipped on the Mac

- [ ] **Step 6: Commit**

```bash
git add feasibility/winrt_probe.py feasibility/coexist.py tests/test_winrt_probe.py
git commit -m "Add Windows shared camera probe to the coexistence test"
```

---

### Task 10: Windows CI and the milestone 1 runbook

**Files:**
- Create: `.github/workflows/tests.yml`
- Create: `docs/milestone-1-runbook.md`

**Interfaces:**
- Consumes: the CLI commands `probe`, `coexist`, `record`, `analyse`; labels from `feasibility/clips.py`; thresholds from `feasibility/stats.py` and `feasibility/coexist.py`.
- Produces: a green test run on windows-latest, and the document used at her laptop.

- [ ] **Step 1: Add the workflow**

`.github/workflows/tests.yml`:

```yaml
name: tests

on:
  push:
  pull_request:

jobs:
  windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: requirements-dev.txt
      - run: python -m pip install -r requirements-dev.txt
      - run: python -m pytest -v
```

- [ ] **Step 2: Push and check the run**

Run:

```bash
git add .github/workflows/tests.yml
git commit -m "Run the test suite on windows-latest"
git push
gh run watch --exit-status $(gh run list --workflow tests.yml --limit 1 --json databaseId --jq '.[0].databaseId')
```

Expected: the run succeeds. `test_winrt_packages_import_on_windows` and `test_open_shared_reports_missing_camera_without_raising` pass rather than skip. If `test_open_shared_reports_missing_camera_without_raising` fails with an `AttributeError` or `ImportError` in the error text, a pywinrt name in `winrt_probe._open` is wrong: fix the name the error points to and push again.

- [ ] **Step 3: Write the runbook**

`docs/milestone-1-runbook.md`:

````markdown
# Milestone 1 runbook

Everything below runs on her Windows 11 laptop, at her usual desk, in her usual lighting.
Allow about an hour: 10 minutes setup, 15 minutes for the Teams test, 30 minutes of recording.

## 1. Setup (once)

1. Install Python 3.12 from python.org. On the first installer screen, tick **Add python.exe to PATH**.
2. Get the code. Either install Git for Windows and run `git clone https://github.com/joshuaknipe/hands-down.git`
   (sign in to GitHub when asked; the repo is private), or on the Mac run
   `git archive --format=zip -o halo.zip HEAD`, copy `halo.zip` over and unzip it.
3. In a terminal in the project folder:

   ```
   py -3.12 -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. Check Settings > Privacy & security > Camera: **Camera access** and **Let desktop apps access your camera** are on.
5. Close Teams and anything else that might be using the camera.

## 2. Probe the camera

```
python -m feasibility probe
```

Expect a line each for `dshow` and `msmf`, at least one saying it opened at 10+ fps.
If both fail, or the laptop has an external webcam too, try `--camera 1`, and add the same
`--camera` option to every command below.

## 3. Teams coexistence test

Have Teams open and signed in, but not in a meeting.

```
python -m feasibility coexist
```

Follow the prompts. Each backend is tested twice: once with Halo opening the camera first, once
with Teams first. When asked, start a "Meet now" meeting with the camera on, and answer honestly
whether her own video shows in Teams. Leave each meeting when told to.

The last line is the conclusion. It is one of:

- **OpenCV works alongside Teams** — no special camera handling is needed.
- **Only Windows shared capture works** — Halo's Windows camera code will use WinRT instead of OpenCV.
- **No backend worked** — Halo will need "pause for call".

If a backend gets stuck, press Ctrl+C, then rerun with the remaining backends only, for example
`python -m feasibility coexist --backends msmf,winrt_shared`.

## 4. Record clips

She sits as she normally works. For each label, run the command, then for each clip:
get her hand into position first, press **Space**, do what her hand naturally does there for
5–10 seconds, press **Space** again. **Q** quits. The preview shows green dots when a hand is
found; that is for reassurance only and is not saved.

Record **4 clips for each of these** (the 4th of each is set aside for later evaluation):

| Label | Hand position |
| --- | --- |
| `hair_scalp` | fingers in the hair on top or at the front of the head |
| `hair_crown` | fingers in the hair at the back or crown |
| `hair_side` | fingers in the hair beside the face or at the temple |
| `hair_long` | fingers in long hair below the jaw or over the shoulder |
| `ear_tuck` | tucking hair behind an ear |

Record **2 clips for each of these** (they are for later milestones):

| Label | Hand position |
| --- | --- |
| `chin_rest` | chin resting on the hand |
| `cheek_rest` | cheek resting on the hand |
| `glasses` | adjusting glasses |
| `drinking` | drinking from a cup or bottle |
| `phone` | phone held to the ear |

Example:

```
python -m feasibility record --label hair_scalp
```

Clips are saved in the `clips` folder on this laptop only. They are never uploaded and git
ignores them. She can watch or delete any clip at any time; delete a clip's `.mp4` and `.json`
together.

## 5. Analyse

```
python -m feasibility analyse
```

The table shows, per clip, the share of frames with a hand found (`hand`) and a face found
(`face`), and the longest stretch with no hand (`gap s`). The verdict line is:

- **GO** — at least 80% of hair clips had a hand found in at least 80% of frames.
- **NO-GO** — fewer did. Look at which labels fail and at the `face` column: a low face rate
  usually means the head is partly out of frame. Try raising or tilting the laptop screen,
  delete the clips, and record again before giving up.
- **INCOMPLETE** — some hair labels have fewer than 3 clips.

"Weak spots" lists labels where most clips failed; expect `hair_crown` here if the webcam crops
the top of her head.

## 6. Bring back the results

Copy the two newest files from the `reports` folder (`coexist-….json` and `analyse-….json`).
They contain numbers and labels only, no images. Record the two conclusions under milestone 1
in `plan.md`.

## 7. Afterwards

Keep the `clips` folder on her laptop for milestone 3, or delete it whenever she wants.
````

- [ ] **Step 4: Commit and push**

```bash
git add docs/milestone-1-runbook.md
git commit -m "Add milestone 1 runbook"
git push
```

---

## Self-review notes

- **Spec coverage (milestone 1):** hand visibility during real motions at her angle → Tasks 3, 5, 6, 7; both launch orders with OpenCV → Tasks 2, 8; whether shared access is available → Task 9 plus the Windows multi-app setting question in Task 8; go / no-go → `analyse` verdict and `coexist` conclusion, with the runbook mapping them to the spec's outcomes; clips recorded on her laptop, held-out split, privacy of clips → Tasks 4, 5, 10. Milestones 2–4 are out of scope for this plan.
- **Deliberately not built yet:** episode state machine, head zone, alerts, tray, packaging, meeting detection. They belong to milestone 2 and depend on milestone 1's answers.
