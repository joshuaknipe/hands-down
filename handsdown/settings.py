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
