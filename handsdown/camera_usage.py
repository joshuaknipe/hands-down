"""Read OS camera activity without opening a capture session.

macOS tracks shared camera stream clients. Windows reads its per-user camera
activity and verifies the recorded app still has a running process. Camera activity is
best effort: unavailable APIs return None, never an invented busy/free result.
"""

import ntpath
import os
import sys
import time

from handsdown.mac_camera_activity import MacCameraActivity


def has_other_windows_camera_user(entries, running_paths, own_path: str) -> bool:
    """Ignore our executable and stale activity left by an app that has exited."""
    own = ntpath.normcase(own_path)
    running = {ntpath.normcase(path) for path in running_paths if ntpath.normcase(path) != own}
    for app, start, stop in entries:
        start = int.from_bytes(start, "little") if isinstance(start, bytes) else start
        stop = int.from_bytes(stop, "little") if isinstance(stop, bytes) else stop
        if not start or stop != 0:
            continue
        name = ntpath.normcase(app)
        if ntpath.isabs(name):
            if name in running:
                return True
        elif "_" in name:  # package family, e.g. MSTeams_8wekyb3d8bbwe
            package, publisher = name.rsplit("_", 1)
            for path in running:
                for part in path.split("\\"):
                    if part.startswith(package + "_") and part.endswith("__" + publisher):
                        return True
    return False


def _windows_running_paths() -> set[str]:
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    class ProcessEntry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32FirstW.restype = wintypes.BOOL
    kernel.Process32NextW.argtypes = kernel.Process32FirstW.argtypes
    kernel.Process32NextW.restype = wintypes.BOOL
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                 ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    paths = set()
    own_path = None
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        more = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        if not more:
            raise ctypes.WinError(ctypes.get_last_error())
        while more:
            process = kernel.OpenProcess(0x1000, False, entry.th32ProcessID)  # QUERY_LIMITED_INFORMATION
            if process:
                try:
                    size = wintypes.DWORD(32768)
                    path = ctypes.create_unicode_buffer(size.value)
                    if kernel.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(size)):
                        paths.add(path.value)
                        if entry.th32ProcessID == os.getpid():
                            own_path = path.value
                finally:
                    kernel.CloseHandle(process)
            more = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    if own_path is not None:
        paths.discard(own_path)  # source launches may report the base Python path rather than sys.executable
    return paths


def _windows_camera_entries():
    import winreg

    entries = []
    path = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam"
    def visit(key, app=""):
        try:
            start = winreg.QueryValueEx(key, "LastUsedTimeStart")[0]
            stop = winreg.QueryValueEx(key, "LastUsedTimeStop")[0]
            entries.append((app.replace("#", "\\"), start, stop))
        except FileNotFoundError:
            pass
        for i in range(winreg.QueryInfoKey(key)[0]):
            name = winreg.EnumKey(key, i)
            with winreg.OpenKey(key, name) as child:
                visit(child, name if not app or app == "NonPackaged" else app)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            visit(key)
    except FileNotFoundError:
        return None
    return entries


def _windows_camera_usage(_index: int) -> bool | None:
    # Windows activity does not identify the particular camera, so any other camera user pauses us.
    entries = _windows_camera_entries()
    if entries is None:
        return None
    return has_other_windows_camera_user(entries, _windows_running_paths(), sys.executable)


CHECKS = {"win32": _windows_camera_usage}


class CameraUsageMonitor:
    def __init__(self, check=None, clock=time.monotonic, warn=lambda _message: None):
        self._check = check if check is not None else (MacCameraActivity() if sys.platform == "darwin"
                                                      else CHECKS.get(sys.platform, lambda _index: None))
        self._clock = clock
        self._warn = warn
        self._next = 0.0
        self._index = None
        self._value = None
        self._warned = False
        self._capture_active = False

    def set_capture_active(self, active: bool) -> None:
        if active != self._capture_active:
            self._capture_active = active
            self._next = 0.0
        setter = getattr(self._check, "set_capture_active", None)
        if setter is not None:
            setter(active)

    def __call__(self, index: int) -> bool | None:
        now = self._clock()
        if index != self._index or now >= self._next:
            self._index = index
            self._next = now + 1.0
            try:
                self._value = self._check(index)
                self._warned = False
            except Exception as exc:
                self._value = None
                if not self._warned:
                    self._warn(f"Camera activity check unavailable: {exc}")
                    self._warned = True
        return self._value

    def close(self) -> None:
        close = getattr(self._check, "close", None)
        if close is not None:
            close()
