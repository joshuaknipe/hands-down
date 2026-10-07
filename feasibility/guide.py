"""Walk through every label in order, showing what to record and how many clips remain."""

from pathlib import Path
from typing import Sequence

from feasibility.clips import LABEL_GUIDE, LABELS, count_clips, target_clips

KEYS_IDLE = "Hand in position, then SPACE with your other hand   N next  P prev  Q quit"
KEYS_RECORDING = "Recording - keep your hand there and moving. SPACE to stop"


class GuidedSession:
    def __init__(self, clips_dir: Path, labels: Sequence[str] = LABELS):
        self._clips_dir = clips_dir
        self._labels = tuple(labels)
        self._index = 0
        if not self.complete(self.label):
            return
        self.advance_to_incomplete()

    @property
    def label(self) -> str:
        return self._labels[self._index]

    def saved(self, label: str) -> int:
        return count_clips(self._clips_dir, label)

    def complete(self, label: str) -> bool:
        return self.saved(label) >= target_clips(label)

    @property
    def finished(self) -> bool:
        return all(self.complete(label) for label in self._labels)

    def advance(self) -> None:
        self._index = min(self._index + 1, len(self._labels) - 1)

    def back(self) -> None:
        self._index = max(self._index - 1, 0)

    def advance_to_incomplete(self) -> None:
        """Move to the next label that still needs clips, wrapping round to skipped ones."""
        n = len(self._labels)
        for step in range(1, n + 1):
            candidate = (self._index + step) % n
            if not self.complete(self._labels[candidate]):
                self._index = candidate
                return

    def lines(self, recording: bool) -> list[str]:
        label = self.label
        saved, target = self.saved(label), target_clips(label)
        position = f"{self._index + 1}/{len(self._labels)}  {label}  -  "
        progress = f"clip {saved + 1} of {target}" if saved < target else f"done ({saved} saved)"
        lines = [position + progress, LABEL_GUIDE[label], KEYS_RECORDING if recording else KEYS_IDLE]
        if self.finished and not recording:
            lines.append("All clips recorded. Press Q to finish.")
        return lines
