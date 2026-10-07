"""Write milestone 1 results as JSON. Reports hold numbers and labels only, never images."""

import json
from datetime import datetime
from pathlib import Path


def write_report(reports_dir: Path, kind: str, payload: dict, now: datetime) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{kind}-{now.strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
