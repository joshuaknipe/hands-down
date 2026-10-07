import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from feasibility.analyse import analyse_clip, format_table, read_frames, run_analyse
from feasibility.clips import Clip, ClipMeta, save_meta
from feasibility.report import write_report
from feasibility.stats import ClipStats
from handsdown.landmarks import Observation


class FakeTracker:
    """Reports a hand on frames whose first pixel is bright."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def process(self, frame, timestamp_ms):
        hand = (((0.5, 0.5),),) if frame[0, 0, 0] > 100 else ()
        return Observation(timestamp_ms, hand, True)


def frames(*values):
    return [np.full((4, 4, 3), v, np.uint8) for v in values]


def clip_with(timestamps, label="hair_scalp"):
    return Clip(Path(f"{label}.mp4"), ClipMeta(label, "dev", "2026-10-07T12:00:00", "dshow", 4, 4, timestamps))


def test_analyse_clip_uses_recorded_timestamps():
    stats = analyse_clip(clip_with([0, 100, 200, 300]), tracker_factory=FakeTracker,
                         frame_reader=lambda path: iter(frames(200, 200, 0, 200)))
    assert (stats.frames, stats.hand_rate, stats.duration_s) == (4, 0.75, 0.3)
    assert stats.longest_hand_gap_s == 0.1
    assert stats.frame_count_mismatch == 0


def test_analyse_clip_reports_extra_and_missing_frames():
    extra = analyse_clip(clip_with([0, 100]), tracker_factory=FakeTracker,
                         frame_reader=lambda path: iter(frames(200, 200, 200)))
    assert (extra.frames, extra.frame_count_mismatch) == (2, 1)
    missing = analyse_clip(clip_with([0, 100, 200]), tracker_factory=FakeTracker,
                           frame_reader=lambda path: iter(frames(200)))
    assert (missing.frames, missing.frame_count_mismatch) == (1, -2)


def test_read_frames_reads_an_mp4(tmp_path):
    path = tmp_path / "c.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (64, 48))
    for _ in range(20):
        writer.write(np.full((48, 64, 3), 128, np.uint8))
    writer.release()
    assert len(list(read_frames(path))) == 20


def test_format_table_flags_failing_true_positives_and_mismatches():
    rows = format_table([
        ClipStats("hair_scalp", "dev", "/x/a.mp4", 30, 1.0, 0.5, 1.0, 0.4, 0),
        ClipStats("chin_rest", "holdout", "/x/b.mp4", 30, 1.0, 0.1, 1.0, 0.9, 2),
    ])
    assert "below 80%" in rows[1] and "a.mp4" in rows[1]
    assert "below" not in rows[2]
    assert "frame count mismatch +2" in rows[2]


def test_write_report(tmp_path):
    path = write_report(tmp_path / "reports", "analyse", {"a": 1}, datetime(2026, 10, 7, 14, 30, 5))
    assert path.name == "analyse-20261007-143005.json"
    assert json.loads(path.read_text()) == {"a": 1}


def test_run_analyse_with_no_clips_returns_error(tmp_path, capsys):
    assert run_analyse(tmp_path / "clips", tmp_path / "reports") == 1
    assert "No clips found" in capsys.readouterr().out


def test_run_analyse_end_to_end_on_a_real_clip(tmp_path, capsys):
    folder = tmp_path / "clips" / "hair_scalp"
    folder.mkdir(parents=True)
    writer = cv2.VideoWriter(str(folder / "c.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 30, (64, 48))
    for _ in range(20):
        writer.write(np.zeros((48, 64, 3), np.uint8))
    writer.release()
    save_meta(folder / "c.json", ClipMeta("hair_scalp", "dev", "2026-10-07T12:00:00", "dshow", 64, 48,
                                          [i * 33 for i in range(20)]))
    assert run_analyse(tmp_path / "clips", tmp_path / "reports", now=lambda: datetime(2026, 10, 7)) == 0
    report = json.loads((tmp_path / "reports" / "analyse-20261007-000000.json").read_text())
    assert report["verdict"]["status"] == "INCOMPLETE"
    assert report["clips"][0]["frames"] == 20
    assert "Verdict: INCOMPLETE" in capsys.readouterr().out
