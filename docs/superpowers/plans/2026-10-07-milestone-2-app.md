# Milestone 2 (Packaged Windows Baseline) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hands Down as a real tray app: it watches the webcam, detects a hand in the head zone, gives one gentle alert per episode, can be paused, logs episodes and "that wasn't me" marks for the trial, has a small settings window, and ships as a Windows build from CI.

**Architecture:** `handsdown/` grows a pure detection core (settings, head zone, episodes, event log) that is unit-tested without a camera, an `Engine` that runs camera → tracker → zone → episodes on a background thread, and a pystray tray icon on the main thread that drives it. The settings window is a separate tkinter process that writes the settings file; the engine reloads the file when it changes. PyInstaller builds a `--onedir` Windows app in CI, which runs a `--self-test` of the frozen build before uploading it.

**Tech Stack:** Python 3.12, MediaPipe 1.1.0, OpenCV 5, pystray 0.19.5, Pillow 12.3.0, platformdirs 4.12.3, tkinter (stdlib), winsound / winreg (stdlib, Windows), PyInstaller 6.22.3, GitHub Actions.

**Spec:** [plan.md](../../../plan.md), "Milestones" item 2, "Detection approach" (stage 1 and Episodes), "Alerts and app shell", "Cross-platform build and packaging", "Privacy". Milestone 1 code is in `handsdown/` and `feasibility/`.

## Global Constraints

- Everything in milestone 1's Global Constraints still holds (Python 3.12, `mediapipe==1.1.0`, no `opencv-python`, Tasks API only, `TimestampGuard` on every tracker call, no network at runtime, nothing user-visible names the behaviour, pathlib everywhere).
- **No images ever touch disk** in the app. The event log stores times, durations, states and marks only.
- **Commits:** one commit per working piece, not per task (user preference). Commit points: after Task 5 (detection core), after Task 9 (tray app), after Task 10 (Windows build). No `Co-Authored-By` or Claude attribution lines.
- **Crown contact is out of scope** (plan.md, Detection approach). No work to detect hands behind the head.
- **No global hotkey** in this milestone (user decision). Pause is from the tray menu only.
- Notification text is discreet: title "Hands Down", message "Gentle reminder". No other wording names what is being detected.
- `handsdown/` never imports from `feasibility/`.
- The camera is released whenever Hands Down is paused, quits, or loses the camera.
- Settings live in the per-user config folder and the event log in the per-user log folder (`platformdirs`, app name "Hands Down").
- Mac setup for the settings window: Homebrew's Python 3.12 has no tkinter; `brew install python-tk@3.12` adds it. Windows' python.org installer includes it.

## Before you start

This plan is self-contained, but the repository state it starts from is not obvious from a fresh checkout:

- **Starting point:** `main` contains all of milestone 1 (tag-free; the last milestone 1 commit is "Guide clip recording in the recorder window"). Create the working branch with `git checkout -b milestone-2 main`. If `origin/main` still shows commits with `Co-Authored-By` lines, the owner has not yet force-pushed the rewritten history: stop and ask them, do not merge or pull it.
- **Environment (Mac):** `python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt`. The settings window (Task 9) also needs `brew install python-tk@3.12`; ask the owner to run it.
- **Camera access:** macOS must allow the terminal or editor to use the camera. Steps that need someone at the camera or watching the screen say "checked by your human partner"; ask them, do not skip.
- **Recorded clips:** Task 5 evaluates the clips in `clips/` (git-ignored, on the owner's Mac only). If they are missing, that step says what to do.
- **Background:** [plan.md](../../../plan.md) is the design. Milestone 1's plan ([2026-10-07-milestone-1-feasibility.md](2026-10-07-milestone-1-feasibility.md)) explains the existing `handsdown/` and `feasibility/` code. The milestone 1 rehearsal found the hand in 92–100% of frames for every position except the crown (1–25%), which is why the crown is out of scope.

## Review Focus

1. **A hand-edited or corrupt settings file** (wrong types, out-of-range numbers, broken JSON). The app must start with defaults or clamped values, not crash. Tests: `test_load_settings_survives_bad_files`, `test_load_settings_ignores_wrong_types_and_clamps` (Task 1).
2. **Teams takes the camera mid-session** (reads start failing). The engine must release the camera, show "camera in use", retry, and recover when it is free, without crashing or blocking. Tests: `test_failed_reads_mark_camera_busy_and_release`, `test_busy_camera_is_retried_until_it_opens` (Task 7).
3. **Her face is lost briefly mid-episode** (she looks down). There must be no second alert, and "not tracking" only shows after sustained loss. Tests: `test_gap_shorter_than_grace_keeps_the_episode` (Task 3), `test_not_tracking_only_after_sustained_face_loss` (Task 7).
4. **Pausing during an active episode.** The episode is logged as interrupted, the camera released, and no alert fires while paused. Test: `test_pause_interrupts_episode_releases_camera_and_silences_alerts` (Task 7).
5. **The chime or notification fails** (no audio device, Focus Assist, missing file). The failure is logged and the engine keeps running. Test: `test_alerter_survives_failing_outputs` (Task 6).

---

## File structure

```
handsdown/
  paths.py            + settings_path(), log_dir()
  settings.py         Settings dataclass, limits, load/save, SettingsStore (reloads on change)
  landmarks.py        + Observation.face_box, bounding_box()
  zone.py             head zone geometry and contact(observation, margin)
  episodes.py         EpisodeTracker: dwell, grace, release, reminder, reset
  eventlog.py         EventLog: append-only JSON lines, thread-safe
  chime.py            generates assets/chime.wav
  alerts.py           play_chime, mac_notify, Alerter
  camera.py           + open_first_camera()
  engine.py           Engine: the background camera loop
  tray.py             draw_icon, STATE_LABELS, menu_items
  app.py              run_app(): wires tray, engine, alerts, settings, log
  settings_window.py  tkinter settings window (separate process)
  startup.py          start with Windows via the per-user Run registry key
  __main__.py         python -m handsdown [--settings | --self-test]
assets/chime.wav      the alert sound (committed)
feasibility/evaluate.py   run the stage 1 detector over recorded clips
packaging/launcher.py     PyInstaller entry point
packaging/handsdown.spec  PyInstaller spec
docs/install-windows.md   installing the build on her laptop
.github/workflows/tests.yml  + build job
tests/test_settings.py, test_zone.py, test_episodes.py, test_eventlog.py, test_evaluate.py,
tests/test_alerts.py, test_engine.py, test_tray.py, test_settings_window.py
```

---

### Task 1: Settings and per-user folders

**Files:**
- Create: `handsdown/settings.py`, `tests/test_settings.py`
- Modify: `handsdown/paths.py`, `tests/test_paths.py`, `requirements.txt`

**Interfaces:**
- Produces:
  - `handsdown.paths.APP_NAME = "Hands Down"`, `settings_path() -> Path`, `log_dir() -> Path`
  - `handsdown.settings.Settings` (frozen dataclass): `dwell_s=0.5, grace_s=1.0, release_s=3.0, reminder_s=0.0, zone_margin=0.5, chime=True, notification=False, start_with_windows=False, camera_index=0`
  - `handsdown.settings.LIMITS: dict[str, tuple[float, float]]`, `clamp(settings) -> Settings`
  - `load_settings(path, warn=print) -> Settings`, `save_settings(path, settings) -> None`
  - `SettingsStore(path, warn=print)` with `get() -> Settings` (re-reads the file when its modification time changes)

- [ ] **Step 1: Add the dependency and install**

Append to `requirements.txt`:

```
platformdirs==4.12.3
```

Run: `.venv/bin/pip install -r requirements-dev.txt`

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_paths.py`:

```python
def test_user_folders_are_named_for_the_app():
    assert paths.settings_path().name == "settings.json"
    assert "Hands Down" in str(paths.settings_path())
    assert "Hands Down" in str(paths.log_dir())
```

`tests/test_settings.py`:

```python
import json
import os

from handsdown.settings import LIMITS, Settings, SettingsStore, clamp, load_settings, save_settings


def test_missing_file_gives_defaults(tmp_path):
    assert load_settings(tmp_path / "settings.json") == Settings()


def test_settings_round_trip(tmp_path):
    path = tmp_path / "sub" / "settings.json"
    custom = Settings(dwell_s=1.5, chime=False, notification=True, camera_index=1)
    save_settings(path, custom)
    assert load_settings(path) == custom


def test_load_settings_survives_bad_files(tmp_path):
    path = tmp_path / "settings.json"
    warnings = []
    for text in ("{not json", "[1, 2]", ""):
        path.write_text(text)
        assert load_settings(path, warn=warnings.append) == Settings()
    assert len(warnings) == 3


def test_load_settings_ignores_wrong_types_and_clamps(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "dwell_s": 99, "grace_s": "long", "chime": "yes", "camera_index": 2.5,
        "zone_margin": -1, "from_a_newer_version": True,
    }))
    loaded = load_settings(path)
    assert loaded.dwell_s == LIMITS["dwell_s"][1]
    assert loaded.zone_margin == LIMITS["zone_margin"][0]
    assert loaded.grace_s == Settings().grace_s
    assert loaded.chime is True and loaded.camera_index == 0


def test_clamp_keeps_values_in_range():
    assert clamp(Settings(release_s=0.0)).release_s == LIMITS["release_s"][0]
    assert clamp(Settings()) == Settings()


def test_store_reloads_when_the_file_changes(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    assert store.get() == Settings()
    save_settings(path, Settings(dwell_s=2.0))
    os.utime(path, ns=(1, 1_000_000_000))  # make sure the modification time differs
    assert store.get().dwell_s == 2.0
    path.unlink()
    assert store.get() == Settings()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_settings.py tests/test_paths.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'handsdown.settings'` (and `AttributeError` for `settings_path`)

- [ ] **Step 4: Implement**

Append to `handsdown/paths.py` (and add `from platformdirs import user_config_path, user_log_path` to its imports):

```python
APP_NAME = "Hands Down"


def settings_path() -> Path:
    return user_config_path(APP_NAME, appauthor=False) / "settings.json"


def log_dir() -> Path:
    return user_log_path(APP_NAME, appauthor=False)
```

`handsdown/settings.py`:

```python
"""Hands Down settings: defaults, limits, and a JSON file in the per-user config folder.

A hand-edited or corrupt file never stops the app: unreadable files give the defaults,
unknown keys and wrong types are ignored, and numbers are clamped to sensible limits.
"""

import json
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Settings:
    dwell_s: float = 0.5  # contact must last this long before an alert
    grace_s: float = 1.0  # gaps in contact or tracking shorter than this are ignored
    release_s: float = 3.0  # an episode ends after this long with no contact
    reminder_s: float = 0.0  # repeat the alert after this long in one episode; 0 is off
    zone_margin: float = 0.5  # how far the head zone reaches beside the face, in face widths
    chime: bool = True
    notification: bool = False
    start_with_windows: bool = False
    camera_index: int = 0


LIMITS = {
    "dwell_s": (0.2, 5.0),
    "grace_s": (0.0, 5.0),
    "release_s": (0.5, 30.0),
    "reminder_s": (0.0, 600.0),
    "zone_margin": (0.1, 1.5),
    "camera_index": (0, 9),
}


def clamp(settings: Settings) -> Settings:
    changes = {name: min(max(getattr(settings, name), low), high) for name, (low, high) in LIMITS.items()}
    return replace(settings, **changes)


def _accepts(default, value) -> bool:
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, int):
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def load_settings(path: Path, warn: Callable[[str], None] = print) -> Settings:
    if not path.is_file():
        return Settings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        warn(f"Settings file unreadable, using defaults: {exc}")
        return Settings()
    if not isinstance(data, dict):
        warn("Settings file is not a JSON object, using defaults")
        return Settings()
    defaults = Settings()
    values = {}
    for f in fields(Settings):
        if f.name in data and _accepts(getattr(defaults, f.name), data[f.name]):
            value = data[f.name]
            values[f.name] = float(value) if isinstance(getattr(defaults, f.name), float) else value
    return clamp(Settings(**values))


def save_settings(path: Path, settings: Settings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    temp.replace(path)  # the engine never sees a half-written file


class SettingsStore:
    """The current settings, re-read whenever the settings file changes on disk."""

    def __init__(self, path: Path, warn: Callable[[str], None] = print):
        self._path = path
        self._warn = warn
        self._stamp: int | None = None
        self._settings = Settings()

    def get(self) -> Settings:
        try:
            stamp = self._path.stat().st_mtime_ns
        except OSError:
            stamp = None
        if stamp != self._stamp:
            self._stamp = stamp
            self._settings = load_settings(self._path, self._warn)
        return self._settings
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_settings.py tests/test_paths.py -q`
Expected: all passed

---

### Task 2: Face box and head-zone contact

**Files:**
- Create: `handsdown/zone.py`, `tests/test_zone.py`
- Modify: `handsdown/landmarks.py`, `tests/test_landmarks.py`

**Interfaces:**
- Consumes: `handsdown.landmarks.Observation`, `Tracker`
- Produces:
  - `handsdown.landmarks.Box = tuple[float, float, float, float]` (x0, y0, x1, y1, normalised)
  - `Observation(timestamp_ms, hands, face_found, face_box: Box | None = None)`: the new field defaults to `None`, so milestone 1 code is unaffected
  - `handsdown.landmarks.bounding_box(points) -> Box`
  - `handsdown.zone.Zone(outer: Box, excluded: Box)` with `contains(x, y) -> bool`
  - `handsdown.zone.head_zone(face: Box, margin: float) -> Zone`, `hand_in_zone(hand, zone) -> bool`, `contact(observation, margin) -> bool`
  - Constants `ABOVE = 0.7`, `BELOW = 0.8`, `MIN_POINTS = 3`

**Geometry.** The face mesh stops at the forehead, so the zone reaches `ABOVE` face heights higher for the scalp, `margin` face widths to each side, and `BELOW` face heights under the chin for hair past the jaw. A box over the mouth and chin is cut out: hands there are usually resting on the chin or holding a cup. Contact needs `MIN_POINTS` of the hand's 21 landmarks inside, so a fingertip grazing the edge does not count.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_landmarks.py`:

```python
from handsdown.landmarks import bounding_box


def test_bounding_box_of_points():
    assert bounding_box([(0.4, 0.5), (0.6, 0.3), (0.5, 0.7)]) == (0.4, 0.3, 0.6, 0.7)


def test_tracker_reports_no_face_box_without_a_face():
    with Tracker() as tracker:
        assert tracker.process(np.zeros((480, 640, 3), np.uint8), 0).face_box is None


def test_observation_face_box_defaults_to_none():
    assert Observation(0, (), True).face_box is None
```

`tests/test_zone.py`:

```python
import pytest

from handsdown.landmarks import Observation
from handsdown.zone import contact, hand_in_zone, head_zone

FACE = (0.4, 0.3, 0.6, 0.6)  # 0.2 wide, 0.3 tall


def hand_at(x, y, n=21):
    return tuple((x, y) for _ in range(n))


def test_zone_reaches_above_beside_and_below_the_face():
    zone = head_zone(FACE, margin=0.5)
    assert zone.outer == pytest.approx((0.3, 0.09, 0.7, 0.84))


def test_mouth_and_chin_are_cut_out():
    zone = head_zone(FACE, margin=0.5)
    assert zone.excluded == pytest.approx((0.44, 0.465, 0.56, 0.705))
    assert not zone.contains(0.5, 0.55)  # chin
    assert zone.contains(0.5, 0.2)  # scalp above the face
    assert zone.contains(0.33, 0.45)  # beside the face
    assert zone.contains(0.38, 0.8)  # long hair below the jaw, to the side


@pytest.mark.parametrize("x, y, expected", [
    (0.33, 0.4, True),  # temple
    (0.5, 0.15, True),  # top of the head
    (0.5, 0.6, False),  # chin rest
    (0.9, 0.5, False),  # far away
])
def test_hand_in_zone(x, y, expected):
    assert hand_in_zone(hand_at(x, y), head_zone(FACE, 0.5)) is expected


def test_a_couple_of_fingertips_on_the_edge_are_not_contact():
    hand = hand_at(0.33, 0.4, n=2) + hand_at(0.9, 0.5, n=19)
    assert not hand_in_zone(hand, head_zone(FACE, 0.5))


def test_contact_needs_a_face_and_a_hand_in_the_zone():
    temple = (hand_at(0.33, 0.4),)
    assert contact(Observation(0, temple, True, FACE), 0.5)
    assert not contact(Observation(0, temple, False, None), 0.5)
    assert not contact(Observation(0, (), True, FACE), 0.5)
    assert contact(Observation(0, (hand_at(0.9, 0.5),) + temple, True, FACE), 0.5)  # either hand counts


def test_wider_margin_reaches_further():
    hand = hand_at(0.27, 0.4)
    assert not hand_in_zone(hand, head_zone(FACE, 0.5))
    assert hand_in_zone(hand, head_zone(FACE, 0.8))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_zone.py tests/test_landmarks.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'handsdown.zone'` and `ImportError: cannot import name 'bounding_box'`

- [ ] **Step 3: Implement**

In `handsdown/landmarks.py`: below `Point = tuple[float, float]` add

```python
Box = tuple[float, float, float, float]  # x0, y0, x1, y1, normalised to the frame


def bounding_box(points) -> Box:
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return (min(xs), min(ys), max(xs), max(ys))
```

add the field to `Observation` after `face_found`:

```python
    face_box: Box | None = None  # bounding box of the face landmarks, when a face is found
```

and in `Tracker.process`, replace the `return Observation(...)` with:

```python
        face_box = bounding_box([(lm.x, lm.y) for lm in face.face_landmarks[0]]) if face.face_landmarks else None
        return Observation(
            timestamp_ms,
            tuple(tuple((lm.x, lm.y) for lm in hand) for hand in hands.hand_landmarks),
            face_box is not None,
            face_box,
        )
```

`handsdown/zone.py`:

```python
"""Stage 1 detection: is a hand in the zone around her head?

Coordinates are normalised to the frame. The zone is built from the face's bounding box:
it covers hair above, beside and below the face, with the mouth and chin cut out.
"""

from dataclasses import dataclass

from handsdown.landmarks import Box, Observation

ABOVE = 0.7  # face heights above the face box (the face mesh stops at the forehead)
BELOW = 0.8  # face heights below it, for hair that hangs past the jaw
MIN_POINTS = 3  # hand landmarks that must be inside the zone to count as contact


@dataclass(frozen=True)
class Zone:
    outer: Box
    excluded: Box  # mouth and chin: hands here are usually resting or holding a cup

    def contains(self, x: float, y: float) -> bool:
        return _inside(self.outer, x, y) and not _inside(self.excluded, x, y)


def _inside(box: Box, x: float, y: float) -> bool:
    x0, y0, x1, y1 = box
    return x0 <= x <= x1 and y0 <= y <= y1


def head_zone(face: Box, margin: float) -> Zone:
    x0, y0, x1, y1 = face
    w, h = x1 - x0, y1 - y0
    outer = (x0 - margin * w, y0 - ABOVE * h, x1 + margin * w, y1 + BELOW * h)
    excluded = (x0 + 0.2 * w, y0 + 0.55 * h, x1 - 0.2 * w, y1 + 0.35 * h)
    return Zone(outer, excluded)


def hand_in_zone(hand, zone: Zone) -> bool:
    return sum(zone.contains(x, y) for x, y in hand) >= MIN_POINTS


def contact(observation: Observation, margin: float) -> bool:
    if observation.face_box is None:
        return False
    zone = head_zone(observation.face_box, margin)
    return any(hand_in_zone(hand, zone) for hand in observation.hands)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q`
Expected: all passed (milestone 1 tests unaffected)

---

### Task 3: Episodes

**Files:**
- Create: `handsdown/episodes.py`, `tests/test_episodes.py`

**Interfaces:**
- Produces:
  - `Timing(dwell_s=0.5, grace_s=1.0, release_s=3.0, reminder_s=0.0)` (frozen)
  - `Episode(start: float, duration_s: float, alerted: bool, ended: str)`; `ended` is `"released"` or `"interrupted"`
  - `Event(kind: str, time: float, episode: Episode | None = None)`; `kind` is `"alert"`, `"reminder"` or `"episode"`
  - `EpisodeTracker(timing)` with attribute `timing` (assignable), `state` (`"idle" | "candidate" | "active"`), `update(now, contact) -> list[Event]`, `reset(now) -> list[Event]`

**Rules (from plan.md, Episodes):** contact starts a candidate. The candidate becomes active, and the alert fires, once contact has lasted `dwell_s` and contact is present now; gaps up to `grace_s` do not end it. A candidate with no contact for longer than `grace_s` was a brush and is dropped silently. An active episode ends, and is reported, after `release_s` without contact; its duration runs from the first to the last contact. With `reminder_s > 0`, an active episode repeats the alert every `reminder_s`. `reset` ends an active episode as interrupted.

- [ ] **Step 1: Write the failing tests**

`tests/test_episodes.py`:

```python
import pytest

from handsdown.episodes import EpisodeTracker, Timing


def run(tracker, start, end, contact, step=0.1):
    """Feed frames every `step` seconds from `start` to `end`; returns all events."""
    events = []
    t = start
    while t < end - 1e-9:
        events += tracker.update(round(t, 3), contact)
        t += step
    return events


def kinds(events):
    return [e.kind for e in events]


def test_a_brush_shorter_than_dwell_never_alerts():
    tracker = EpisodeTracker(Timing())
    events = run(tracker, 0.0, 0.3, True) + run(tracker, 0.3, 3.0, False)
    assert events == [] and tracker.state == "idle"


def test_held_contact_alerts_once_at_the_dwell_time():
    tracker = EpisodeTracker(Timing())
    events = run(tracker, 0.0, 5.0, True)
    assert kinds(events) == ["alert"]
    assert events[0].time == pytest.approx(0.5)


def test_gap_shorter_than_grace_keeps_the_episode():
    tracker = EpisodeTracker(Timing())
    events = run(tracker, 0.0, 1.0, True) + run(tracker, 1.0, 1.8, False) + run(tracker, 1.8, 3.0, True)
    assert kinds(events) == ["alert"]
    assert tracker.state == "active"


def test_gap_during_candidate_shorter_than_grace_still_alerts():
    tracker = EpisodeTracker(Timing())
    events = run(tracker, 0.0, 0.3, True) + run(tracker, 0.3, 0.6, False) + run(tracker, 0.6, 1.0, True)
    assert kinds(events) == ["alert"]


def test_episode_ends_after_release_time_without_contact():
    tracker = EpisodeTracker(Timing())
    events = run(tracker, 0.0, 2.0, True) + run(tracker, 2.0, 6.0, False)
    assert kinds(events) == ["alert", "episode"]
    episode = events[1].episode
    assert episode.start == 0.0 and episode.duration_s == pytest.approx(1.9)
    assert episode.alerted and episode.ended == "released"
    assert tracker.state == "idle"


def test_a_new_episode_can_alert_after_the_last_one_ends():
    tracker = EpisodeTracker(Timing())
    events = run(tracker, 0.0, 1.0, True) + run(tracker, 1.0, 5.0, False) + run(tracker, 5.0, 6.0, True)
    assert kinds(events) == ["alert", "episode", "alert"]


def test_reminder_repeats_the_alert_during_a_long_episode():
    tracker = EpisodeTracker(Timing(reminder_s=2.0))
    events = run(tracker, 0.0, 5.0, True)
    assert kinds(events) == ["alert", "reminder", "reminder"]
    assert [round(e.time, 1) for e in events] == [0.5, 2.5, 4.5]


def test_reset_interrupts_an_active_episode():
    tracker = EpisodeTracker(Timing())
    run(tracker, 0.0, 1.0, True)
    events = tracker.reset(1.5)
    assert kinds(events) == ["episode"] and events[0].episode.ended == "interrupted"
    assert tracker.state == "idle" and tracker.reset(2.0) == []


def test_reset_drops_a_candidate_silently():
    tracker = EpisodeTracker(Timing())
    run(tracker, 0.0, 0.3, True)
    assert tracker.reset(0.3) == [] and tracker.state == "idle"


def test_timing_changes_apply_immediately():
    tracker = EpisodeTracker(Timing(dwell_s=2.0))
    assert run(tracker, 0.0, 1.0, True) == []
    tracker.timing = Timing(dwell_s=0.5)
    assert kinds(run(tracker, 1.0, 1.2, True)) == ["alert"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_episodes.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'handsdown.episodes'`

- [ ] **Step 3: Implement `handsdown/episodes.py`**

```python
"""Turn per-frame contact into episodes: one alert per episode, with dwell, grace and release times.

Times are seconds on the caller's monotonic clock.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Timing:
    dwell_s: float = 0.5
    grace_s: float = 1.0
    release_s: float = 3.0
    reminder_s: float = 0.0  # 0 means no reminder


@dataclass(frozen=True)
class Episode:
    start: float
    duration_s: float  # first contact to last contact
    alerted: bool
    ended: str  # "released" or "interrupted"


@dataclass(frozen=True)
class Event:
    kind: str  # "alert", "reminder" or "episode"
    time: float
    episode: Episode | None = None


class EpisodeTracker:
    def __init__(self, timing: Timing):
        self.timing = timing
        self.state = "idle"
        self._start = 0.0
        self._last_contact = 0.0
        self._last_alert = 0.0

    def update(self, now: float, contact: bool) -> list[Event]:
        t = self.timing
        if contact:
            if self.state == "idle":
                self.state, self._start = "candidate", now
            self._last_contact = now
        if self.state == "candidate":
            if now - self._last_contact > t.grace_s:
                self.state = "idle"  # a brush, not an episode
            elif contact and now - self._start >= t.dwell_s - 1e-9:
                self.state, self._last_alert = "active", now
                return [Event("alert", now)]
        elif self.state == "active":
            if now - self._last_contact >= t.release_s:
                return [self._end(self._last_contact, "released")]
            if t.reminder_s > 0 and now - self._last_alert >= t.reminder_s - 1e-9:
                self._last_alert = now
                return [Event("reminder", now)]
        return []

    def reset(self, now: float) -> list[Event]:
        if self.state == "active":
            return [self._end(now, "interrupted")]
        self.state = "idle"
        return []

    def _end(self, end: float, how: str) -> Event:
        self.state = "idle"
        return Event("episode", end, Episode(self._start, round(end - self._start, 3), True, how))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_episodes.py -q`
Expected: all passed

---

### Task 4: Event log

**Files:**
- Create: `handsdown/eventlog.py`, `tests/test_eventlog.py`

**Interfaces:**
- Produces: `EventLog(folder: Path, now=datetime.now)` with property `path -> Path` (`folder / "events.jsonl"`), `write(kind: str, **fields) -> None` (thread-safe), `read() -> list[dict]` (skips unreadable lines)

**Record kinds used by later tasks:** `start`, `stop`, `state` (`state`), `alert` (`reminder: bool`), `episode` (`duration_s`, `alerted`, `ended`), `pause` (`reason`, `minutes`), `resume`, `false_alert` (`alert_time`), `error` (`message`). Every record has `time` (local ISO 8601, seconds) and `kind`. Never images.

- [ ] **Step 1: Write the failing tests**

`tests/test_eventlog.py`:

```python
import threading
from datetime import datetime

from handsdown.eventlog import EventLog


def test_write_and_read_back(tmp_path):
    log = EventLog(tmp_path / "logs", now=lambda: datetime(2026, 10, 7, 9, 30, 5))
    log.write("state", state="watching")
    log.write("episode", duration_s=2.5, alerted=True, ended="released")
    records = log.read()
    assert records[0] == {"time": "2026-10-07T09:30:05", "kind": "state", "state": "watching"}
    assert records[1]["kind"] == "episode" and records[1]["duration_s"] == 2.5
    assert log.path == tmp_path / "logs" / "events.jsonl"


def test_read_skips_damaged_lines(tmp_path):
    log = EventLog(tmp_path)
    log.write("start")
    with log.path.open("a", encoding="utf-8") as f:
        f.write('{"half a line\n')
    log.write("stop")
    assert [r["kind"] for r in log.read()] == ["start", "stop"]


def test_read_with_no_log_is_empty(tmp_path):
    assert EventLog(tmp_path / "none").read() == []


def test_writes_from_two_threads_do_not_interleave(tmp_path):
    log = EventLog(tmp_path)

    def burst(kind):
        for _ in range(200):
            log.write(kind, detail="x" * 200)

    threads = [threading.Thread(target=burst, args=(k,)) for k in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(log.read()) == 400
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_eventlog.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'handsdown.eventlog'`

- [ ] **Step 3: Implement `handsdown/eventlog.py`**

```python
"""Append-only log of what Hands Down saw and did: one JSON object per line, never images."""

import json
import threading
from datetime import datetime
from pathlib import Path


class EventLog:
    def __init__(self, folder: Path, now=datetime.now):
        self._folder = folder
        self._now = now
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._folder / "events.jsonl"

    def write(self, kind: str, **fields) -> None:
        record = {"time": self._now().isoformat(timespec="seconds"), "kind": kind, **fields}
        line = json.dumps(record) + "\n"
        with self._lock:
            self._folder.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line)

    def read(self) -> list[dict]:
        if not self.path.is_file():
            return []
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                records.append(json.loads(line))
            except ValueError:
                continue  # a line cut short by a crash or power loss
        return records
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_eventlog.py -q`
Expected: all passed

---

### Task 5: Evaluate the detector on recorded clips

**Files:**
- Create: `feasibility/evaluate.py`, `tests/test_evaluate.py`
- Modify: `feasibility/__main__.py` (add `evaluate`)

**Interfaces:**
- Consumes: `handsdown.zone.contact`, `handsdown.episodes.EpisodeTracker`, `Timing`, `handsdown.settings.Settings`, `feasibility.clips.load_clips`, `TRUE_POSITIVE_LABELS`, `LABELS`, `feasibility.analyse.read_frames`, `handsdown.landmarks.Tracker`
- Produces:
  - `ClipOutcome(label, split, video, contact_rate: float, alerted: bool, latency_s: float | None)`
  - `outcome_from(label, split, video, observations, settings) -> ClipOutcome`
  - `summary_lines(outcomes) -> list[str]`
  - `run_evaluate(clips_dir, settings) -> int`
  - CLI: `python -m feasibility evaluate [--margin M] [--dwell S]`

**Purpose.** The clip harness from plan.md: run the real stage 1 detector and episode logic over labelled clips, so zone and timing changes are measured instead of judged by feel. Hair clips should alert; other clips ideally should not. Clips are milestone 1 recordings, so this works on the rehearsal clips and later on hers.

- [ ] **Step 1: Write the failing tests**

`tests/test_evaluate.py`:

```python
from feasibility.evaluate import ClipOutcome, outcome_from, summary_lines
from handsdown.landmarks import Observation
from handsdown.settings import Settings

FACE = (0.4, 0.3, 0.6, 0.6)
TEMPLE = tuple((0.33, 0.4) for _ in range(21))


def frames(contact_flags, step_ms=100):
    return [Observation(i * step_ms, (TEMPLE,) if c else (), True, FACE) for i, c in enumerate(contact_flags)]


def test_held_contact_alerts_with_latency():
    outcome = outcome_from("hair_side", "dev", "a.mp4", frames([True] * 20), Settings())
    assert outcome.alerted and outcome.latency_s == 0.5 and outcome.contact_rate == 1.0


def test_brief_contact_does_not_alert():
    outcome = outcome_from("chin_rest", "dev", "b.mp4", frames([True] * 3 + [False] * 17), Settings())
    assert not outcome.alerted and outcome.latency_s is None
    assert outcome.contact_rate == 0.15


def test_empty_clip():
    outcome = outcome_from("glasses", "dev", "c.mp4", [], Settings())
    assert not outcome.alerted and outcome.contact_rate == 0.0


def test_summary_counts_hair_and_other_clips_separately():
    outcomes = [
        ClipOutcome("hair_side", "dev", "1.mp4", 1.0, True, 0.5),
        ClipOutcome("hair_side", "dev", "2.mp4", 0.2, False, None),
        ClipOutcome("chin_rest", "dev", "3.mp4", 0.9, True, 0.6),
    ]
    lines = summary_lines(outcomes)
    assert any(line.startswith("hair_side") and "1/2 alerted" in line for line in lines)
    assert any("Hair positions: 1/2 clips alerted" in line for line in lines)
    assert any("Other positions: 1/1 clips alerted" in line for line in lines)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_evaluate.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'feasibility.evaluate'`

- [ ] **Step 3: Implement `feasibility/evaluate.py`**

```python
"""Run the stage 1 detector and episode logic over recorded clips: which clips would alert?"""

from dataclasses import dataclass
from pathlib import Path

from feasibility.analyse import read_frames
from feasibility.clips import LABELS, TRUE_POSITIVE_LABELS, load_clips
from handsdown.episodes import EpisodeTracker, Timing
from handsdown.landmarks import Tracker
from handsdown.settings import Settings
from handsdown.zone import contact


@dataclass(frozen=True)
class ClipOutcome:
    label: str
    split: str
    video: str
    contact_rate: float
    alerted: bool
    latency_s: float | None  # clip start to first alert


def outcome_from(label: str, split: str, video: str, observations, settings: Settings) -> ClipOutcome:
    tracker = EpisodeTracker(Timing(settings.dwell_s, settings.grace_s, settings.release_s, 0.0))
    touching = 0
    alerted_at = None
    for o in observations:
        now = o.timestamp_ms / 1000
        hit = contact(o, settings.zone_margin)
        touching += hit
        for event in tracker.update(now, hit):
            if event.kind == "alert" and alerted_at is None:
                alerted_at = now
    start = observations[0].timestamp_ms / 1000 if observations else 0.0
    rate = touching / len(observations) if observations else 0.0
    latency = None if alerted_at is None else round(alerted_at - start, 2)
    return ClipOutcome(label, split, video, rate, alerted_at is not None, latency)


def summary_lines(outcomes: list[ClipOutcome]) -> list[str]:
    lines = []
    for label in LABELS:
        group = [o for o in outcomes if o.label == label]
        if not group:
            continue
        alerted = sum(o.alerted for o in group)
        contact_rate = sum(o.contact_rate for o in group) / len(group)
        latencies = [o.latency_s for o in group if o.latency_s is not None]
        latency = f"{sum(latencies) / len(latencies):.1f} s" if latencies else "-"
        lines.append(f"{label:<11} {alerted}/{len(group)} alerted   contact {contact_rate:>4.0%}   latency {latency}")
    hair = [o for o in outcomes if o.label in TRUE_POSITIVE_LABELS]
    other = [o for o in outcomes if o.label not in TRUE_POSITIVE_LABELS]
    lines.append("")
    lines.append(f"Hair positions: {sum(o.alerted for o in hair)}/{len(hair)} clips alerted (want all)")
    lines.append(f"Other positions: {sum(o.alerted for o in other)}/{len(other)} clips alerted (want none)")
    return lines


def run_evaluate(clips_dir: Path, settings: Settings) -> int:
    clips = load_clips(clips_dir)
    if not clips:
        print(f"No clips found in {clips_dir}. Record some first: python -m feasibility record")
        return 1
    outcomes = []
    for i, clip in enumerate(clips, 1):
        print(f"[{i}/{len(clips)}] {clip.meta.label}/{clip.video.name}")
        timestamps = clip.meta.timestamps_ms
        with Tracker() as tracker:
            observations = [tracker.process(frame, timestamps[n])
                            for n, frame in enumerate(read_frames(clip.video)) if n < len(timestamps)]
        outcomes.append(outcome_from(clip.meta.label, clip.meta.split, str(clip.video), observations, settings))
    print()
    for line in summary_lines(outcomes):
        print(line)
    return 0
```

- [ ] **Step 4: Add the CLI command**

In `feasibility/__main__.py`, add before `args = parser.parse_args(argv)`:

```python
    ev = sub.add_parser("evaluate", help="Run the stage 1 detector over recorded clips")
    ev.add_argument("--margin", type=float, default=None, help="head zone margin in face widths")
    ev.add_argument("--dwell", type=float, default=None, help="seconds of contact before an alert")
```

and before `return 2`:

```python
    if args.command == "evaluate":
        from dataclasses import replace

        from feasibility.evaluate import run_evaluate
        from handsdown.paths import clips_dir
        from handsdown.settings import Settings, clamp

        settings = Settings()
        if args.margin is not None:
            settings = replace(settings, zone_margin=args.margin)
        if args.dwell is not None:
            settings = replace(settings, dwell_s=args.dwell)
        return run_evaluate(clips_dir(), clamp(settings))
```

- [ ] **Step 5: Run all tests, then evaluate the rehearsal clips if they still exist**

Run: `.venv/bin/python -m pytest -q`
Expected: all passed

Run: `.venv/bin/python -m feasibility evaluate`
Expected, if the rehearsal clips are present: a per-label table and two summary lines. Hair positions other than `hair_crown` should mostly alert. Record the two summary lines in the ledger: they are the first measurement of stage 1. If `clips/` was deleted, the command prints "No clips found" and exits 1; note that in the ledger.

- [ ] **Step 6: Commit the detection core**

```bash
git add handsdown feasibility tests requirements.txt
git commit -m "Add the stage 1 detection core: settings, head zone, episodes and event log

The head zone is built from the face box with the mouth and chin cut out.
Episodes give one alert per episode with dwell, grace and release times.
python -m feasibility evaluate runs the detector over recorded clips."
```

---

### Task 6: Chime and alerts

**Files:**
- Create: `handsdown/chime.py`, `assets/chime.wav`, `handsdown/alerts.py`, `tests/test_alerts.py`

**Interfaces:**
- Consumes: `handsdown.paths.resource_path`, `handsdown.settings.Settings`
- Produces:
  - `handsdown.chime.RATE = 44100`, `chime() -> np.ndarray`, `write_wav(path, samples)`
  - `handsdown.alerts.NOTIFICATION_TITLE = "Hands Down"`, `NOTIFICATION_TEXT = "Gentle reminder"`
  - `play_chime(platform=sys.platform, runner=subprocess.Popen) -> None`
  - `mac_notify(title, text, runner=subprocess.Popen) -> None`
  - `Alerter(settings: Callable[[], Settings], sound: Callable[[], None], notify: Callable[[str, str], None], warn: Callable[[str], None])` with `alert(kind: str) -> None`

- [ ] **Step 1: Write the failing tests**

`tests/test_alerts.py`:

```python
import sys
import types
import wave

import numpy as np

from handsdown import alerts, chime
from handsdown.alerts import Alerter
from handsdown.paths import resource_path
from handsdown.settings import Settings


def test_chime_is_short_soft_and_starts_silent():
    samples = chime.chime()
    assert 0.5 < len(samples) / chime.RATE < 1.5
    assert np.abs(samples).max() <= 0.3
    assert abs(samples[0]) < 0.01


def test_write_wav_round_trip(tmp_path):
    path = tmp_path / "c.wav"
    chime.write_wav(path, chime.chime())
    with wave.open(str(path)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, chime.RATE)
        assert w.getnframes() == len(chime.chime())


def test_committed_chime_exists():
    assert resource_path("assets/chime.wav").stat().st_size > 10_000


def test_play_chime_on_mac_uses_afplay():
    calls = []
    alerts.play_chime(platform="darwin", runner=calls.append)
    assert calls == [["afplay", str(resource_path("assets/chime.wav"))]]


def test_play_chime_on_windows_plays_asynchronously(monkeypatch):
    played = []
    fake = types.SimpleNamespace(SND_FILENAME=1, SND_ASYNC=2, SND_NODEFAULT=4,
                                 PlaySound=lambda path, flags: played.append((path, flags)))
    monkeypatch.setitem(sys.modules, "winsound", fake)
    alerts.play_chime(platform="win32")
    assert played == [(str(resource_path("assets/chime.wav")), 7)]


def test_mac_notify_is_discreet():
    calls = []
    alerts.mac_notify("Hands Down", "Gentle reminder", runner=calls.append)
    assert calls[0][:2] == ["osascript", "-e"]
    assert 'display notification "Gentle reminder" with title "Hands Down"' in calls[0][2]


class Recorder:
    def __init__(self):
        self.sounds, self.notes, self.warnings = 0, [], []

    def sound(self):
        self.sounds += 1

    def notify(self, title, text):
        self.notes.append((title, text))


def test_alerter_uses_the_alert_types_chosen_in_settings():
    r = Recorder()
    settings = [Settings(chime=True, notification=False)]
    alerter = Alerter(lambda: settings[0], r.sound, r.notify, r.warnings.append)
    alerter.alert("alert")
    settings[0] = Settings(chime=False, notification=True)
    alerter.alert("reminder")
    assert r.sounds == 1
    assert r.notes == [(alerts.NOTIFICATION_TITLE, alerts.NOTIFICATION_TEXT)]


def test_alerter_survives_failing_outputs():
    warnings = []

    def broken(*args):
        raise OSError("no audio device")

    alerter = Alerter(lambda: Settings(chime=True, notification=True), broken, broken, warnings.append)
    alerter.alert("alert")
    assert len(warnings) == 2 and "no audio device" in warnings[0]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_alerts.py -q`
Expected: FAIL with `ImportError: cannot import name 'alerts' from 'handsdown'`

- [ ] **Step 3: Implement the chime and generate the WAV**

`handsdown/chime.py`:

```python
"""The alert sound: two soft descending tones. Run this module to regenerate assets/chime.wav."""

import wave
from pathlib import Path

import numpy as np

RATE = 44100


def _tone(freq: float, seconds: float, volume: float) -> np.ndarray:
    t = np.arange(int(RATE * seconds)) / RATE
    envelope = np.minimum(1.0, t / 0.01) * np.exp(-t * 6)  # 10 ms fade-in, then a soft decay
    return volume * envelope * np.sin(2 * np.pi * freq * t)


def chime() -> np.ndarray:
    return np.concatenate([_tone(880, 0.35, 0.25), _tone(660, 0.6, 0.25)])


def write_wav(path: Path, samples: np.ndarray) -> None:
    data = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "assets" / "chime.wav"
    out.parent.mkdir(exist_ok=True)
    write_wav(out, chime())
    print(f"Wrote {out}")
```

Run: `.venv/bin/python -m handsdown.chime && afplay assets/chime.wav`
Expected: `Wrote .../assets/chime.wav`, and a short, soft two-note chime plays.

- [ ] **Step 4: Implement `handsdown/alerts.py`**

```python
"""Gentle alerts: a soft chime and an optional notification. Nothing names what is being detected."""

import subprocess
import sys
from typing import Callable

from handsdown.paths import resource_path
from handsdown.settings import Settings

NOTIFICATION_TITLE = "Hands Down"
NOTIFICATION_TEXT = "Gentle reminder"


def play_chime(platform: str = sys.platform, runner=subprocess.Popen) -> None:
    path = str(resource_path("assets/chime.wav"))
    if platform == "win32":
        import winsound

        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    elif platform == "darwin":
        runner(["afplay", path])


def mac_notify(title: str, text: str, runner=subprocess.Popen) -> None:
    """Development fallback: pystray cannot show notifications on macOS."""
    runner(["osascript", "-e", f'display notification "{text}" with title "{title}"'])


class Alerter:
    def __init__(self, settings: Callable[[], Settings], sound: Callable[[], None],
                 notify: Callable[[str, str], None], warn: Callable[[str], None]):
        self._settings = settings
        self._sound = sound
        self._notify = notify
        self._warn = warn

    def alert(self, kind: str) -> None:
        """Fire the alert types chosen in settings. A failing output is reported, never raised."""
        settings = self._settings()
        if settings.chime:
            try:
                self._sound()
            except Exception as exc:
                self._warn(f"Chime failed: {exc}")
        if settings.notification:
            try:
                self._notify(NOTIFICATION_TITLE, NOTIFICATION_TEXT)
            except Exception as exc:
                self._warn(f"Notification failed: {exc}")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_alerts.py -q`
Expected: all passed

---

### Task 7: The engine (background camera loop)

**Files:**
- Create: `handsdown/engine.py`, `tests/test_engine.py`
- Modify: `handsdown/camera.py` (add `open_first_camera`)

**Interfaces:**
- Consumes: `Settings`, `EventLog`, `EpisodeTracker`, `Timing`, `contact`, `Tracker`, `open_camera`, `backends_for_platform`
- Produces:
  - `handsdown.camera.open_first_camera(index: int) -> cv2.VideoCapture | None` (first backend for this OS that delivers a real frame; buffer size 1 so frames are fresh)
  - `handsdown.engine.Engine(settings, log, alert, on_state, open_capture, tracker_factory=Tracker, clock=time.monotonic, wall=datetime.now)`
    - thread-safe from the tray: `pause(seconds: float | None, reason: str)`, `resume()`, property `paused`, `mark_false_alert() -> bool`, `stop()`
    - loop: `run()` (blocking; runs `tick()` until stopped), `tick() -> float` (one step; returns seconds to wait)
    - attribute `state`: `None` until the first step, then `"watching" | "not_tracking" | "camera_busy" | "paused"`
  - Constants `TARGET_FPS = 8.0`, `NOT_TRACKING_AFTER_S = 2.0`, `RETRY_CAMERA_S = 10.0`, `MAX_FAILED_READS = 10`

**Behaviour.** Paused: release the camera (ending any active episode as interrupted), show "paused", check again every 0.5 s; a timed pause resumes by itself. No camera: try to open it; on failure show "camera_busy" and retry every 10 s. Camera open: read a frame; 10 failed reads in a row mean another app took it, so release it and show "camera_busy". Each frame goes to the tracker, the head-zone contact goes to the episode tracker (with timings re-read from settings every frame), and events become alerts and log records. "not_tracking" shows after 2 s without a face. Every state change is logged. The tracker is recreated after the camera is released, since VIDEO mode state must not carry across a gap.

- [ ] **Step 1: Write the failing tests**

`tests/test_engine.py`:

```python
import numpy as np

from handsdown.engine import MAX_FAILED_READS, RETRY_CAMERA_S, Engine
from handsdown.eventlog import EventLog
from handsdown.landmarks import Observation
from handsdown.settings import Settings
from tests.helpers import FakeCapture, FakeClock

FACE = (0.4, 0.3, 0.6, 0.6)
TEMPLE = tuple((0.33, 0.4) for _ in range(21))
FRAME = np.full((48, 64, 3), 128, np.uint8)


class ScriptedTracker:
    """Returns whatever observation the test has put in world["observation"]."""

    def __init__(self, world):
        self.world = world
        self.closed = False

    def process(self, frame, timestamp_ms):
        return self.world["observation"]

    def close(self):
        self.closed = True


class Harness:
    def __init__(self, tmp_path, cameras=None, settings=None):
        self.clock = FakeClock(100.0)
        self.world = {"observation": Observation(0, (), True, FACE)}
        self.settings = settings or Settings()
        self.alerts, self.states, self.opened = [], [], []
        self.cameras = list(cameras) if cameras is not None else None
        self.log = EventLog(tmp_path)
        self.engine = Engine(lambda: self.settings, self.log, self.alerts.append, self.states.append,
                             self.open, tracker_factory=lambda: ScriptedTracker(self.world), clock=self.clock)

    def open(self, index):
        if self.cameras is None:
            cap = FakeCapture(reads=[(True, FRAME)] * 10_000)
        else:
            cap = self.cameras.pop(0) if self.cameras else None
        if cap is not None:
            self.opened.append(cap)
        return cap

    def run(self, seconds, step=0.125):
        end = self.clock.now + seconds
        while self.clock.now < end - 1e-9:
            self.engine.tick()
            self.clock.now += step

    def kinds(self):
        return [r["kind"] for r in self.log.read()]


def test_hand_in_zone_alerts_once_and_logs_it(tmp_path):
    h = Harness(tmp_path)
    h.run(1.0)
    assert h.states == ["watching"]
    h.world["observation"] = Observation(0, (TEMPLE,), True, FACE)
    h.run(2.0)
    assert h.alerts == ["alert"]
    assert h.kinds().count("alert") == 1


def test_episode_is_logged_when_the_hand_leaves(tmp_path):
    h = Harness(tmp_path)
    h.world["observation"] = Observation(0, (TEMPLE,), True, FACE)
    h.run(2.0)
    h.world["observation"] = Observation(0, (), True, FACE)
    h.run(4.0)
    episode = [r for r in h.log.read() if r["kind"] == "episode"][0]
    assert episode["alerted"] and episode["ended"] == "released" and episode["duration_s"] > 1.5


def test_not_tracking_only_after_sustained_face_loss(tmp_path):
    h = Harness(tmp_path)
    h.run(0.5)
    h.world["observation"] = Observation(0, (), False, None)
    h.run(1.5)
    assert h.states == ["watching"]
    h.run(1.0)
    assert h.states == ["watching", "not_tracking"]
    h.world["observation"] = Observation(0, (), True, FACE)
    h.run(0.25)
    assert h.states[-1] == "watching"


def test_pause_interrupts_episode_releases_camera_and_silences_alerts(tmp_path):
    h = Harness(tmp_path)
    h.world["observation"] = Observation(0, (TEMPLE,), True, FACE)
    h.run(1.0)
    h.engine.pause(None, "call")
    h.run(5.0)
    assert h.alerts == ["alert"]
    assert h.opened[0].released and h.states[-1] == "paused"
    episode = [r for r in h.log.read() if r["kind"] == "episode"][0]
    assert episode["ended"] == "interrupted"
    assert {"kind": "pause", "reason": "call", "minutes": None}.items() <= [r for r in h.log.read() if r["kind"] == "pause"][0].items()


def test_resume_reopens_the_camera(tmp_path):
    h = Harness(tmp_path)
    h.run(0.5)
    h.engine.pause(None, "call")
    h.run(0.5)
    h.engine.resume()
    h.run(0.5)
    assert len(h.opened) == 2 and h.states[-1] == "watching"
    assert not h.engine.paused


def test_timed_pause_resumes_by_itself(tmp_path):
    h = Harness(tmp_path)
    h.run(0.5)
    h.engine.pause(60, "15 min")
    h.run(30)
    assert h.states[-1] == "paused"
    h.run(31)
    assert h.states[-1] == "watching" and "resume" in h.kinds()


def test_busy_camera_is_retried_until_it_opens(tmp_path):
    h = Harness(tmp_path, cameras=[None, None, FakeCapture(reads=[(True, FRAME)] * 100)])
    assert h.engine.tick() == RETRY_CAMERA_S
    assert h.states == ["camera_busy"]
    h.engine.tick()
    h.engine.tick()
    assert h.states == ["camera_busy", "watching"]


def test_failed_reads_mark_camera_busy_and_release(tmp_path):
    bad = FakeCapture(reads=[(True, FRAME)] * 3)  # then every read fails
    h = Harness(tmp_path, cameras=[bad])
    for _ in range(3 + MAX_FAILED_READS):
        h.engine.tick()
    assert bad.released and h.states[-1] == "camera_busy"


def test_mark_false_alert_logs_the_last_alert_time(tmp_path):
    h = Harness(tmp_path)
    assert h.engine.mark_false_alert() is False
    h.world["observation"] = Observation(0, (TEMPLE,), True, FACE)
    h.run(1.0)
    assert h.engine.mark_false_alert() is True
    marks = [r for r in h.log.read() if r["kind"] == "false_alert"]
    assert len(marks) == 1 and marks[0]["alert_time"]


def test_settings_changes_apply_on_the_next_frame(tmp_path):
    h = Harness(tmp_path, settings=Settings(dwell_s=5.0))
    h.world["observation"] = Observation(0, (TEMPLE,), True, FACE)
    h.run(1.0)
    assert h.alerts == []
    h.settings = Settings(dwell_s=0.5)
    h.run(0.25)
    assert h.alerts == ["alert"]


def test_run_stops_releases_and_logs(tmp_path):
    import threading

    h = Harness(tmp_path)
    h.engine.clock = None  # run() uses the real wait, the fake clock stays put
    thread = threading.Thread(target=h.engine.run)
    thread.start()
    h.engine.stop()
    thread.join(2)
    assert not thread.is_alive()
    assert h.kinds()[0] == "start" and h.kinds()[-1] == "stop"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'handsdown.engine'`

- [ ] **Step 3: Add `open_first_camera` to `handsdown/camera.py`**

Append:

```python
def open_first_camera(index: int):
    """The first backend for this OS that delivers a real frame, or None if the camera is busy or missing."""
    for backend in backends_for_platform():
        result = open_camera(index, backend)
        if result.ok:
            result.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # read the newest frame, not a stale queued one
            return result.capture
    return None
```

- [ ] **Step 4: Implement `handsdown/engine.py`**

```python
"""The camera loop: camera, tracker, head-zone contact and episodes, run on a background thread.

The tray calls pause(), resume(), mark_false_alert() and stop() from its own thread.
Everything else happens on the engine thread, one tick() at a time.
"""

import math
import threading
import time
from datetime import datetime
from typing import Callable

from handsdown.episodes import EpisodeTracker, Event, Timing
from handsdown.eventlog import EventLog
from handsdown.landmarks import Tracker
from handsdown.settings import Settings
from handsdown.zone import contact

TARGET_FPS = 8.0
NOT_TRACKING_AFTER_S = 2.0  # no face for this long shows "not tracking"
RETRY_CAMERA_S = 10.0  # how often to retry a busy or missing camera
MAX_FAILED_READS = 10  # failed reads in a row before the camera counts as taken
PAUSED_CHECK_S = 0.5


class Engine:
    def __init__(self, settings: Callable[[], Settings], log: EventLog, alert: Callable[[str], None],
                 on_state: Callable[[str], None], open_capture: Callable[[int], object],
                 tracker_factory=Tracker, clock=time.monotonic, wall=datetime.now):
        self._settings = settings
        self._log = log
        self._alert = alert
        self._on_state = on_state
        self._open_capture = open_capture
        self._tracker_factory = tracker_factory
        self.clock = clock
        self._wall = wall
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._pause_until: float | None = None  # clock time to resume at; math.inf until resumed
        self._capture = None
        self._tracker = None
        self._failed_reads = 0
        self._last_face: float | None = None
        self._episodes = EpisodeTracker(Timing())
        self._last_alert_wall: datetime | None = None
        self.state: str | None = None

    # Called from the tray thread.

    def pause(self, seconds: float | None, reason: str) -> None:
        with self._lock:
            self._pause_until = math.inf if seconds is None else self._now() + seconds
        self._log.write("pause", reason=reason, minutes=None if seconds is None else round(seconds / 60))

    def resume(self) -> None:
        with self._lock:
            was_paused = self._pause_until is not None
            self._pause_until = None
        if was_paused:
            self._log.write("resume")

    @property
    def paused(self) -> bool:
        with self._lock:
            return self._pause_until is not None

    def mark_false_alert(self) -> bool:
        if self._last_alert_wall is None:
            return False
        self._log.write("false_alert", alert_time=self._last_alert_wall.isoformat(timespec="seconds"))
        return True

    def stop(self) -> None:
        self._stop.set()

    # The engine thread.

    def run(self) -> None:
        self._log.write("start")
        try:
            while not self._stop.is_set():
                self._stop.wait(self.tick())
        finally:
            self._release(self._now())
            self._log.write("stop")

    def tick(self) -> float:
        now = self._now()
        if self._check_paused(now):
            self._release(now)
            self._set_state("paused")
            return PAUSED_CHECK_S
        settings = self._settings()
        if self._capture is None:
            self._capture = self._open_capture(settings.camera_index)
            if self._capture is None:
                self._set_state("camera_busy")
                return RETRY_CAMERA_S
            self._failed_reads = 0
            self._last_face = now  # give the face a moment to be found before "not tracking"
        ok, frame = self._capture.read()
        if not ok:
            self._failed_reads += 1
            if self._failed_reads >= MAX_FAILED_READS:
                self._release(now)
                self._set_state("camera_busy")
                return RETRY_CAMERA_S
            return 0.1
        self._failed_reads = 0
        self._process(frame, now, settings)
        return max(0.0, 1 / TARGET_FPS - (self._now() - now))

    def _now(self) -> float:
        return (self.clock or time.monotonic)()

    def _check_paused(self, now: float) -> bool:
        with self._lock:
            if self._pause_until is not None and now >= self._pause_until:
                self._pause_until = None
                resumed = True
            else:
                resumed = False
            paused = self._pause_until is not None
        if resumed:
            self._log.write("resume")
        return paused

    def _process(self, frame, now: float, settings: Settings) -> None:
        if self._tracker is None:
            self._tracker = self._tracker_factory()
        observation = self._tracker.process(frame, int(now * 1000))
        if observation.face_found:
            self._last_face = now
        tracking = self._last_face is not None and now - self._last_face <= NOT_TRACKING_AFTER_S
        self._set_state("watching" if tracking else "not_tracking")
        self._episodes.timing = Timing(settings.dwell_s, settings.grace_s, settings.release_s, settings.reminder_s)
        for event in self._episodes.update(now, contact(observation, settings.zone_margin)):
            self._handle(event)

    def _handle(self, event: Event) -> None:
        if event.kind in ("alert", "reminder"):
            self._last_alert_wall = self._wall()
            self._log.write("alert", reminder=event.kind == "reminder")
            self._alert(event.kind)
        else:
            e = event.episode
            self._log.write("episode", duration_s=e.duration_s, alerted=e.alerted, ended=e.ended)

    def _release(self, now: float) -> None:
        for event in self._episodes.reset(now):
            self._handle(event)
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        if self._tracker is not None:
            self._tracker.close()
            self._tracker = None

    def _set_state(self, state: str) -> None:
        if state == self.state:
            return
        self.state = state
        self._log.write("state", state=state)
        self._on_state(state)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_engine.py -q`
Expected: all passed

---

### Task 8: Tray icon, menu and the app

**Files:**
- Create: `handsdown/tray.py`, `handsdown/app.py`, `handsdown/__main__.py`, `tests/test_tray.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: `Engine`, `SettingsStore`, `EventLog`, `Alerter`, `play_chime`, `mac_notify`, `open_first_camera`, `settings_path`, `log_dir`
- Produces:
  - `handsdown.tray.STATE_COLOURS`, `STATE_LABELS` (keys: `None`, `"watching"`, `"not_tracking"`, `"camera_busy"`, `"paused"`)
  - `draw_icon(state: str | None, size: int = 64) -> PIL.Image.Image`: a thin ring in the state's colour on a transparent background
  - `MenuItem(label: str, action: str | None, enabled: bool = True)` (frozen) and `menu_items(state, paused) -> list[MenuItem]`
  - `handsdown.app.run_app() -> int`, `handsdown.app.settings_command() -> list[str]`
  - `python -m handsdown` starts the app; `--settings` opens the settings window (Task 9); `--self-test` runs the build check (Task 10)

**Threads.** pystray must own the main thread on macOS, so `run_app` starts the engine thread from pystray's `setup` callback. The menu is rebuilt from `menu_items()` whenever pystray shows it, and `update_menu()` is called on every state change. Menu actions must take at most two arguments (pystray checks), so each is built by a small factory.

- [ ] **Step 1: Add the dependencies and install**

Append to `requirements.txt`:

```
pystray==0.19.5
Pillow==12.3.0
```

Run: `.venv/bin/pip install -r requirements-dev.txt`

- [ ] **Step 2: Write the failing tests**

`tests/test_tray.py`:

```python
import sys

import pytest

from handsdown import app
from handsdown.tray import STATE_COLOURS, STATE_LABELS, draw_icon, menu_items


@pytest.mark.parametrize("state", list(STATE_COLOURS))
def test_icon_is_a_ring_in_the_state_colour(state):
    image = draw_icon(state)
    assert image.size == (64, 64) and image.mode == "RGBA"
    assert image.getpixel((32, 32))[3] == 0  # centre is transparent
    assert image.getpixel((32, 9))[:3] == STATE_COLOURS[state]  # on the ring
    assert image.getpixel((1, 1))[3] == 0  # corner is transparent


def test_every_state_has_a_plain_label():
    for state in STATE_COLOURS:
        assert STATE_LABELS[state]
    joined = " ".join(STATE_LABELS.values()).lower()
    assert "hair" not in joined and "pull" not in joined


def test_menu_when_watching():
    items = menu_items("watching", paused=False)
    assert items[0].label == STATE_LABELS["watching"] and not items[0].enabled
    actions = [i.action for i in items[1:]]
    assert actions == ["pause_call", "pause_15", "pause_60", "false_alert", "settings", "open_log", "quit"]


def test_menu_when_paused_offers_resume_first():
    items = menu_items("paused", paused=True)
    assert [i.action for i in items[1:3]] == ["resume", "false_alert"]
    assert "pause_call" not in [i.action for i in items]


def test_settings_command_runs_this_module_from_source():
    assert app.settings_command() == [sys.executable, "-m", "handsdown", "--settings"]


def test_settings_command_in_a_frozen_build(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert app.settings_command() == [sys.executable, "--settings"]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_tray.py -q`
Expected: FAIL with `ImportError: cannot import name 'app' from 'handsdown'`

- [ ] **Step 4: Implement `handsdown/tray.py`**

```python
"""The tray icon (a thin ring whose colour shows the state) and its menu. Discreet if her screen is shared."""

from dataclasses import dataclass

from PIL import Image, ImageDraw

STATE_COLOURS = {
    None: (150, 150, 150),  # starting
    "watching": (88, 166, 160),
    "not_tracking": (214, 176, 92),
    "camera_busy": (205, 110, 92),
    "paused": (150, 150, 150),
}

STATE_LABELS = {
    None: "Starting",
    "watching": "Watching",
    "not_tracking": "Can't see you",
    "camera_busy": "Camera in use by another app",
    "paused": "Paused",
}


def draw_icon(state: str | None, size: int = 64) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pad = size // 8
    colour = STATE_COLOURS.get(state, STATE_COLOURS[None])
    ImageDraw.Draw(image).ellipse((pad, pad, size - 1 - pad, size - 1 - pad), outline=colour + (255,),
                                  width=max(2, size // 9))
    return image


@dataclass(frozen=True)
class MenuItem:
    label: str
    action: str | None
    enabled: bool = True


def menu_items(state: str | None, paused: bool) -> list[MenuItem]:
    items = [MenuItem(STATE_LABELS.get(state, STATE_LABELS[None]), None, enabled=False)]
    if paused:
        items.append(MenuItem("Resume", "resume"))
    else:
        items += [
            MenuItem("Pause for call", "pause_call"),
            MenuItem("Pause 15 minutes", "pause_15"),
            MenuItem("Pause 1 hour", "pause_60"),
        ]
    items += [
        MenuItem("That wasn't me", "false_alert"),
        MenuItem("Settings…", "settings"),
        MenuItem("Open log folder", "open_log"),
        MenuItem("Quit", "quit"),
    ]
    return items
```

- [ ] **Step 5: Implement `handsdown/app.py` and `handsdown/__main__.py`**

`handsdown/app.py`:

```python
"""Hands Down: the tray app that ties the camera loop, alerts, settings and log together."""

import os
import subprocess
import sys
import threading

import pystray

from handsdown.alerts import Alerter, mac_notify, play_chime
from handsdown.camera import open_first_camera
from handsdown.engine import Engine
from handsdown.eventlog import EventLog
from handsdown.paths import log_dir, settings_path
from handsdown.settings import SettingsStore
from handsdown.tray import STATE_LABELS, draw_icon, menu_items

PAUSES = {"pause_call": (None, "call"), "pause_15": (15 * 60, "15 min"), "pause_60": (60 * 60, "1 hour")}


def settings_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--settings"]
    return [sys.executable, "-m", "handsdown", "--settings"]


def open_folder(folder) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(folder)
    else:
        subprocess.Popen(["open", str(folder)])


def run_app() -> int:
    log = EventLog(log_dir())
    store = SettingsStore(settings_path(), warn=lambda message: log.write("error", message=message))
    icon = pystray.Icon("handsdown", draw_icon(None), "Hands Down")

    def notify(title: str, text: str) -> None:
        if sys.platform == "win32":
            icon.notify(text, title)
        else:
            mac_notify(title, text)

    alerter = Alerter(store.get, play_chime, notify, warn=lambda message: log.write("error", message=message))

    def on_state(state: str) -> None:
        icon.icon = draw_icon(state)
        icon.title = f"Hands Down - {STATE_LABELS[state]}"
        icon.update_menu()

    engine = Engine(store.get, log, alerter.alert, on_state, open_first_camera)

    def act(action: str) -> None:
        if action in PAUSES:
            seconds, reason = PAUSES[action]
            engine.pause(seconds, reason)
        elif action == "resume":
            engine.resume()
        elif action == "false_alert":
            engine.mark_false_alert()
        elif action == "settings":
            subprocess.Popen(settings_command())
        elif action == "open_log":
            open_folder(log_dir())
        elif action == "quit":
            engine.stop()
            icon.stop()
        icon.update_menu()

    def item(entry):
        return pystray.MenuItem(entry.label, lambda: act(entry.action), enabled=entry.enabled)

    icon.menu = pystray.Menu(lambda: (item(entry) for entry in menu_items(engine.state, engine.paused)))

    def setup(tray_icon) -> None:
        tray_icon.visible = True
        threading.Thread(target=engine.run, name="engine", daemon=True).start()

    icon.run(setup=setup)
    return 0
```

`handsdown/__main__.py`:

```python
"""python -m handsdown            start Hands Down in the tray
python -m handsdown --settings   open the settings window
python -m handsdown --self-test  check that a build can load its models and assets"""

import os
import sys

os.environ.setdefault("GLOG_minloglevel", "2")  # quieten MediaPipe's C++ logging


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--settings" in args:
        from handsdown.settings_window import run_settings_window

        return run_settings_window()
    if "--self-test" in args:
        from handsdown.selftest import run_self_test

        return run_self_test()
    from handsdown.app import run_app

    return run_app()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_tray.py -q`
Expected: all passed

- [ ] **Step 7: Run the app on the Mac**

Run: `.venv/bin/python -m handsdown` (leave it running)
Expected, checked by your human partner: a ring appears in the menu bar and turns teal within a few seconds; clicking it shows "Watching" and the menu. Holding a hand on the side of the head for a second plays the chime once. "Pause for call" turns the ring grey and the camera light goes off; "Resume" brings it back. "Open log folder" shows `events.jsonl` with state, alert and episode records. "Quit" removes the icon and the process exits. ("Settings…" works after Task 9.)

---

### Task 9: Settings window and start with Windows

**Files:**
- Create: `handsdown/settings_window.py`, `handsdown/startup.py`, `tests/test_settings_window.py`

**Interfaces:**
- Consumes: `Settings`, `clamp`, `load_settings`, `save_settings`, `settings_path`
- Produces:
  - `handsdown.settings_window.REMINDER_CHOICES`, `ZONE_CHOICES` (label → value dicts), `form_values(settings) -> dict`, `settings_from_form(values: dict, base: Settings) -> Settings`, `run_settings_window(path: Path | None = None) -> int`
  - `handsdown.startup.RUN_KEY`, `VALUE_NAME = "Hands Down"`, `launch_command() -> str | None`, `set_start_with_windows(enabled: bool, winreg=None) -> bool`

**Start with Windows.** plan.md says a Startup-folder shortcut; creating a `.lnk` needs pywin32. The per-user `Run` registry key does the same job with the standard library's `winreg`, so this task uses it (ruling to record in the ledger, and plan.md is updated to match). Only a packaged build registers itself: running from source has no stable command to start at sign-in.

- [ ] **Step 1: Install tkinter on the Mac**

tkinter ships with python.org Python on Windows but not with Homebrew's Python. Ask your human partner to run `brew install python-tk@3.12`, then check:

Run: `.venv/bin/python -c "import tkinter; print(tkinter.TkVersion)"`
Expected: a version number such as `9.0` or `8.6`

- [ ] **Step 2: Write the failing tests**

`tests/test_settings_window.py`:

```python
import sys

import pytest

from handsdown import startup
from handsdown.settings import Settings
from handsdown.settings_window import REMINDER_CHOICES, ZONE_CHOICES, form_values, settings_from_form


def test_form_shows_current_settings_in_plain_choices():
    values = form_values(Settings(reminder_s=60.0, zone_margin=0.8, chime=False))
    assert values["reminder"] == "Every minute" and values["zone"] == "Large"
    assert values["chime"] is False and values["dwell_s"] == 0.5


def test_unusual_values_show_the_closest_choice():
    assert form_values(Settings(reminder_s=50.0))["reminder"] == "Every minute"
    assert form_values(Settings(zone_margin=0.45))["zone"] == "Medium"


def test_form_round_trip_keeps_hidden_settings():
    base = Settings(grace_s=2.0, release_s=5.0)
    values = form_values(base) | {"dwell_s": 1.25, "notification": True, "reminder": "Off", "zone": "Small"}
    result = settings_from_form(values, base)
    assert result.dwell_s == 1.25 and result.notification and result.reminder_s == 0.0
    assert result.zone_margin == ZONE_CHOICES["Small"]
    assert (result.grace_s, result.release_s) == (2.0, 5.0)


def test_form_values_are_clamped():
    result = settings_from_form(form_values(Settings()) | {"dwell_s": 99.0, "camera_index": 42}, Settings())
    assert result.dwell_s == 5.0 and result.camera_index == 9


def test_every_choice_is_within_limits():
    assert set(REMINDER_CHOICES.values()) <= {0.0, 30.0, 60.0, 120.0}
    assert all(0.1 <= v <= 1.5 for v in ZONE_CHOICES.values())


class FakeKey:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


class FakeWinreg:
    HKEY_CURRENT_USER = "HKCU"
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self):
        self.values = {}

    def OpenKey(self, root, path, reserved, access):
        assert (root, path) == ("HKCU", startup.RUN_KEY)
        return FakeKey()

    def SetValueEx(self, key, name, reserved, kind, value):
        self.values[name] = value

    def DeleteValue(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


def test_packaged_build_registers_and_unregisters(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\HandsDown\HandsDown.exe")
    reg = FakeWinreg()
    assert startup.set_start_with_windows(True, winreg=reg) is True
    assert reg.values == {"Hands Down": r'"C:\Apps\HandsDown\HandsDown.exe"'}
    assert startup.set_start_with_windows(False, winreg=reg) is False
    assert reg.values == {}
    assert startup.set_start_with_windows(False, winreg=reg) is False  # already off is fine


def test_running_from_source_never_registers():
    reg = FakeWinreg()
    assert startup.launch_command() is None
    assert startup.set_start_with_windows(True, winreg=reg) is False
    assert reg.values == {}


@pytest.mark.skipif(sys.platform == "win32", reason="checks the non-Windows path")
def test_start_with_windows_does_nothing_elsewhere():
    assert startup.set_start_with_windows(True) is False
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_settings_window.py -q`
Expected: FAIL with `ImportError: cannot import name 'startup' from 'handsdown'`

- [ ] **Step 4: Implement `handsdown/startup.py`**

```python
"""Start Hands Down when she signs in to Windows, using the per-user Run registry key."""

import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Hands Down"


def launch_command() -> str | None:
    """Only a packaged build can start at sign-in; running from source has no stable command."""
    return f'"{sys.executable}"' if getattr(sys, "frozen", False) else None


def set_start_with_windows(enabled: bool, winreg=None) -> bool:
    """Register or unregister. Returns whether Hands Down is now set to start with Windows."""
    if winreg is None:
        if sys.platform != "win32":
            return False
        import winreg
    command = launch_command()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled and command:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
            return True
        try:
            winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass
        return False
```

- [ ] **Step 5: Implement `handsdown/settings_window.py`**

```python
"""The settings window. It runs as its own process (python -m handsdown --settings) so tkinter
never shares a thread with the tray icon, and saves to the settings file the app watches."""

import sys
from dataclasses import replace
from pathlib import Path

from handsdown import startup
from handsdown.paths import settings_path
from handsdown.settings import Settings, clamp, load_settings, save_settings

REMINDER_CHOICES = {"Off": 0.0, "Every 30 seconds": 30.0, "Every minute": 60.0, "Every 2 minutes": 120.0}
ZONE_CHOICES = {"Small": 0.3, "Medium": 0.5, "Large": 0.8}


def _closest(choices: dict, value: float) -> str:
    return min(choices, key=lambda label: abs(choices[label] - value))


def form_values(settings: Settings) -> dict:
    return {
        "chime": settings.chime,
        "notification": settings.notification,
        "dwell_s": settings.dwell_s,
        "reminder": _closest(REMINDER_CHOICES, settings.reminder_s),
        "zone": _closest(ZONE_CHOICES, settings.zone_margin),
        "start_with_windows": settings.start_with_windows,
        "camera_index": settings.camera_index,
    }


def settings_from_form(values: dict, base: Settings) -> Settings:
    return clamp(replace(
        base,
        chime=bool(values["chime"]),
        notification=bool(values["notification"]),
        dwell_s=round(float(values["dwell_s"]), 2),
        reminder_s=REMINDER_CHOICES[values["reminder"]],
        zone_margin=ZONE_CHOICES[values["zone"]],
        start_with_windows=bool(values["start_with_windows"]),
        camera_index=int(values["camera_index"]),
    ))


def run_settings_window(path: Path | None = None) -> int:
    import tkinter as tk
    from tkinter import ttk

    path = path or settings_path()
    base = load_settings(path)
    values = form_values(base)

    root = tk.Tk()
    root.title("Hands Down settings")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=16)
    frame.grid(sticky="nsew")

    chime = tk.BooleanVar(value=values["chime"])
    notification = tk.BooleanVar(value=values["notification"])
    dwell = tk.DoubleVar(value=values["dwell_s"])
    reminder = tk.StringVar(value=values["reminder"])
    zone = tk.StringVar(value=values["zone"])
    start = tk.BooleanVar(value=values["start_with_windows"])
    camera = tk.IntVar(value=values["camera_index"])

    row = 0

    def add(label: str, widget) -> None:
        nonlocal row
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 12))
        widget.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

    add("Alert sound", ttk.Checkbutton(frame, variable=chime))
    add("Notification", ttk.Checkbutton(frame, variable=notification))
    dwell_label = ttk.Label(frame, text=f"{dwell.get():.1f} s")
    slider = ttk.Scale(frame, from_=0.2, to=3.0, variable=dwell, length=180,
                       command=lambda _value: dwell_label.config(text=f"{dwell.get():.1f} s"))
    add("Wait before alerting", slider)
    dwell_label.grid(row=row - 1, column=2, sticky="w")
    add("Repeat while it continues", ttk.Combobox(frame, textvariable=reminder, state="readonly",
                                                  values=list(REMINDER_CHOICES), width=18))
    add("Area around the head", ttk.Combobox(frame, textvariable=zone, state="readonly",
                                             values=list(ZONE_CHOICES), width=18))
    if sys.platform == "win32":
        add("Start with Windows", ttk.Checkbutton(frame, variable=start))
    add("Camera number", ttk.Spinbox(frame, from_=0, to=9, textvariable=camera, width=5))

    def save() -> None:
        new = settings_from_form({
            "chime": chime.get(), "notification": notification.get(), "dwell_s": dwell.get(),
            "reminder": reminder.get(), "zone": zone.get(), "start_with_windows": start.get(),
            "camera_index": camera.get(),
        }, base)
        if sys.platform == "win32":
            new = replace(new, start_with_windows=startup.set_start_with_windows(new.start_with_windows))
        save_settings(path, new)
        root.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=row, column=0, columnspan=3, sticky="e", pady=(12, 0))
    ttk.Button(buttons, text="Cancel", command=root.destroy).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(buttons, text="Save", command=save).grid(row=0, column=1)
    root.mainloop()
    return 0
```

- [ ] **Step 6: Run all tests, then check the window and the full app on the Mac**

Run: `.venv/bin/python -m pytest -q`
Expected: all passed

Run: `.venv/bin/python -m handsdown --settings`
Expected, checked by your human partner: a small window titled "Hands Down settings" with the controls above (no "Start with Windows" on the Mac). Change "Wait before alerting", click Save, reopen: the change is kept.

Run: `.venv/bin/python -m handsdown`, then choose "Settings…" from the tray menu.
Expected: the same window opens while the tray keeps working; saving a longer wait is picked up by the running app (an alert now needs the longer contact).

- [ ] **Step 7: Update plan.md and commit the tray app**

In `plan.md`, "Cross-platform build and packaging", replace the "Start with Windows" bullet with:

```markdown
- **Start with Windows:** the packaged build adds itself to the per-user `Run` registry key, toggled from settings. (A Startup-folder shortcut would need pywin32 to create the `.lnk`.)
```

and in "Key decisions", change the Notifications row's Choice and Why to: `pystray's own notifications on Windows (osascript on the Mac for development)` / `Shown by the tray icon itself, so no extra library or app registration is needed`, with `desktop-notifier, plyer, win10toast` as Rejected.

```bash
git add handsdown tests requirements.txt assets plan.md
git commit -m "Add the Hands Down tray app

A tray icon shows the state and offers pause for call, timed pauses,
\"that wasn't me\", settings, the log folder and quit. The engine runs the
camera, head-zone detector and episodes on a background thread, releases
the camera when paused or when another app takes it, and logs states,
alerts, episodes and marks. Alerts are a soft chime and an optional
notification. Settings open in a small window and can start the packaged
app with Windows."
```

---

### Task 10: Windows build in CI

**Files:**
- Create: `handsdown/selftest.py`, `packaging/launcher.py`, `packaging/handsdown.spec`, `docs/install-windows.md`, `tests/test_selftest.py`
- Modify: `requirements-dev.txt`, `.github/workflows/tests.yml`

**Interfaces:**
- Consumes: `Tracker`, `resource_path`, `model_path`, `handsdown.__main__.main`
- Produces:
  - `handsdown.selftest.run_self_test() -> int` (0 when models load, the tracker runs on a blank frame, the chime exists, and the settings and log folders are writable; 1 otherwise, with the reason on stderr when there is one)
  - `dist/HandsDown/HandsDown.exe` from `pyinstaller packaging/handsdown.spec`
  - CI job `build` on windows-latest: builds, runs `HandsDown.exe --self-test`, uploads `HandsDown` as an artifact

- [ ] **Step 1: Write the failing test**

`tests/test_selftest.py`:

```python
from handsdown import selftest


def test_self_test_passes_from_source(monkeypatch, tmp_path):
    monkeypatch.setattr(selftest, "settings_path", lambda: tmp_path / "config" / "settings.json")
    monkeypatch.setattr(selftest, "log_dir", lambda: tmp_path / "logs")
    assert selftest.run_self_test() == 0


def test_self_test_fails_when_an_asset_is_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(selftest, "settings_path", lambda: tmp_path / "settings.json")
    monkeypatch.setattr(selftest, "log_dir", lambda: tmp_path / "logs")
    monkeypatch.setattr(selftest, "ASSETS", ("assets/missing.wav",))
    assert selftest.run_self_test() == 1
    assert "missing.wav" in capsys.readouterr().err
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_selftest.py -q`
Expected: FAIL with `ImportError: cannot import name 'selftest' from 'handsdown'`

- [ ] **Step 3: Implement `handsdown/selftest.py`**

```python
"""Check that a build can run: models load, the tracker works, assets exist, folders are writable.

CI runs this inside the frozen Windows build, where missing data files are the likeliest bug.
"""

import sys

import numpy as np

from handsdown.paths import log_dir, resource_path, settings_path

ASSETS = ("assets/chime.wav", "models/hand_landmarker.task", "models/face_landmarker.task")


def run_self_test() -> int:
    try:
        for asset in ASSETS:
            if not resource_path(asset).is_file():
                raise FileNotFoundError(f"missing {asset}")
        from handsdown.landmarks import Tracker

        with Tracker() as tracker:
            tracker.process(np.zeros((480, 640, 3), np.uint8), 0)
        for folder in (settings_path().parent, log_dir()):
            folder.mkdir(parents=True, exist_ok=True)
            probe = folder / ".selftest"
            probe.write_text("ok")
            probe.unlink()
    except Exception as exc:
        if sys.stderr:
            print(f"Self-test failed: {exc}", file=sys.stderr)
        return 1
    return 0
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_selftest.py -q`
Expected: 2 passed

- [ ] **Step 5: Add the PyInstaller files**

Append to `requirements-dev.txt`:

```
pyinstaller==6.22.3
```

`packaging/launcher.py`:

```python
"""PyInstaller entry point for Hands Down."""

import sys

from handsdown.__main__ import main

sys.exit(main())
```

`packaging/handsdown.spec`:

```python
# PyInstaller spec for Hands Down: a windowed --onedir build named HandsDown.
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

root = SPECPATH + "/.."

a = Analysis(
    [root + "/packaging/launcher.py"],
    pathex=[root],
    datas=[
        (root + "/models/hand_landmarker.task", "models"),
        (root + "/models/face_landmarker.task", "models"),
        (root + "/assets/chime.wav", "assets"),
        *collect_data_files("mediapipe"),
    ],
    binaries=collect_dynamic_libs("mediapipe"),
    hiddenimports=["pystray._win32", "PIL._tkinter_finder"],
    excludes=["feasibility", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="HandsDown", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="HandsDown")
```

- [ ] **Step 6: Build and self-test on the Mac**

PyInstaller cannot cross-compile, so this checks the spec and the frozen self-test on macOS only.

Run: `.venv/bin/pip install -r requirements-dev.txt && .venv/bin/pyinstaller --noconfirm --distpath build/dist --workpath build/work packaging/handsdown.spec && build/dist/HandsDown/HandsDown --self-test; echo "exit=$?"`
Expected: the build finishes and prints `exit=0`. If it prints a missing-file or import error, add the file to `datas` or the module to `hiddenimports` and rebuild. Record any additions as a ruling.

- [ ] **Step 7: Add the build job to CI**

Append to `.github/workflows/tests.yml`, under `jobs:` (same indentation as `windows:`):

```yaml
  build:
    needs: windows
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: requirements-dev.txt
      - run: python -m pip install -r requirements-dev.txt
      - run: pyinstaller --noconfirm packaging/handsdown.spec
      - name: Self-test the frozen build
        shell: pwsh
        run: |
          $p = Start-Process -FilePath "dist\HandsDown\HandsDown.exe" -ArgumentList "--self-test" -Wait -PassThru
          if ($p.ExitCode -ne 0) { throw "Self-test failed with exit code $($p.ExitCode)" }
      - uses: actions/upload-artifact@v4
        with:
          name: HandsDown
          path: dist/HandsDown
```

- [ ] **Step 8: Write the install guide**

`docs/install-windows.md`:

````markdown
# Installing Hands Down on Windows

1. Open the repository's **Actions** tab on GitHub, choose the latest green **tests** run on
   `main`, and download the **HandsDown** artifact (a zip).
2. Unzip it to `%LOCALAPPDATA%\Programs\HandsDown` (paste that into File Explorer's address bar;
   create the folder if needed).
3. Double-click `HandsDown.exe`. Windows SmartScreen will warn because the app is not signed:
   choose **More info**, then **Run anyway**. This happens once.
4. A ring appears in the system tray (click the **^** arrow by the clock if it is hidden; drag
   it onto the taskbar to keep it visible). Teal means watching.
5. Right-click the ring, choose **Settings…**, tick **Start with Windows**, and Save.

## Using it

- **Pause for call** before a Teams or Zoom call that needs the camera; **Resume** afterwards.
- **That wasn't me** marks the last alert as a false alarm. Please use it during the trial.
- **Open log folder** shows `events.jsonl`: times, durations and states only, never images.

## Updating

Quit Hands Down from the tray, replace the folder's contents with the new artifact, and start it again.
Settings and the log are kept, since they live in your user profile, not in the app folder.
````

- [ ] **Step 9: Push and check the Windows build**

Run:

```bash
git add handsdown/selftest.py packaging docs/install-windows.md tests/test_selftest.py requirements-dev.txt .github/workflows/tests.yml
git commit -m "Build Hands Down for Windows in CI

PyInstaller builds a windowed --onedir app; CI runs its --self-test (models,
tracker, chime, user folders) before uploading it as an artifact."
git push
```

Then watch the run: `gh run watch --exit-status $(gh run list --limit 1 --json databaseId --jq '.[0].databaseId')`
Expected: both jobs succeed, and the run has a **HandsDown** artifact. If the self-test step fails, read its log, fix the spec (missing data or hidden import), and push again; fold the fix into the same commit with `git commit --amend` only if the commit has not been pushed, otherwise make one follow-up commit.

Pushing requires the earlier force-push to have been done by your human partner (local `main` was rewritten); if `git push` is rejected as non-fast-forward, stop and ask them.

---

## Self-review notes

- **Spec coverage (milestone 2):** stage 1 head zone → Task 2; episodes with dwell, grace, release, reminder, reset → Tasks 3, 7; chime and notification → Task 6; tray with states, pause for call and timed pauses, "that wasn't me", open log, quit → Tasks 7, 8; event log of episodes, states and marks for the trial → Tasks 4, 7; settings window including start with Windows → Task 9; packaged build from CI with model loading checked in the frozen build → Task 10; camera released on pause and when another app takes it → Task 7. The clip harness from "Privacy and testing" → Task 5.
- **Deliberately not in this milestone:** hair segmentation (milestone 4), automatic meeting detection (waits for the Teams test on her laptop), global hotkey (user decision), crown detection (out of scope), a packaged Mac build (out of scope).
- **Waits on her laptop:** the Teams coexistence test. If it shows Teams and OpenCV cannot share the camera, nothing here changes: "Pause for call" is already the first menu item and the engine already handles a busy camera. If only shared capture works, `open_first_camera` is the one function to swap.
