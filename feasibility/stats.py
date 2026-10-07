"""Per-clip hand-visibility statistics and milestone 1's go / no-go verdict."""

from dataclasses import dataclass, field
from typing import Sequence

from feasibility.clips import TRUE_POSITIVE_LABELS
from handsdown.landmarks import Observation

MIN_CLIP_HAND_RATE = 0.8  # a clip passes when a hand is found in at least this share of frames
MIN_PASSING_SHARE = 0.8  # GO needs at least this share of true-positive clips to pass
MIN_CLIPS_PER_LABEL = 3  # each true-positive label needs this many clips before a verdict
WEAK_LABEL_PASS_SHARE = 0.5  # a label with fewer passing clips than this is flagged


@dataclass(frozen=True)
class ClipStats:
    label: str
    split: str
    video: str
    frames: int
    duration_s: float
    hand_rate: float
    face_rate: float
    longest_hand_gap_s: float
    frame_count_mismatch: int  # video frames minus recorded timestamps; 0 when they agree

    @property
    def passed(self) -> bool:
        return self.frames > 0 and self.hand_rate >= MIN_CLIP_HAND_RATE


def longest_gap_s(observations: Sequence[Observation]) -> float:
    """Longest stretch without a hand, from its first frame to the next frame with a hand (or the clip's end)."""
    longest = 0
    run_start = None
    for o in observations:
        if o.hand_found:
            if run_start is not None:
                longest = max(longest, o.timestamp_ms - run_start)
                run_start = None
        elif run_start is None:
            run_start = o.timestamp_ms
    if run_start is not None:
        longest = max(longest, observations[-1].timestamp_ms - run_start)
    return longest / 1000


def clip_stats(label: str, split: str, video: str, observations: Sequence[Observation],
               frame_count_mismatch: int = 0) -> ClipStats:
    frames = len(observations)
    if frames == 0:
        return ClipStats(label, split, video, 0, 0.0, 0.0, 0.0, 0.0, frame_count_mismatch)
    return ClipStats(
        label, split, video, frames,
        duration_s=(observations[-1].timestamp_ms - observations[0].timestamp_ms) / 1000,
        hand_rate=sum(o.hand_found for o in observations) / frames,
        face_rate=sum(o.face_found for o in observations) / frames,
        longest_hand_gap_s=longest_gap_s(observations),
        frame_count_mismatch=frame_count_mismatch,
    )


@dataclass
class Verdict:
    status: str  # "GO", "NO-GO" or "INCOMPLETE"
    passing_share: float
    missing_labels: list[str] = field(default_factory=list)
    weak_labels: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        out = [
            f"Verdict: {self.status}. {self.passing_share:.0%} of true-positive clips had a hand in at least "
            f"{MIN_CLIP_HAND_RATE:.0%} of frames; GO needs {MIN_PASSING_SHARE:.0%}."
        ]
        if self.missing_labels:
            out.append(f"Record at least {MIN_CLIPS_PER_LABEL} clips each for: {', '.join(self.missing_labels)}")
        if self.weak_labels:
            out.append(f"Weak spots (under {WEAK_LABEL_PASS_SHARE:.0%} of clips pass): {', '.join(self.weak_labels)}")
        return out


def evaluate(stats: list[ClipStats]) -> Verdict:
    true_positives = [s for s in stats if s.label in TRUE_POSITIVE_LABELS]
    missing, weak = [], []
    for label in TRUE_POSITIVE_LABELS:
        clips = [s for s in true_positives if s.label == label]
        if len(clips) < MIN_CLIPS_PER_LABEL:
            missing.append(label)
        if clips and sum(s.passed for s in clips) / len(clips) < WEAK_LABEL_PASS_SHARE:
            weak.append(label)
    share = sum(s.passed for s in true_positives) / len(true_positives) if true_positives else 0.0
    if missing:
        status = "INCOMPLETE"
    elif share >= MIN_PASSING_SHARE:
        status = "GO"
    else:
        status = "NO-GO"
    return Verdict(status, share, missing, weak)
