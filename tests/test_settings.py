import json
import os

from handsdown.settings import LIMITS, Settings, SettingsStore, clamp, load_settings, save_settings


def test_missing_file_gives_defaults(tmp_path):
    assert load_settings(tmp_path / "settings.json") == Settings()


def test_settings_round_trip(tmp_path):
    path = tmp_path / "sub" / "settings.json"
    custom = Settings(dwell_s=1.5, chime=False, notification=True, screen_border=True, camera_index=1)
    save_settings(path, custom)
    assert load_settings(path) == custom


def test_load_settings_survives_bad_files(tmp_path):
    path = tmp_path / "settings.json"
    warnings = []
    for text in ("{not json", "[1, 2]", ""):
        path.write_text(text)
        assert load_settings(path, warn=warnings.append) == Settings()
    assert len(warnings) == 3


def test_load_settings_ignores_wrong_types_and_clamps(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "dwell_s": 99, "grace_s": "long", "chime": "yes", "camera_index": 2.5,
        "zone_margin": -1, "from_a_newer_version": True,
    }))
    loaded = load_settings(path)
    assert loaded.dwell_s == LIMITS["dwell_s"][1]
    assert loaded.zone_margin == LIMITS["zone_margin"][0]
    assert loaded.grace_s == Settings().grace_s
    assert loaded.chime is True and loaded.camera_index == 0


def test_clamp_keeps_values_in_range():
    assert clamp(Settings(release_s=0.0)).release_s == LIMITS["release_s"][0]
    assert clamp(Settings()) == Settings()


def test_store_reloads_when_the_file_changes(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    assert store.get() == Settings()
    save_settings(path, Settings(dwell_s=2.0))
    os.utime(path, ns=(1, 1_000_000_000))  # make sure the modification time differs
    assert store.get().dwell_s == 2.0
    path.unlink()
    assert store.get() == Settings()


def test_sound_choices_survive_a_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    custom = Settings(sound="bell", volume="quiet", pause_when_locked=False)
    save_settings(path, custom)
    assert load_settings(path) == custom


def test_unknown_sound_or_volume_falls_back_to_the_default(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"sound": "air horn", "volume": 11, "pause_when_locked": "no"}))
    loaded = load_settings(path)
    assert loaded.sound == Settings().sound and loaded.volume == Settings().volume
    assert loaded.pause_when_locked is True
    assert clamp(Settings(sound="nope", volume="loud")) == Settings()


def test_zone_shape_settings_are_clamped():
    loaded = clamp(Settings(zone_above=-1.0, zone_below=9.0, chin_cutout=5.0))
    assert loaded.zone_above == LIMITS["zone_above"][0]
    assert loaded.zone_below == LIMITS["zone_below"][1]
    assert loaded.chin_cutout == LIMITS["chin_cutout"][1]
    assert LIMITS["chin_cutout"][0] == 0.0  # off is allowed
