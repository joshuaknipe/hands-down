"""Optional screen border, reminder text and desktop blur, from alert until hands move away.

Like the camera view, it runs as its own process (python -m handsdown --border) so no window
toolkit shares a thread with the tray icon. The app writes "show" and "hide" lines to its stdin;
the border closes when stdin ends. Its windows ignore the mouse and never take the focus.
"""

import io
import json
import os
import subprocess
import sys
import threading
import time

from handsdown.settings import Settings, clamp

EFFECT_FIELDS = ("screen_border", "border_color", "border_width", "screen_text", "custom_text",
                 "screen_blur", "blur_level", "text_size", "text_color", "text_background",
                 "text_background_color", "text_padding_x", "text_padding_y", "text_position")

HOLD_S = 0.3  # keep the border up through a frame or two of missed contact, so it does not flicker


class Border:
    """The border process, from the engine's side. It starts when first needed and stops when turned off."""

    def __init__(self, command: list[str], popen=subprocess.Popen, clock=time.monotonic, preview: bool = False):
        self._preview = preview
        self._command = command
        self._popen = popen
        self._clock = clock
        self._process = None
        self._shown = False
        self._config = None
        self._last_contact: float | None = None

    def update(self, enabled: bool | Settings, touching: bool) -> None:
        settings = clamp(enabled) if isinstance(enabled, Settings) else None
        if settings is not None:
            enabled = settings.screen_border or settings.screen_text or settings.screen_blur
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
            self._config = None
        if settings is not None:
            config = {name: getattr(settings, name) for name in EFFECT_FIELDS}
            if self._preview:
                config["preview"] = True
            if config != self._config:
                self._send("configure " + json.dumps(config, ensure_ascii=True))
                if self._process is None:
                    return
                self._config = config
        if show != self._shown:
            self._send("show" if show else "hide")
            self._shown = show if self._process is not None else False

    def _send(self, command: str) -> None:
        try:
            self._process.stdin.write(f"{command}\n".encode())
            self._process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            self.close()

    def close(self) -> None:
        process, self._process = self._process, None
        self._shown = False
        self._config = None
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


def blurred_image(image, level: int):
    from PIL import ImageFilter

    return image.filter(ImageFilter.GaussianBlur(level))


def capture_screen(bbox):
    from PIL import ImageGrab

    if sys.platform == "darwin":
        import Quartz
        if not Quartz.CGPreflightScreenCaptureAccess():
            Quartz.CGRequestScreenCaptureAccess()
            raise OSError("Screen Recording permission is required")
    return ImageGrab.grab(bbox=bbox, all_screens=True)


class ScreenSnapshot:
    """Capture once per alert; strength changes always blur the original image."""

    def __init__(self, capture=capture_screen):
        self._capture = capture
        self.clear()

    def clear(self) -> None:
        self._source = None
        self.error = ""

    def image(self, bbox, size, level):
        from PIL import Image

        if self._source is None and not self.error:
            try:
                self._source = self._capture(bbox).convert("RGB").resize(size, Image.Resampling.LANCZOS)
            except Exception:
                self.error = "Screen blur unavailable. Check screen capture permissions."
        return blurred_image(self._source, level) if self._source is not None else None


def _configuration(command: str) -> Settings:
    data = json.loads(command.removeprefix("configure "))
    return clamp(Settings(**{name: data.get(name, getattr(Settings(), name)) for name in EFFECT_FIELDS}))


def panel_origin(screen: tuple, panel: tuple, position: str) -> tuple:
    """Place a text panel inside the display, with a 24-point/pixel edge margin."""
    width, height = screen
    pw, ph = panel
    vertical, horizontal = ("middle", "center") if position == "center" else position.split("-")
    x = 24 if horizontal == "left" else width - pw - 24 if horizontal == "right" else (width - pw) / 2
    y = 24 if vertical == "top" else height - ph - 24 if vertical == "bottom" else (height - ph) / 2
    return max(0, min(x, width - pw)), max(0, min(y, height - ph))


def _mac_color(color):
    import AppKit

    rgb = tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(*rgb, 1.0)


def _run_mac(stream) -> None:
    import AppKit
    import Quartz
    from PyObjCTools import AppHelper

    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    settings = Settings(screen_border=True)
    preview = False
    windows = []
    frames = []
    shown = False

    def build() -> None:
        screens = [screen.frame() for screen in AppKit.NSScreen.screens()]
        if screens == frames:
            return
        for window, *_ in windows:
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
            window.setLevel_(AppKit.NSScreenSaverWindowLevel)
            window.setCollectionBehavior_(
                AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces | AppKit.NSWindowCollectionBehaviorStationary
                | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
                | AppKit.NSWindowCollectionBehaviorIgnoresCycle)
            width, height = frame.size.width, frame.size.height
            view = window.contentView()
            background = AppKit.NSImageView.alloc().initWithFrame_(((0, 0), (width, height)))
            background.setImageScaling_(AppKit.NSImageScaleAxesIndependently)
            view.addSubview_(background)
            panel = AppKit.NSView.alloc().initWithFrame_(((0, 0), (0, 0)))
            panel.setWantsLayer_(True)
            view.addSubview_(panel)
            label = AppKit.NSTextField.alloc().initWithFrame_(((width * .1, height * .35), (width * .8, height * .3)))
            label.setEditable_(False)
            label.setSelectable_(False)
            label.setBordered_(False)
            label.setDrawsBackground_(False)
            label.setBackgroundColor_(AppKit.NSColor.colorWithCalibratedWhite_alpha_(0.08, 0.9))
            label.setTextColor_(AppKit.NSColor.whiteColor())
            label.setFont_(AppKit.NSFont.boldSystemFontOfSize_(32))
            label.setAlignment_(AppKit.NSTextAlignmentCenter)
            label.cell().setWraps_(True)
            view.addSubview_(label)
            view.setWantsLayer_(True)
            windows.append((window, background, label, ScreenSnapshot(), frame))

    def render() -> None:
        # Hide all surfaces before a newly enabled blur captures the desktop.
        for window, *_ in windows:
            window.orderOut_(None)
        main_height = AppKit.NSScreen.screens()[0].frame().size.height
        for window, background, label, snapshot, frame in windows:
            window.setLevel_(AppKit.NSNormalWindowLevel if preview else AppKit.NSScreenSaverWindowLevel)
            width, height = int(frame.size.width), int(frame.size.height)
            image = None
            if settings.screen_blur:
                x, y = int(frame.origin.x), int(main_height - frame.origin.y - frame.size.height)
                image = snapshot.image((x, y, x + width, y + height), (width, height), settings.blur_level)
            else:
                snapshot.clear()
            if image is not None:
                png = io.BytesIO()
                image.save(png, format="PNG")
                data = AppKit.NSData.dataWithBytes_length_(png.getvalue(), len(png.getvalue()))
                background.setImage_(AppKit.NSImage.alloc().initWithData_(data))
            else:
                background.setImage_(None)
            text = settings.custom_text if settings.screen_text else ""
            if settings.screen_blur and snapshot.error:
                text = (text + "\n" + snapshot.error).strip()
            label.setStringValue_(text)
            font_size = settings.text_size
            px = settings.text_padding_x if settings.text_background else 0
            py = settings.text_padding_y if settings.text_background else 0
            max_width, max_height = max(1, width - 48), max(1, height - 48)
            px, py = min(px, max_width / 4), min(py, max_height / 4)
            content_width = max_width - px * 2
            label.setTextColor_(_mac_color(settings.text_color))
            label.setFont_(AppKit.NSFont.boldSystemFontOfSize_(font_size))
            fitting = label.cell().cellSizeForBounds_(((0, 0), (content_width, max_height)))
            while fitting.height > max_height - py * 2 and font_size > 12:
                font_size -= 1
                label.setFont_(AppKit.NSFont.boldSystemFontOfSize_(font_size))
                fitting = label.cell().cellSizeForBounds_(((0, 0), (content_width, max_height)))
            text_width = min(content_width, fitting.width + 4)
            text_height = min(max_height - py * 2, fitting.height)
            pw, ph = text_width + px * 2, text_height + py * 2
            x, top = panel_origin((width, height), (pw, ph), settings.text_position)
            y = height - top - ph  # AppKit's origin is bottom-left
            panel = window.contentView().subviews()[1]
            panel.setFrame_(((x, y), (pw, ph)))
            panel.layer().setBackgroundColor_(_mac_color(settings.text_background_color).CGColor())
            panel.setHidden_(not (text and settings.text_background))
            label.setFrame_(((x + px, y + py), (text_width, text_height)))
            label.setHidden_(not bool(text))
            layer = window.contentView().layer()
            layer.setBorderWidth_(min(settings.border_width, width / 2, height / 2) if settings.screen_border else 0)
            rgb = tuple(int(settings.border_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
            layer.setBorderColor_(Quartz.CGColorCreateGenericRGB(*rgb, 1.0))
        for window, *_ in windows:
            window.orderFrontRegardless()

    def handle(command: str) -> None:
        nonlocal settings, shown, preview
        if command.startswith("configure "):
            settings = _configuration(command)
            preview = bool(json.loads(command.removeprefix("configure ")).get("preview", False))
            if shown:
                build()
                render()
        elif command == "show":
            build()
            render()
            shown = True
        elif command == "hide":
            shown = False
            for window, background, label, snapshot, _ in windows:
                window.orderOut_(None)
                background.setImage_(None)
                snapshot.clear()

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
    from PIL import ImageTk

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
    settings = Settings(screen_border=True)
    preview = False
    shown = False
    for x0, y0, x1, y1 in monitors:
        width, height = x1 - x0, y1 - y0
        window = tk.Toplevel(root, bg=key)
        window.overrideredirect(True)
        window.geometry(f"{width}x{height}+{x0}+{y0}")
        window.attributes("-transparentcolor", key, "-topmost", True, "-alpha", 0.0)
        canvas = tk.Canvas(window, bg=key, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        window.update_idletasks()
        hwnd = user32.GetParent(window.winfo_id())
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                              style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        windows.append((window, hwnd, canvas, ScreenSnapshot(), (x0, y0, x1, y1)))

    commands: queue.Queue = queue.Queue()

    def render() -> None:
        for window, *_ in windows:
            window.attributes("-alpha", 0.0)
        root.update_idletasks()
        for window, hwnd, canvas, snapshot, bbox in windows:
            x0, y0, x1, y1 = bbox
            width, height = x1 - x0, y1 - y0
            canvas.delete("all")
            canvas.image = None
            if settings.screen_blur:
                image = snapshot.image(bbox, (width, height), settings.blur_level)
                if image is not None:
                    canvas.image = ImageTk.PhotoImage(image, master=window)
                    canvas.create_image(0, 0, image=canvas.image, anchor="nw")
            else:
                snapshot.clear()
            if settings.screen_border:
                thickness = min(settings.border_width, width / 2, height / 2)
                half = thickness / 2
                # Avoid the transparency key if that exact color is selected.
                color = settings.border_color if settings.border_color != key else "#010204"
                canvas.create_rectangle(half, half, width - half, height - half,
                                        width=thickness, outline=color)
            text = settings.custom_text if settings.screen_text else ""
            if settings.screen_blur and snapshot.error:
                text = (text + "\n" + snapshot.error).strip()
            if text:
                px = settings.text_padding_x if settings.text_background else 0
                py = settings.text_padding_y if settings.text_background else 0
                max_width, max_height = max(1, width - 48), max(1, height - 48)
                px, py = min(px, max_width / 4), min(py, max_height / 4)
                # Tk negative font sizes are pixels, matching the monitor coordinates.
                color = settings.text_color if settings.text_color != key else "#010204"
                font_size = settings.text_size
                item = canvas.create_text(0, 0, text=text, fill=color, anchor="nw",
                                          font=("Segoe UI", -font_size, "bold"),
                                          width=int(max_width - px * 2), justify="center")
                left, top, right, bottom = canvas.bbox(item)
                while bottom - top > max_height - py * 2 and font_size > 12:
                    font_size -= 1
                    canvas.itemconfigure(item, font=("Segoe UI", -font_size, "bold"))
                    left, top, right, bottom = canvas.bbox(item)
                pw, ph = right - left + px * 2, bottom - top + py * 2
                x, y = panel_origin((width, height), (pw, ph), settings.text_position)
                canvas.move(item, x + px - left, y + py - top)
                if settings.text_background:
                    color = settings.text_background_color
                    color = color if color != key else "#010204"
                    panel = canvas.create_rectangle(x, y, x + pw, y + ph, fill=color, outline="")
                    canvas.tag_lower(panel, item)
        for window, hwnd, *_ in windows:
            window.attributes("-topmost", not preview)
            user32.SetWindowPos(hwnd, -2 if preview else HWND_TOPMOST, 0, 0, 0, 0,
                                SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
            window.attributes("-alpha", 1.0)

    def poll() -> None:
        nonlocal settings, shown, preview
        while not commands.empty():
            command = commands.get()
            if command.startswith("configure "):
                settings = _configuration(command)
                preview = bool(json.loads(command.removeprefix("configure ")).get("preview", False))
                if shown:
                    render()
            elif command == "show":
                render()
                shown = True
            elif command == "hide":
                shown = False
                for window, hwnd, canvas, snapshot, _ in windows:
                    window.attributes("-alpha", 0.0)
                    canvas.delete("all")
                    canvas.image = None
                    snapshot.clear()
        root.after(30, poll)

    threading.Thread(target=read_commands, args=(stream, commands.put), daemon=True).start()
    poll()
    root.mainloop()
