"""Only one copy of Hands Down runs at a time: a second copy would double every alert and fight for the camera.

The running copy holds an exclusive lock on a file in the settings folder. The operating system drops the
lock when the process exits, even after a crash, so a stale lock file never blocks a fresh start.
"""

import sys
from pathlib import Path


class Lock:
    def __init__(self, handle):
        self._handle = handle

    def release(self) -> None:
        if self._handle is None:
            return
        if sys.platform == "win32":
            import msvcrt

            self._handle.seek(0)
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
        self._handle.close()  # closing also drops an flock
        self._handle = None


def acquire(path: Path) -> Lock | None:
    """The lock, or None if another copy already holds it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    try:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return Lock(handle)
