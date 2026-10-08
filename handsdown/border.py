"""The optional red border round the screen, shown from the alert until the hand leaves the head zone.

Like the camera view, it runs as its own process (python -m handsdown --border) so no window
toolkit shares a thread with the tray icon. The app writes "show" and "hide" lines to its stdin;
the border closes when stdin ends. Its windows ignore the mouse and never take the focus.
"""

import os
import subprocess
import sys
import threading
import time

HOLD_S = 0.3  # keep the border up through a frame or two of missed contact, so it does not flicker
WIDTH = 8  # points on macOS, pixels on Windows
RED = (0.86, 0.16, 0.16)


class Border:
    """The border process, from the engine's side. It starts when first needed and stops when turned off."""

    def __init__(self, command: list[str], popen=subprocess.Popen, clock=time.monotonic):
        self._command = command
        self._popen = popen
        self._clock = clock
        self._process = None
        self._shown = False
        self._last_contact: float | None = None

    def update(self, enabled: bool, touching: bool) -> None:
        if not enabled:
            self.close()
            return
        now = self._clock()
        if touching:
            self._last_contact = now
        show = self._last_contact is not None and now - self._last_contact < HOLD_S
        if self._process is None or self._process.poll() is not None:
            self._process = self._popen(self._command, stdin=subprocess.PIPE)
            self._shown = False
        if show != self._shown:
            self._send("show" if show else "hide")
            self._shown = show

    def _send(self, command: str) -> None:
        try:
            self._process.stdin.write(f"{command}\n".encode())
            self._process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            self.close()

    def close(self) -> None:
        process, self._process = self._process, None
        self._shown = False
        self._last_contact = None
        if process is not None:
            try:
                process.stdin.close()
            except (BrokenPipeError, OSError, ValueError):
                pass


def read_commands(stream, handle) -> None:
    """Pass each command line to handle, then end the process once the app stops sending."""
    for line in stream:
        handle(line.decode(errors="ignore").strip())
    os._exit(0)  # see preview.end_viewer: a normal exit can hang on the blocked stdin reader


def run_border(stream=None) -> int:
    stream = stream or sys.stdin.buffer
    if sys.platform == "darwin":
        _run_mac(stream)
    elif sys.platform == "win32":
        _run_windows(stream)
    return 0


def _run_mac(stream) -> None:
    import AppKit
    import Quartz
    from PyObjCTools import AppHelper

    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)  # no Dock icon when run from source
    colour = Quartz.CGColorCreateGenericRGB(*RED, 1.0)
    windows: list = []
    frames: list = []

    def build() -> None:
        """One window per screen, rebuilt when screens are added, removed or rearranged."""
        screens = [screen.frame() for screen in AppKit.NSScreen.screens()]
        if screens == frames:
            return
        for window in windows:
            window.orderOut_(None)
        windows.clear()
        frames[:] = screens
        for frame in screens:
            window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, AppKit.NSWindowStyleMaskBorderless, AppKit.NSBackingStoreBuffered, False)
            window.setReleasedWhenClosed_(False)
            window.setOpaque_(False)
            window.setBackgroundColor_(AppKit.NSColor.clearColor())
            window.setHasShadow_(False)
            window.setIgnoresMouseEvents_(True)
            window.setLevel_(AppKit.NSScreenSaverWindowLevel)  # above the menu bar and full-screen apps
            window.setCollectionBehavior_(
                AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces | AppKit.NSWindowCollectionBehaviorStationary
                | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
                | AppKit.NSWindowCollectionBehaviorIgnoresCycle)
            view = window.contentView()
            view.setWantsLayer_(True)
            view.layer().setBorderWidth_(WIDTH)
            view.layer().setBorderColor_(colour)
            windows.append(window)

    def handle(command: str) -> None:
        if command == "show":
            build()
            for window in windows:
                window.orderFrontRegardless()  # shows it without making Hands Down the active app
        elif command == "hide":
            for window in windows:
                window.orderOut_(None)

    threading.Thread(target=read_commands, args=(stream, lambda c: AppHelper.callAfter(handle, c)),
                     daemon=True).start()
    AppHelper.runEventLoop()


def _windows_monitors() -> list[tuple[int, int, int, int]]:
    import ctypes
    from ctypes import wintypes

    monitors = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                       ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def collect(_monitor, _dc, rect, _data):
        r = rect.contents
        monitors.append((r.left, r.top, r.right, r.bottom))
        return True

    ctypes.windll.user32.EnumDisplayMonitors(None, None, callback_type(collect), 0)
    return monitors


def _run_windows(stream) -> None:
    import ctypes
    import queue
    import tkinter as tk

    user32 = ctypes.windll.user32
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # real pixels on every monitor
    except Exception:
        pass
    GWL_EXSTYLE, HWND_TOPMOST = -20, -1
    WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80000, 0x20, 0x80, 0x8000000
    SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10
    key = "#010203"  # drawn as see-through

    root = tk.Tk()
    root.withdraw()
    try:
        monitors = _windows_monitors()
    except Exception:
        monitors = []
    monitors = monitors or [(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())]
    windows = []
    for x0, y0, x1, y1 in monitors:
        width, height = x1 - x0, y1 - y0
        window = tk.Toplevel(root, bg=key)
        window.overrideredirect(True)
        window.geometry(f"{width}x{height}+{x0}+{y0}")
        window.attributes("-transparentcolor", key, "-topmost", True, "-alpha", 0.0)
        canvas = tk.Canvas(window, bg=key, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        half = WIDTH / 2
        canvas.create_rectangle(half, half, width - half, height - half, width=WIDTH,
                                outline="#%02x%02x%02x" % tuple(int(c * 255) for c in RED))
        window.update_idletasks()
        hwnd = user32.GetParent(window.winfo_id())
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                              style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        windows.append((window, hwnd))

    commands: queue.Queue = queue.Queue()

    def poll() -> None:
        while not commands.empty():
            command = commands.get()
            for window, hwnd in windows:
                if command == "show":
                    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
                    window.attributes("-alpha", 1.0)
                elif command == "hide":
                    window.attributes("-alpha", 0.0)
        root.after(30, poll)

    threading.Thread(target=read_commands, args=(stream, commands.put), daemon=True).start()
    poll()
    root.mainloop()
