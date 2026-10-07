"""Run the tracker over saved clips and report how often her hand is found."""

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

from feasibility.clips import LABELS, TRUE_POSITIVE_LABELS, Clip, load_clips
from feasibility.report import write_report
from feasibility.stats import MIN_CLIP_HAND_RATE, ClipStats, clip_stats, evaluate
from handsdown.landmarks import Tracker


def read_frames(video: Path) -> Iterator[np.ndarray]:
    capture = cv2.VideoCapture(str(video))
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                return
            yield frame
    finally:
        capture.release()


def analyse_clip(clip: Clip, tracker_factory=Tracker, frame_reader=read_frames) -> ClipStats:
    """Track every frame using the recorded timestamps. Uses the shorter of video and timestamps."""
    timestamps = clip.meta.timestamps_ms
    observations = []
    video_frames = 0
    with tracker_factory() as tracker:  # a fresh tracker per clip: VIDEO mode keeps state between frames
        for frame in frame_reader(clip.video):
            if video_frames < len(timestamps):
                observations.append(tracker.process(frame, timestamps[video_frames]))
            video_frames += 1
    return clip_stats(clip.meta.label, clip.meta.split, str(clip.video), observations,
                      frame_count_mismatch=video_frames - len(timestamps))


def format_table(stats: list[ClipStats]) -> list[str]:
    rows = [f"{'label':<11} {'split':<8} {'frames':>6} {'secs':>5} {'hand':>5} {'face':>5} {'gap s':>5}  clip"]
    for s in sorted(stats, key=lambda s: (LABELS.index(s.label), s.video)):
        row = (f"{s.label:<11} {s.split:<8} {s.frames:>6} {s.duration_s:>5.1f} {s.hand_rate:>5.0%} "
               f"{s.face_rate:>5.0%} {s.longest_hand_gap_s:>5.1f}  {Path(s.video).name}")
        if s.label in TRUE_POSITIVE_LABELS and not s.passed:
            row += f"  below {MIN_CLIP_HAND_RATE:.0%}"
        if s.frame_count_mismatch:
            row += f"  frame count mismatch {s.frame_count_mismatch:+d}"
        rows.append(row)
    return rows


def run_analyse(clips_dir: Path, reports_dir: Path, now=datetime.now) -> int:
    clips = load_clips(clips_dir)
    if not clips:
        print(f"No clips found in {clips_dir}. Record some first: python -m feasibility record --label hair_scalp")
        return 1
    stats = []
    for i, clip in enumerate(clips, 1):
        print(f"[{i}/{len(clips)}] {clip.meta.label}/{clip.video.name}")
        stats.append(analyse_clip(clip))
    print()
    for line in format_table(stats):
        print(line)
    verdict = evaluate(stats)
    print()
    for line in verdict.lines():
        print(line)
    payload = {"clips": [asdict(s) | {"passed": s.passed} for s in stats], "verdict": asdict(verdict)}
    print(f"Report written to {write_report(reports_dir, 'analyse', payload, now())}")
    return 0
