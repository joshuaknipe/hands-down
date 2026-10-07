"""Is the screen locked? Used to release the camera while she is away. Never raises."""

import sys


def _windows_locked() -> bool:
    import ctypes

    user32 = ctypes.windll.user32
    desktop = user32.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_SWITCHDESKTOP
    if not desktop:
        return True  # the input desktop is the secure lock screen
    try:
        return not user32.SwitchDesktop(desktop)
    finally:
        user32.CloseDesktop(desktop)


def _mac_locked() -> bool:
    import Quartz

    session = Quartz.CGSessionCopyCurrentDictionary()
    return bool(session and session.get("CGSSessionScreenIsLocked", False))


CHECKS = {"win32": _windows_locked, "darwin": _mac_locked}


def is_screen_locked(platform: str = sys.platform, checks=CHECKS) -> bool:
    check = checks.get(platform)
    if check is None:
        return False
    try:
        return bool(check())
    except Exception:
        return False
