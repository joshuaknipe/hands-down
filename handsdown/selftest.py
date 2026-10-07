"""Check that a build can run: models load, the tracker works, assets exist, folders are writable.

CI runs this inside the frozen Windows build, where missing data files are the likeliest bug.
"""

import sys

import numpy as np

from handsdown.chime import sound_file
from handsdown.paths import log_dir, resource_path, settings_path
from handsdown.settings import SOUNDS, VOLUMES

ASSETS = (
    "models/hand_landmarker.task",
    "models/face_landmarker.task",
    *(sound_file(sound, volume) for sound in SOUNDS for volume in VOLUMES),
)


def run_self_test() -> int:
    try:
        for asset in ASSETS:
            if not resource_path(asset).is_file():
                raise FileNotFoundError(f"missing {asset}")
        from handsdown.landmarks import Tracker

        with Tracker() as tracker:
            tracker.process(np.zeros((480, 640, 3), np.uint8), 0)
        for folder in (settings_path().parent, log_dir()):
            folder.mkdir(parents=True, exist_ok=True)
            probe = folder / ".selftest"
            probe.write_text("ok")
            probe.unlink()
    except Exception as exc:
        if sys.stderr:
            print(f"Self-test failed: {exc}", file=sys.stderr)
        return 1
    return 0
