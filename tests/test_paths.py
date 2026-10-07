import hashlib
import sys

import pytest

from handsdown import paths


def test_resource_path_from_source_is_under_project_root():
    assert paths.resource_path("models/hand_landmarker.task") == (
        paths.PROJECT_ROOT / "models" / "hand_landmarker.task"
    )


def test_resource_path_when_frozen_uses_pyinstaller_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert paths.resource_path("models/x.task") == tmp_path / "models" / "x.task"


def test_bundled_models_match_recorded_hashes():
    lines = (paths.PROJECT_ROOT / "models" / "SHA256SUMS").read_text().splitlines()
    assert len(lines) == 2
    for line in lines:
        expected, name = line.split()
        digest = hashlib.sha256(paths.model_path(name).read_bytes()).hexdigest()
        assert digest == expected, name


def test_missing_model_raises_with_path():
    with pytest.raises(FileNotFoundError, match="nope.task"):
        paths.model_path("nope.task")


def test_data_folders_are_under_project_root():
    assert paths.clips_dir() == paths.PROJECT_ROOT / "clips"
    assert paths.reports_dir() == paths.PROJECT_ROOT / "reports"


def test_user_folders_are_named_for_the_app():
    assert paths.settings_path().name == "settings.json"
    assert "Hands Down" in str(paths.settings_path())
    assert "Hands Down" in str(paths.log_dir())
