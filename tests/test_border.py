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
