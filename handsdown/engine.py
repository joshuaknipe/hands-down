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
