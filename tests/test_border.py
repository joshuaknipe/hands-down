import io

from handsdown import border
from handsdown.border import HOLD_S, Border
from tests.helpers import FakeClock


class FakeStdin(io.BytesIO):
    def __init__(self, broken=False):
        super().__init__()
        self.broken = broken

    def write(self, data):
        if self.broken:
            raise BrokenPipeError
        return super().write(data)

    def close(self):
        self.closed_by_border = True


class FakeProcess:
    def __init__(self, broken=False):
        self.stdin = FakeStdin(broken)
        self.returncode = None

    def poll(self):
        return self.returncode


def make_border(broken=False):
    processes = []
    clock = FakeClock(100.0)

    def popen(command, stdin):
        processes.append(FakeProcess(broken))
        return processes[-1]

    return Border(["border"], popen=popen, clock=clock), processes, clock


def sent(process):
    return process.stdin.getvalue().decode().split()


def test_turned_off_it_never_starts():
    b, processes, _ = make_border()
    b.update(False, True)
    assert processes == []


def test_shows_while_touching_and_hides_after_a_short_hold():
    b, processes, clock = make_border()
    b.update(True, False)
    assert len(processes) == 1 and sent(processes[0]) == []  # started early, so the first touch shows at once
    b.update(True, True)
    b.update(True, True)
    assert sent(processes[0]) == ["show"]
    clock.now += HOLD_S / 2
    b.update(True, False)  # a missed frame keeps it up
    assert sent(processes[0]) == ["show"]
    clock.now += HOLD_S
    b.update(True, False)
    assert sent(processes[0]) == ["show", "hide"]


def test_turning_it_off_closes_the_process():
    b, processes, _ = make_border()
    b.update(True, True)
    b.update(False, True)
    assert processes[0].stdin.closed_by_border
    b.update(True, True)
    assert len(processes) == 2 and sent(processes[1]) == ["show"]


def test_a_border_that_went_away_is_restarted():
    b, processes, _ = make_border(broken=True)
    b.update(True, True)  # no exception
    processes[0].returncode = 1
    b.update(True, True)
    assert len(processes) == 2


def test_read_commands_passes_lines_then_exits(monkeypatch):
    seen, exits = [], []
    monkeypatch.setattr(border.os, "_exit", exits.append)
    border.read_commands(io.BytesIO(b"show\nhide\n"), seen.append)
    assert seen == ["show", "hide"] and exits == [0]


def test_the_border_does_not_load_the_vision_models_library():
    import subprocess
    import sys
    from pathlib import Path

    script = "import sys, handsdown.border, handsdown.commands; print('mediapipe' in sys.modules)"
    root = Path(__file__).resolve().parent.parent
    out = subprocess.run([sys.executable, "-c", script], cwd=root, capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == "False", out.stderr


def test_text_or_blur_can_run_without_a_border_and_update_while_shown():
    import json
    from dataclasses import replace
    from handsdown.settings import Settings

    b, processes, clock = make_border()
    settings = Settings(screen_text=True, custom_text="Breathe\nHands down")
    b.update(settings, True)
    lines = processes[0].stdin.getvalue().decode().splitlines()
    assert lines[-1] == "show"
    config = json.loads(lines[0].removeprefix("configure "))
    assert config["screen_border"] is False and config["custom_text"] == "Breathe\nHands down"
    b.update(replace(settings, screen_text=False, screen_blur=True, blur_level=30), True)
    lines = processes[0].stdin.getvalue().decode().splitlines()
    assert len(lines) == 3 and json.loads(lines[-1].removeprefix("configure "))["blur_level"] == 30
    clock.now += HOLD_S + 0.1
    b.update(settings, False)
    assert processes[0].stdin.getvalue().decode().splitlines()[-1] == "hide"
    b.update(Settings(), False)
    assert processes[0].stdin.closed_by_border


def test_blur_level_softens_edges_and_keeps_original_snapshot():
    from PIL import Image
    image = Image.new("RGB", (100, 40), "black")
    image.paste("white", (50, 0, 100, 40))
    light = border.blurred_image(image, 2)
    strong = border.blurred_image(image, 30)
    assert light.size == strong.size == image.size
    assert light.getpixel((35, 20))[0] < strong.getpixel((35, 20))[0]
    assert image.getpixel((35, 20)) == (0, 0, 0)


def test_snapshot_is_reused_for_strength_changes_and_released_on_hide():
    from PIL import Image
    captures = []

    def capture(bbox):
        captures.append(bbox)
        return Image.new("RGB", (20, 20), "white")

    snapshot = border.ScreenSnapshot(capture)
    assert snapshot.image((0, 0, 20, 20), (20, 20), 2).size == (20, 20)
    snapshot.image((0, 0, 20, 20), (20, 20), 10)
    assert len(captures) == 1
    snapshot.clear()
    snapshot.image((0, 0, 20, 20), (20, 20), 10)
    assert len(captures) == 2


def test_capture_failure_is_visible_and_retried_next_episode():
    def denied(bbox):
        raise OSError("permission denied")

    snapshot = border.ScreenSnapshot(denied)
    assert snapshot.image((0, 0, 20, 20), (20, 20), 10) is None
    assert "unavailable" in snapshot.error.lower()
    snapshot.clear()
    assert snapshot.error == ""


def test_effect_configuration_broken_pipe_recovers_next_update():
    from handsdown.settings import Settings
    b, processes, _ = make_border(broken=True)
    b.update(Settings(screen_text=True), True)
    b.update(Settings(screen_text=True), True)
    assert len(processes) == 2


def test_text_panel_locations_include_padding_and_keep_panel_on_screen():
    # Top-left coordinates shared by both renderers; macOS converts the final y.
    screen = (1000, 800)
    panel = (240, 80)
    assert border.panel_origin(screen, panel, "top-left") == (24, 24)
    assert border.panel_origin(screen, panel, "center") == (380, 360)
    assert border.panel_origin(screen, panel, "bottom-right") == (736, 696)
    assert border.panel_origin(screen, panel, "top-center") == (380, 24)
    assert border.panel_origin(screen, panel, "middle-right") == (736, 360)
    assert border.panel_origin((100, 80), (150, 100), "bottom-right") == (0, 0)
