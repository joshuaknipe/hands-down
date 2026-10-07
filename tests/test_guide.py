from pathlib import Path

from feasibility.clips import LABELS
from feasibility.guide import GuidedSession


def fake_clips(clips_dir: Path, label: str, count: int) -> None:
    folder = clips_dir / label
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (folder / f"{i}.json").write_text("{}")


def test_starts_at_the_first_label_with_instructions(tmp_path):
    session = GuidedSession(tmp_path)
    assert session.label == "hair_scalp"
    lines = session.lines(recording=False)
    assert lines[0] == "1/10  hair_scalp  -  clip 1 of 4"
    assert "top or at the front of the head" in lines[1]
    assert "in position" in lines[2] and "SPACE with your other hand" in lines[2] and "N next" in lines[2]


def test_resumes_at_the_first_label_that_still_needs_clips(tmp_path):
    fake_clips(tmp_path, "hair_scalp", 4)
    fake_clips(tmp_path, "hair_crown", 1)
    session = GuidedSession(tmp_path)
    assert session.label == "hair_crown"
    assert session.lines(recording=False)[0] == "2/10  hair_crown  -  clip 2 of 4"


def test_next_and_previous_stop_at_the_ends(tmp_path):
    session = GuidedSession(tmp_path)
    session.back()
    assert session.label == "hair_scalp"
    for _ in range(20):
        session.advance()
    assert session.label == LABELS[-1]


def test_after_a_label_is_complete_it_moves_to_the_next_incomplete_one(tmp_path):
    fake_clips(tmp_path, "hair_crown", 4)
    session = GuidedSession(tmp_path)
    fake_clips(tmp_path, "hair_scalp", 4)
    session.advance_to_incomplete()
    assert session.label == "hair_side"


def test_moving_on_wraps_back_to_skipped_labels(tmp_path):
    for label in LABELS[1:]:
        fake_clips(tmp_path, label, 4)
    session = GuidedSession(tmp_path)
    session.advance()  # skip hair_scalp without recording
    session.advance_to_incomplete()
    assert session.label == "hair_scalp"


def test_finished_when_every_label_has_its_clips(tmp_path):
    for label in LABELS:
        fake_clips(tmp_path, label, 4)
    session = GuidedSession(tmp_path)
    assert session.finished
    assert "All clips recorded" in " ".join(session.lines(recording=False))


def test_single_label_session(tmp_path):
    session = GuidedSession(tmp_path, labels=("glasses",))
    assert session.lines(recording=False)[0] == "1/1  glasses  -  clip 1 of 2"


def test_lines_while_recording_say_how_to_stop(tmp_path):
    lines = GuidedSession(tmp_path).lines(recording=True)
    assert "keep your hand there" in lines[2] and "SPACE to stop" in lines[2]
