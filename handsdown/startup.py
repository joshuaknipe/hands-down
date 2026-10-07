"""Start Hands Down at sign-in: the per-user Run registry key on Windows, a LaunchAgent on macOS.

Only a packaged build registers itself: running from source has no stable command to start.
"""

import plistlib
import sys
from pathlib import Path

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


LAUNCH_AGENT_LABEL = "com.handsdown.app"
LAUNCH_AGENT_FILE = f"{LAUNCH_AGENT_LABEL}.plist"


def mac_app_bundle() -> Path | None:
    """The HandsDown.app this process runs from, when it is a packaged Mac build."""
    if not getattr(sys, "frozen", False):
        return None
    bundle = Path(sys.executable).parents[2]  # HandsDown.app/Contents/MacOS/HandsDown
    return bundle if bundle.suffix == ".app" else None


def set_start_at_login_mac(enabled: bool, agents_dir: Path | None = None) -> bool:
    """Add or remove a per-user login item. Returns whether Hands Down now starts at login."""
    agents_dir = agents_dir or Path.home() / "Library" / "LaunchAgents"
    agent = agents_dir / LAUNCH_AGENT_FILE
    bundle = mac_app_bundle()
    if enabled and bundle is not None:
        agents_dir.mkdir(parents=True, exist_ok=True)
        agent.write_bytes(plistlib.dumps({
            "Label": LAUNCH_AGENT_LABEL,
            "ProgramArguments": ["/usr/bin/open", "-a", str(bundle)],
            "RunAtLoad": True,
        }))
        return True
    agent.unlink(missing_ok=True)
    return False


def set_start_at_login(enabled: bool, platform: str = sys.platform) -> bool:
    if platform == "win32":
        return set_start_with_windows(enabled)
    if platform == "darwin":
        return set_start_at_login_mac(enabled)
    return False


def startup_label(platform: str = sys.platform) -> str | None:
    """The settings checkbox's wording, or None where starting at sign-in is not supported."""
    return {"win32": "Start with Windows", "darwin": "Start at login"}.get(platform)
