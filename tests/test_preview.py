import io

import numpy as np

from handsdown import preview
from handsdown.landmarks import Observation
from handsdown.settings import Settings

FACE = (0.4, 0.3, 0.6, 0.6)
TEMPLE = tuple((0.33, 0.4) for _ in range(21))
FRAME = np.zeros((480, 640, 3), np.uint8)


def test_frames_round_trip_through_a_pipe():
    stream = io.BytesIO()
    preview.write_frame(stream, b"first")
    preview.write_frame(stream, b"second")
    stream.seek(0)
    assert preview.read_frame(stream) == b"first"
    assert preview.read_frame(stream) == b"second"
    assert preview.read_frame(stream) is None


def test_a_cut_off_frame_reads_as_the_end():
    stream = io.BytesIO()
    preview.write_frame(stream, b"complete frame")
    stream = io.BytesIO(stream.getvalue()[:-3])
    assert preview.read_frame(stream) is None


def test_annotate_draws_zone_and_hand_on_a_mirrored_copy():
    out = preview.annotate(FRAME, Observation(0, (TEMPLE,), True, FACE), Settings(), contact=True)
    assert FRAME.max() == 0  # the engine's frame is untouched
    assert out.shape == FRAME.shape
    zone_left = 639 - int(0.3 * 640)  # the zone's left edge, mirrored
    assert out[240, zone_left - 2:zone_left + 3].max() > 0
    hand_x, hand_y = 639 - int(0.33 * 640), int(0.4 * 480)
    assert out[hand_y - 2:hand_y + 3, hand_x - 2:hand_x + 3].max() > 0


def test_annotate_without_a_face_still_shows_the_picture():
    out = preview.annotate(FRAME, Observation(0, (), False, None), Settings(), contact=False)
    assert out.shape == FRAME.shape


def test_encode_makes_a_jpeg_in_memory():
    assert preview.encode(FRAME)[:2] == b"\xff\xd8"


class FakeStdin(io.BytesIO):
    def __init__(self, broken=False):
        super().__init__()
        self.broken = broken

    def write(self, data):
        if self.broken:
            raise BrokenPipeError
        return super().write(data)

    def close(self):
        self.closed_by_view = True


class FakeProcess:
    def __init__(self, broken=False):
        self.stdin = FakeStdin(broken)
        self.returncode = None

    def poll(self):
        return self.returncode


def make_view(broken=False):
    processes = []

    def popen(command, stdin):
        processes.append(FakeProcess(broken))
        return processes[-1]

    return preview.CameraView(["viewer"], popen=popen), processes


def test_camera_view_sends_frames_while_open():
    view, processes = make_view()
    assert not view.is_open
    view.send(b"ignored while closed")
    view.open()
    view.open()  # already open: no second window
    assert view.is_open and len(processes) == 1
    view.send(b"jpeg")
    assert processes[0].stdin.getvalue() == b"\x00\x00\x00\x04jpeg"


def test_camera_view_closes_when_its_window_is_gone():
    view, processes = make_view(broken=True)
    view.open()
    view.send(b"jpeg")  # the viewer went away: no exception
    assert not view.is_open


def test_camera_view_reopens_after_the_window_was_closed():
    view, processes = make_view()
    view.open()
    processes[0].returncode = 0
    assert not view.is_open
    view.open()
    assert len(processes) == 2


def test_annotate_with_the_chin_cut_out_off():
    out = preview.annotate(FRAME, Observation(0, (), True, FACE), Settings(chin_cutout=0.0), contact=False)
    assert out.shape == FRAME.shape


def test_settings_key_opens_settings_and_escape_closes():
    opened = []
    assert preview.handle_key(ord("s"), lambda: opened.append(1)) is True
    assert preview.handle_key(ord("S"), lambda: opened.append(1)) is True
    assert opened == [1, 1]
    assert preview.handle_key(27, lambda: None) is False
    assert preview.handle_key(ord("q"), lambda: None) is False
    assert preview.handle_key(-1, lambda: None) is True  # no key pressed


def test_settings_button_sits_in_the_top_right_corner():
    x0, y0, x1, y1 = preview.settings_button(640)
    assert x1 <= 640 and x0 > 640 / 2 and y0 >= 0 and y1 < 80
    assert preview.button_hit(preview.settings_button(640), (x0 + x1) // 2, (y0 + y1) // 2)
    assert not preview.button_hit(preview.settings_button(640), 10, 10)


def test_with_controls_draws_the_button_without_changing_the_frame():
    out = preview.with_controls(FRAME)
    assert FRAME.max() == 0 and out.max() > 0
    x0, y0, x1, y1 = preview.settings_button(640)
    assert out[y0:y1, x0:x1].max() > 0


def test_viewer_exits_cleanly_while_its_reader_waits_on_stdin():
    """Closing the camera window used to abort the viewer: a daemon thread held stdin's lock at shutdown."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    script = (
        "import sys, threading, time\n"
        "from handsdown import preview\n"
        "threading.Thread(target=lambda: preview.read_frame(sys.stdin.buffer), daemon=True).start()\n"
        "time.sleep(0.3)\n"
        "preview.end_viewer(0)\n"
    )
    root = Path(__file__).resolve().parent.parent
    env = os.environ | {"PYTHONPATH": str(root)}
    process = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    try:
        process.wait(timeout=20)  # stdin stays open, as it does while the app is running
        err = process.stderr.read()
    finally:
        process.kill()
        process.stdin.close()
    assert process.returncode == 0, err.decode()
    assert b"Fatal Python error" not in err


def test_the_viewer_does_not_load_the_vision_models_library():
    """The camera view only shows pictures; loading MediaPipe made it take seconds to open."""
    import subprocess
    import sys
    from pathlib import Path

    script = "import sys, handsdown.preview, handsdown.commands; print('mediapipe' in sys.modules)"
    root = Path(__file__).resolve().parent.parent
    out = subprocess.run([sys.executable, "-c", script], cwd=root, capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == "False", out.stderr
