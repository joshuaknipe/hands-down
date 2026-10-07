"""Fakes shared by the test suite."""


class FakeClock:
    """A clock that only moves when a test sets `now`."""

    def __init__(self, now: float = 0.0):
        self.now = now

    def __call__(self) -> float:
        return self.now
