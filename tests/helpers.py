"""Fakes shared by the test suite."""


class FakeClock:
    """A clock that only moves when a test sets `now`."""

    def __init__(self, now: float = 0.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


class FakeCapture:
    """Stands in for cv2.VideoCapture: replays a list of (ok, frame) reads."""

    def __init__(self, opened: bool = True, reads=()):
        self.opened = opened
        self.reads = list(reads)
        self.released = False
        self.props = {}

    def isOpened(self) -> bool:
        return self.opened

    def set(self, prop, value) -> bool:
        self.props[prop] = value
        return True

    def read(self):
        if not self.reads:
            return False, None
        return self.reads.pop(0)

    def release(self) -> None:
        self.released = True


class ScriptedAsk:
    """Stands in for input(): returns scripted answers in order and records each prompt."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.answers:
            raise AssertionError(f"Unexpected prompt: {prompt}")
        return self.answers.pop(0)
