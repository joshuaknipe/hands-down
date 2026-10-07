from datetime import datetime
from pathlib import Path

import pytest

from feasibility import clips
from feasibility.clips import ClipMeta


def make_meta(label="hair_scalp", split="dev"):
    return ClipMeta(label, split, "2026-10-07T12:00:00", "dshow", 640, 480, [0, 33, 66])


def write_clip(clips_dir: Path, name: str, meta: ClipMeta, video=True, meta_text=None):
    folder = clips_dir / meta.label
    folder.mkdir(parents=True, exist_ok=True)
    if video:
        (folder / f"{name}.mp4").write_bytes(b"video")
    (folder / f"{name}.json").write_text(meta_text if meta_text is not None else meta.to_json())


def test_labels_describe_hand_position_only():
    assert set(clips.TRUE_POSITIVE_LABELS).isdisjoint(clips.FALSE_POSITIVE_LABELS)
    for label in clips.LABELS:
        assert "pull" not in label and "trich" not in label


def test_every_fourth_clip_of_a_label_is_held_out():
    assert [clips.assign_split(n) for n in range(8)] == ["dev", "dev", "dev", "holdout"] * 2


def test_meta_round_trips_through_json():
    meta = make_meta()
    assert ClipMeta.from_json(meta.to_json()) == meta


@pytest.mark.parametrize("change, error", [
    ({"label": "waving"}, ValueError),
    ({"split": "train"}, ValueError),
    ({"timestamps_ms": [0, "x"]}, ValueError),
    ({"surprise": 1}, TypeError),
])
def test_meta_rejects_bad_data(change, error):
    import json

    data = json.loads(make_meta().to_json()) | change
    with pytest.raises(error):
        ClipMeta.from_json(json.dumps(data))


def test_new_clip_paths_share_a_stem_inside_the_label_folder(tmp_path):
    video, meta = clips.new_clip_paths(tmp_path, "hair_crown", datetime(2026, 10, 7, 9, 5, 3, 120000))
    assert video == tmp_path / "hair_crown" / "20261007-090503-120000.mp4"
    assert meta == tmp_path / "hair_crown" / "20261007-090503-120000.json"


def test_count_and_load_clips(tmp_path):
    write_clip(tmp_path, "a", make_meta())
    write_clip(tmp_path, "b", make_meta("chin_rest"))
    assert clips.count_clips(tmp_path, "hair_scalp") == 1
    assert clips.count_clips(tmp_path, "hair_crown") == 0
    loaded = clips.load_clips(tmp_path)
    assert [c.meta.label for c in loaded] == ["chin_rest", "hair_scalp"]
    assert loaded[1].video == tmp_path / "hair_scalp" / "a.mp4"


def test_load_clips_skips_orphans_and_corrupt_metadata(tmp_path):
    write_clip(tmp_path, "good", make_meta())
    write_clip(tmp_path, "no-video", make_meta(), video=False)
    write_clip(tmp_path, "corrupt", make_meta(), meta_text="{not json")
    (tmp_path / "hair_scalp" / "no-meta.mp4").write_bytes(b"video")  # recording crashed before metadata
    warnings = []
    loaded = clips.load_clips(tmp_path, warn=warnings.append)
    assert [c.video.name for c in loaded] == ["good.mp4"]
    assert len(warnings) == 2
    assert any("no-video" in w and "missing" in w for w in warnings)
    assert any("corrupt" in w and "unreadable" in w for w in warnings)


def test_load_clips_from_a_missing_folder_is_empty(tmp_path):
    assert clips.load_clips(tmp_path / "nothing-here") == []
