"""Gentle alerts: a soft chime and an optional notification. Nothing names what is being detected."""

import subprocess
import sys
import zlib
from pathlib import Path
from typing import Callable

from handsdown.chime import gain, read_wav, sound_file, write_wav
from handsdown.paths import resource_path, sound_cache_dir
from handsdown.settings import Settings

NOTIFICATION_TITLE = "Hands Down"
NOTIFICATION_TEXT = "Gentle reminder"


def volume_file(sound: str, volume: int, cache: Path) -> Path:
    """The sound at this volume, written once to the cache folder; other cached volumes are removed.

    A file, not a volume flag, because winsound cannot set the volume of what it plays."""
    source = resource_path(sound_file(sound))
    stamp = zlib.crc32(source.read_bytes())  # a new version of the sound gets a new file
    path = cache / f"{sound}-{round(gain(volume) * 1000)}-{stamp:08x}.wav"
    if not path.is_file():
        cache.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        write_wav(temp, read_wav(source) * gain(volume))
        temp.replace(path)
        for old in cache.glob("*.wav"):
            if old != path:
                try:
                    old.unlink()
                except OSError:
                    pass  # still playing on Windows: removed next time
    return path


def play_chime(sound: str = "chime", volume: int = 63, platform: str = sys.platform,
               runner=subprocess.Popen, cache: Path | None = None) -> None:
    path = str(volume_file(sound, volume, cache or sound_cache_dir()))
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
