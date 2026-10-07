"""Clip labels, metadata and where clips live on disk.

A clip is a video plus a JSON sidecar with the same stem, in clips/<label>/.
The sidecar is written last, so a clip without one is an interrupted recording.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

# Where the hand is, not what it is doing: nothing user-visible names the behaviour.
TRUE_POSITIVE_LABELS = ("hair_scalp", "hair_crown", "hair_side", "hair_long", "ear_tuck")
FALSE_POSITIVE_LABELS = ("chin_rest", "cheek_rest", "glasses", "drinking", "phone")
LABELS = TRUE_POSITIVE_LABELS + FALSE_POSITIVE_LABELS
SPLITS = ("dev", "holdout")
HOLDOUT_EVERY = 4  # every 4th clip of a label is kept back for evaluation only

# What to do for each label, shown in the recorder window.
LABEL_GUIDE = {
    "hair_scalp": "Fingers in the hair on top or at the front of the head",
    "hair_crown": "Fingers in the hair at the back or crown",
    "hair_side": "Fingers in the hair beside the face or at the temple",
    "hair_long": "Fingers in long hair below the jaw or over the shoulder",
    "ear_tuck": "Tucking hair behind an ear",
    "chin_rest": "Chin resting on the hand",
    "cheek_rest": "Cheek resting on the hand",
    "glasses": "Adjusting glasses",
    "drinking": "Drinking from a cup or bottle",
    "phone": "Phone held to the ear",
}


def target_clips(label: str) -> int:
    """Clips to record per label: 4 for hair labels (one is held out), 2 for the others."""
    return HOLDOUT_EVERY if label in TRUE_POSITIVE_LABELS else 2


@dataclass
class ClipMeta:
    label: str
    split: str
    recorded_at: str  # ISO 8601, local time
    backend: str
    width: int
    height: int
    timestamps_ms: list[int]  # one per written frame, from the start of the recording

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, text: str) -> "ClipMeta":
        meta = cls(**json.loads(text))
        if meta.label not in LABELS:
            raise ValueError(f"unknown label {meta.label!r}")
        if meta.split not in SPLITS:
            raise ValueError(f"unknown split {meta.split!r}")
        if not all(isinstance(t, int) for t in meta.timestamps_ms):
            raise ValueError("timestamps_ms must be whole milliseconds")
        return meta


@dataclass(frozen=True)
class Clip:
    video: Path
    meta: ClipMeta


def assign_split(existing_count: int) -> str:
    return "holdout" if existing_count % HOLDOUT_EVERY == HOLDOUT_EVERY - 1 else "dev"


def new_clip_paths(clips_dir: Path, label: str, now: datetime) -> tuple[Path, Path]:
    stem = now.strftime("%Y%m%d-%H%M%S-%f")
    folder = clips_dir / label
    return folder / f"{stem}.mp4", folder / f"{stem}.json"


def count_clips(clips_dir: Path, label: str) -> int:
    return len(list((clips_dir / label).glob("*.json")))


def save_meta(path: Path, meta: ClipMeta) -> None:
    path.write_text(meta.to_json(), encoding="utf-8")


def load_clips(clips_dir: Path, warn: Callable[[str], None] = print) -> list[Clip]:
    """Every complete clip, sorted by path. Broken clips are skipped with a warning."""
    clips = []
    if not clips_dir.is_dir():
        return clips
    for meta_path in sorted(clips_dir.glob("*/*.json")):
        video = meta_path.with_suffix(".mp4")
        if not video.is_file():
            warn(f"Skipping {meta_path.parent.name}/{meta_path.name}: its video is missing")
            continue
        try:
            meta = ClipMeta.from_json(meta_path.read_text(encoding="utf-8"))
        except (ValueError, TypeError) as exc:  # json.JSONDecodeError is a ValueError
            warn(f"Skipping {meta_path.parent.name}/{meta_path.name}: unreadable metadata ({exc})")
            continue
        clips.append(Clip(video, meta))
    return clips
