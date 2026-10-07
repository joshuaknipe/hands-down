"""The optional camera view: the live picture with the head zone and hand points drawn on it.

The engine owns the camera. While the view is open, it sends each annotated frame as an
in-memory JPEG through a pipe to a separate viewer process (python -m handsdown --camera-view),
which shows it in an OpenCV window. Nothing is ever written to disk.
"""

import struct
import subprocess
import sys
import threading
from typing import Callable

import cv2
import numpy as np

from handsdown.landmarks import Box, Observation
from handsdown.settings import Settings
from handsdown.zone import head_zone

WINDOW_TITLE = "Hands Down camera"
ZONE_COLOUR = (160, 166, 88)  # BGR teal, matching the tray ring
EXCLUDED_COLOUR = (150, 150, 150)
FACE_COLOUR = (220, 220, 220)
HAND_COLOUR = (92, 176, 214)
CONTACT_COLOUR = (92, 110, 205)
TEXT_COLOUR = (240, 240, 240)


def write_frame(stream, data: bytes) -> None:
    stream.write(struct.pack(">I", len(data)) + data)
    stream.flush()


def read_frame(stream) -> bytes | None:
    """The next frame, or None at the end of the stream (including a cut-off frame)."""
    header = stream.read(4)
    if len(header) < 4:
        return None
    (length,) = struct.unpack(">I", header)
    data = stream.read(length)
    return data if len(data) == length else None


def _rect(image: np.ndarray, box: Box, colour, thickness: int = 2) -> None:
    h, w = image.shape[:2]
    x0, y0, x1, y1 = box
    cv2.rectangle(image, (int(x0 * w), int(y0 * h)), (int(x1 * w), int(y1 * h)), colour, thickness)


def annotate(frame: np.ndarray, observation: Observation, settings: Settings, contact: bool) -> np.ndarray:
    """A mirrored copy of the frame with the head zone, face box and hand points drawn on it."""
    image = frame.copy()
    h, w = image.shape[:2]
    if observation.face_box is not None:
        zone = head_zone(observation.face_box, settings.zone_margin, settings.zone_above, settings.zone_below,
                         settings.chin_cutout)
        _rect(image, zone.outer, CONTACT_COLOUR if contact else ZONE_COLOUR)
        if zone.excluded is not None:
            _rect(image, zone.excluded, EXCLUDED_COLOUR, 1)
        _rect(image, observation.face_box, FACE_COLOUR, 1)
    for hand in observation.hands:
        for x, y in hand:
            cv2.circle(image, (int(x * w), int(y * h)), 3, HAND_COLOUR, -1)
    image = cv2.flip(image, 1)  # mirrored, like looking in a mirror
    if observation.face_box is None:
        label, colour = "No face found", EXCLUDED_COLOUR
    elif contact:
        label, colour = "In zone", CONTACT_COLOUR
    else:
        label, colour = "Clear", ZONE_COLOUR
    cv2.putText(image, label, (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.9, colour, 2, cv2.LINE_AA)
    return image


def encode(image: np.ndarray) -> bytes:
    ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return data.tobytes() if ok else b""


class CameraView:
    """The viewer process, from the engine's side. Sending to a closed view does nothing."""

    def __init__(self, command: list[str], popen=subprocess.Popen):
        self._command = command
        self._popen = popen
        self._process = None
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def open(self) -> None:
        if self.is_open:
            return
        with self._lock:
            self._process = self._popen(self._command, stdin=subprocess.PIPE)

    def send(self, jpeg: bytes) -> None:
        with self._lock:
            process = self._process
        if process is None or process.poll() is not None:
            return
        try:
            write_frame(process.stdin, jpeg)
        except (BrokenPipeError, OSError, ValueError):
            self.close()

    def close(self) -> None:
        with self._lock:
            process, self._process = self._process, None
        if process is not None:
            try:
                process.stdin.close()
            except (BrokenPipeError, OSError, ValueError):
                pass


BUTTON_COLOUR = (60, 60, 60)


def settings_button(width: int) -> Box:
    """Pixel box of the Settings button drawn in the viewer's top-right corner."""
    return (width - 132, 12, width - 12, 48)


def button_hit(button, x: int, y: int) -> bool:
    x0, y0, x1, y1 = button
    return x0 <= x <= x1 and y0 <= y <= y1


def with_controls(image: np.ndarray) -> np.ndarray:
    """A copy with the Settings button and the key hints drawn on it."""
    out = image.copy()
    h, w = out.shape[:2]
    x0, y0, x1, y1 = settings_button(w)
    cv2.rectangle(out, (x0, y0), (x1, y1), BUTTON_COLOUR, -1)
    cv2.putText(out, "Settings", (x0 + 14, y1 - 11), cv2.FONT_HERSHEY_SIMPLEX, 0.7, TEXT_COLOUR, 2, cv2.LINE_AA)
    cv2.putText(out, "S settings   Esc close", (12, h - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.55, TEXT_COLOUR, 1,
                cv2.LINE_AA)
    return out


def handle_key(key: int, open_settings: Callable[[], None]) -> bool:
    """Act on a key from cv2.waitKey; returns False when the viewer should close."""
    if key in (27, ord("q"), ord("Q")):
        return False
    if key in (ord("s"), ord("S")):
        open_settings()
    return True


def run_viewer(stream=None, open_settings: Callable[[], None] = lambda: None) -> int:
    """The viewer process: show frames from stdin until the window is closed or the app stops sending."""
    stream = stream or sys.stdin.buffer
    latest: list[bytes | None] = [None]
    ended = threading.Event()

    def reader() -> None:
        while (data := read_frame(stream)) is not None:
            latest[0] = data
        ended.set()

    threading.Thread(target=reader, daemon=True).start()
    shown = False
    width = [0]

    def on_mouse(event, x, y, _flags, _param) -> None:
        if event == cv2.EVENT_LBUTTONUP and button_hit(settings_button(width[0]), x, y):
            open_settings()
    while not ended.is_set():
        data, latest[0] = latest[0], None
        if data:
            image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if image is not None:
                width[0] = image.shape[1]
                cv2.imshow(WINDOW_TITLE, with_controls(image))
                if not shown:
                    cv2.setMouseCallback(WINDOW_TITLE, on_mouse)
                shown = True
        if not handle_key(cv2.waitKey(30), open_settings):
            break
        if shown and cv2.getWindowProperty(WINDOW_TITLE, cv2.WND_PROP_VISIBLE) < 1:
            break  # closed with the window's close button
    cv2.destroyAllWindows()
    return 0
