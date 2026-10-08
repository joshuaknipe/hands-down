"""Commands that start Hands Down's other windows as separate processes, from source or a frozen build.

Kept apart from app.py so the small windows can use them without loading the tray or the vision models.
"""

import sys


def _command(flag: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, flag]
    return [sys.executable, "-m", "handsdown", flag]


def settings_command() -> list[str]:
    return _command("--settings")


def camera_view_command() -> list[str]:
    return _command("--camera-view")


def border_command() -> list[str]:
    return _command("--border")


def summary_command() -> list[str]:
    return _command("--summary")
