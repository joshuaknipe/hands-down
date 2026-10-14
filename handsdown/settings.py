"""Hands Down settings: defaults, limits, and a JSON file in the per-user config folder.

A hand-edited or corrupt file never stops the app: unreadable files give the defaults,
unknown keys and wrong types are ignored, and numbers are clamped to sensible limits.
"""

import json
import re
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Callable

SOUNDS = ("chime", "bell", "knock", "rising", "low", "buzz", "beeps", "warble", "honk")
TEXT_POSITIONS = ("top-left", "top-center", "top-right", "middle-left", "center", "middle-right",
                  "bottom-left", "bottom-center", "bottom-right")
LEGACY_VOLUMES = {"quiet": 44, "medium": 55, "normal": 63}  # the old three-step setting, in percent


@dataclass(frozen=True)
class Settings:
    dwell_s: float = 0.5  # contact must last this long before an alert
    grace_s: float = 1.0  # gaps in contact or tracking shorter than this are ignored
    release_s: float = 3.0  # an episode ends after this long with no contact
    reminder_s: float = 0.0  # repeat the alert after this long in one episode; 0 is off
    zone_margin: float = 0.5  # how far the head zone reaches beside the face, in face widths
    zone_above: float = 0.7  # how far it reaches above the face, in face heights
    zone_below: float = 0.8  # how far it reaches below the chin, in face heights
    chin_cutout: float = 1.0  # size of the ignored mouth and chin area; 0 is off
    chime: bool = True
    sound: str = "chime"  # one of SOUNDS
    volume: int = 63  # percent, on a loudness curve (see chime.gain); 63 is the sounds as stored
    notification: bool = False
    screen_border: bool = False  # screen effects last from the alert until the hand moves away
    border_color: str = "#db2929"
    border_width: int = 8  # points on macOS, pixels on Windows
    screen_text: bool = False
    custom_text: str = "Hands down"
    text_size: int = 32
    text_color: str = "#ffffff"
    text_background: bool = True
    text_background_color: str = "#151515"
    text_padding_x: int = 20
    text_padding_y: int = 16
    text_position: str = "center"
    screen_blur: bool = False
    blur_level: int = 15  # Gaussian blur radius, in screen points/pixels
    start_with_windows: bool = False
    camera_index: int = 0
    pause_when_locked: bool = True  # release the camera while the screen is locked


LIMITS = {
    "dwell_s": (0.2, 5.0),
    "grace_s": (0.0, 5.0),
    "release_s": (0.5, 30.0),
    "reminder_s": (0.0, 600.0),
    "zone_margin": (0.1, 1.5),
    "zone_above": (0.0, 1.5),
    "zone_below": (0.0, 2.0),
    "chin_cutout": (0.0, 2.0),
    "camera_index": (0, 9),
    "volume": (20, 100),
    "border_width": (1, 500),
    "text_size": (12, 160),
    "text_padding_x": (0, 300),
    "text_padding_y": (0, 200),
    "blur_level": (1, 50),
}

CHOICES = {"sound": SOUNDS, "text_position": TEXT_POSITIONS}


def clamp(settings: Settings) -> Settings:
    changes = {name: min(max(getattr(settings, name), low), high) for name, (low, high) in LIMITS.items()}
    defaults = Settings()
    for name in ("border_color", "text_color", "text_background_color"):
        color = getattr(settings, name)
        changes[name] = color.lower() if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else getattr(defaults, name)
    changes["custom_text"] = settings.custom_text[:500]
    for name, allowed in CHOICES.items():
        if getattr(settings, name) not in allowed:
            changes[name] = getattr(defaults, name)
    return replace(settings, **changes)


def _accepts(default, value) -> bool:
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, str):
        return isinstance(value, str)
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
    if isinstance(data.get("volume"), str):
        data["volume"] = LEGACY_VOLUMES.get(data["volume"], Settings().volume)
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
