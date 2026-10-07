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
            if t.reminder_s > 0 and contact and now - self._last_alert >= t.reminder_s - 1e-9:
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
