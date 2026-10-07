"""Append-only log of what Hands Down saw and did: one JSON object per line, never images."""

import json
import threading
from datetime import datetime
from pathlib import Path


class EventLog:
    def __init__(self, folder: Path, now=datetime.now):
        self._folder = folder
        self._now = now
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._folder / "events.jsonl"

    def write(self, kind: str, **fields) -> None:
        record = {"time": self._now().isoformat(timespec="seconds"), "kind": kind, **fields}
        line = json.dumps(record) + "\n"
        with self._lock:
            self._folder.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line)

    def read(self) -> list[dict]:
        if not self.path.is_file():
            return []
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                records.append(json.loads(line))
            except ValueError:
                continue  # a line cut short by a crash or power loss
        return records
