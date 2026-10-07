from feasibility.evaluate import ClipOutcome, outcome_from, summary_lines
from handsdown.landmarks import Observation
from handsdown.settings import Settings

FACE = (0.4, 0.3, 0.6, 0.6)
TEMPLE = tuple((0.33, 0.4) for _ in range(21))


def frames(contact_flags, step_ms=100):
    return [Observation(i * step_ms, (TEMPLE,) if c else (), True, FACE) for i, c in enumerate(contact_flags)]


def test_held_contact_alerts_with_latency():
    outcome = outcome_from("hair_side", "dev", "a.mp4", frames([True] * 20), Settings())
    assert outcome.alerted and outcome.latency_s == 0.5 and outcome.contact_rate == 1.0


def test_brief_contact_does_not_alert():
    outcome = outcome_from("chin_rest", "dev", "b.mp4", frames([True] * 3 + [False] * 17), Settings())
    assert not outcome.alerted and outcome.latency_s is None
    assert outcome.contact_rate == 0.15


def test_empty_clip():
    outcome = outcome_from("glasses", "dev", "c.mp4", [], Settings())
    assert not outcome.alerted and outcome.contact_rate == 0.0


def test_summary_counts_hair_and_other_clips_separately():
    outcomes = [
        ClipOutcome("hair_side", "dev", "1.mp4", 1.0, True, 0.5),
        ClipOutcome("hair_side", "dev", "2.mp4", 0.2, False, None),
        ClipOutcome("chin_rest", "dev", "3.mp4", 0.9, True, 0.6),
    ]
    lines = summary_lines(outcomes)
    assert any(line.startswith("hair_side") and "1/2 alerted" in line for line in lines)
    assert any("Hair positions: 1/2 clips alerted" in line for line in lines)
    assert any("Other positions: 1/1 clips alerted" in line for line in lines)
