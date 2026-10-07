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
