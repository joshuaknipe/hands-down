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
