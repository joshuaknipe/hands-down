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
        self.locked = False
        self.log = EventLog(tmp_path)
        self.engine = Engine(lambda: self.settings, self.log, self.alerts.append, self.states.append,
                             self.open, tracker_factory=lambda: ScriptedTracker(self.world), clock=self.clock,
                             is_locked=lambda: self.locked)

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


def test_locked_screen_pauses_until_unlocked(tmp_path):
    h = Harness(tmp_path)
    h.world["observation"] = Observation(0, (TEMPLE,), True, FACE)
    h.run(1.0)
    h.locked = True
    h.run(5.0)
    assert h.opened[0].released and h.states[-1] == "paused" and h.alerts == ["alert"]
    pauses = [r for r in h.log.read() if r["kind"] == "pause"]
    assert len(pauses) == 1 and pauses[0]["reason"] == "screen locked"
    assert [r["ended"] for r in h.log.read() if r["kind"] == "episode"] == ["interrupted"]
    h.locked = False
    h.run(0.5)
    assert h.states[-1] == "watching" and len(h.opened) == 2
    assert h.kinds().count("resume") == 1


def test_locked_screen_is_ignored_when_the_setting_is_off(tmp_path):
    h = Harness(tmp_path, settings=Settings(pause_when_locked=False))
    h.locked = True
    h.run(1.0)
    assert h.states == ["watching"] and "pause" not in h.kinds()


def test_unlocking_during_a_manual_pause_stays_paused(tmp_path):
    h = Harness(tmp_path)
    h.run(0.5)
    h.engine.pause(None, "call")
    h.locked = True
    h.run(1.0)
    h.locked = False
    h.run(1.0)
    assert h.states[-1] == "paused" and h.engine.paused
