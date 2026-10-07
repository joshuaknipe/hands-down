"""Run the stage 1 detector and episode logic over recorded clips: which clips would alert?"""

from dataclasses import dataclass
from pathlib import Path

from feasibility.analyse import read_frames
from feasibility.clips import LABELS, TRUE_POSITIVE_LABELS, load_clips
from handsdown.episodes import EpisodeTracker, Timing
from handsdown.landmarks import Tracker
from handsdown.settings import Settings
from handsdown.zone import contact


@dataclass(frozen=True)
class ClipOutcome:
    label: str
    split: str
    video: str
    contact_rate: float
    alerted: bool
    latency_s: float | None  # clip start to first alert


def outcome_from(label: str, split: str, video: str, observations, settings: Settings) -> ClipOutcome:
    tracker = EpisodeTracker(Timing(settings.dwell_s, settings.grace_s, settings.release_s, 0.0))
    touching = 0
    alerted_at = None
    for o in observations:
        now = o.timestamp_ms / 1000
        hit = contact(o, settings.zone_margin)
        touching += hit
        for event in tracker.update(now, hit):
            if event.kind == "alert" and alerted_at is None:
                alerted_at = now
    start = observations[0].timestamp_ms / 1000 if observations else 0.0
    rate = touching / len(observations) if observations else 0.0
    latency = None if alerted_at is None else round(alerted_at - start, 2)
    return ClipOutcome(label, split, video, rate, alerted_at is not None, latency)


def summary_lines(outcomes: list[ClipOutcome]) -> list[str]:
    lines = []
    for label in LABELS:
        group = [o for o in outcomes if o.label == label]
        if not group:
            continue
        alerted = sum(o.alerted for o in group)
        contact_rate = sum(o.contact_rate for o in group) / len(group)
        latencies = [o.latency_s for o in group if o.latency_s is not None]
        latency = f"{sum(latencies) / len(latencies):.1f} s" if latencies else "-"
        lines.append(f"{label:<11} {alerted}/{len(group)} alerted   contact {contact_rate:>4.0%}   latency {latency}")
    hair = [o for o in outcomes if o.label in TRUE_POSITIVE_LABELS]
    other = [o for o in outcomes if o.label not in TRUE_POSITIVE_LABELS]
    lines.append("")
    lines.append(f"Hair positions: {sum(o.alerted for o in hair)}/{len(hair)} clips alerted (want all)")
    lines.append(f"Other positions: {sum(o.alerted for o in other)}/{len(other)} clips alerted (want none)")
    return lines


def run_evaluate(clips_dir: Path, settings: Settings) -> int:
    clips = load_clips(clips_dir)
    if not clips:
        print(f"No clips found in {clips_dir}. Record some first: python -m feasibility record")
        return 1
    outcomes = []
    for i, clip in enumerate(clips, 1):
        print(f"[{i}/{len(clips)}] {clip.meta.label}/{clip.video.name}")
        timestamps = clip.meta.timestamps_ms
        with Tracker() as tracker:
            observations = [tracker.process(frame, timestamps[n])
                            for n, frame in enumerate(read_frames(clip.video)) if n < len(timestamps)]
        outcomes.append(outcome_from(clip.meta.label, clip.meta.split, str(clip.video), observations, settings))
    print()
    for line in summary_lines(outcomes):
        print(line)
    return 0
