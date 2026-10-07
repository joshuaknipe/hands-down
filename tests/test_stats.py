import pytest

from feasibility.clips import TRUE_POSITIVE_LABELS
from feasibility.stats import ClipStats, clip_stats, evaluate, longest_gap_s
from handsdown.landmarks import Observation


def obs(ts, hand, face=True):
    return Observation(ts, (((0.5, 0.5),),) if hand else (), face)


def sequence(flags, step=100):
    return [obs(i * step, flag) for i, flag in enumerate(flags)]


def test_longest_gap_runs_to_the_next_hand():
    assert longest_gap_s(sequence([True, True, False, False, False, True])) == pytest.approx(0.3)


def test_longest_gap_counts_a_trailing_run():
    assert longest_gap_s(sequence([True, False, False])) == pytest.approx(0.1)


def test_longest_gap_with_hand_throughout_is_zero():
    assert longest_gap_s(sequence([True] * 4)) == 0.0
    assert longest_gap_s([]) == 0.0


def test_clip_stats_rates_and_duration():
    observations = sequence([True, True, True, False])
    observations[3] = obs(300, False, face=False)
    s = clip_stats("hair_scalp", "dev", "a.mp4", observations, frame_count_mismatch=1)
    assert (s.frames, s.duration_s, s.hand_rate, s.face_rate) == (4, 0.3, 0.75, 0.75)
    assert s.frame_count_mismatch == 1
    assert not s.passed


def test_clip_stats_for_an_empty_clip():
    s = clip_stats("hair_scalp", "dev", "a.mp4", [])
    assert (s.frames, s.duration_s, s.hand_rate, s.face_rate, s.passed) == (0, 0.0, 0.0, 0.0, False)


def stat(label, hand_rate):
    return ClipStats(label, "dev", f"{label}.mp4", 30, 1.0, hand_rate, 1.0, 0.0, 0)


def full_set(failing=None):
    """Three clips per true-positive label, all passing except the (label, count) given."""
    stats = []
    for label in TRUE_POSITIVE_LABELS:
        fails = failing.get(label, 0) if failing else 0
        stats += [stat(label, 0.5 if i < fails else 0.95) for i in range(3)]
    return stats


def test_all_clips_passing_is_go():
    verdict = evaluate(full_set())
    assert (verdict.status, verdict.passing_share, verdict.weak_labels) == ("GO", 1.0, [])


def test_too_few_clips_for_a_label_is_incomplete():
    stats = [s for s in full_set() if s.label != "hair_crown"] + [stat("hair_crown", 0.95)] * 2
    verdict = evaluate(stats)
    assert verdict.status == "INCOMPLETE" and verdict.missing_labels == ["hair_crown"]


def test_no_clips_is_incomplete():
    verdict = evaluate([])
    assert verdict.status == "INCOMPLETE" and verdict.missing_labels == list(TRUE_POSITIVE_LABELS)


def test_too_many_failing_clips_is_no_go():
    verdict = evaluate(full_set({"hair_crown": 2, "hair_long": 2}))  # 11 of 15 pass
    assert verdict.status == "NO-GO"
    assert verdict.passing_share == pytest.approx(11 / 15)


def test_weak_label_is_reported_without_blocking_go():
    verdict = evaluate(full_set({"hair_crown": 2}))  # 13 of 15 pass
    assert verdict.status == "GO" and verdict.weak_labels == ["hair_crown"]


def test_false_positive_clips_do_not_affect_the_verdict():
    verdict = evaluate(full_set() + [stat("chin_rest", 0.0)] * 5)
    assert verdict.status == "GO" and verdict.passing_share == 1.0


def test_verdict_lines_explain_the_result():
    lines = evaluate(full_set({"hair_crown": 2})).lines()
    assert lines[0].startswith("Verdict: GO")
    assert any("hair_crown" in line for line in lines[1:])
