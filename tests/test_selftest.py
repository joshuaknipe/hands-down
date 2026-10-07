from handsdown import selftest


def test_self_test_passes_from_source(monkeypatch, tmp_path):
    monkeypatch.setattr(selftest, "settings_path", lambda: tmp_path / "config" / "settings.json")
    monkeypatch.setattr(selftest, "log_dir", lambda: tmp_path / "logs")
    assert selftest.run_self_test() == 0


def test_self_test_fails_when_an_asset_is_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(selftest, "settings_path", lambda: tmp_path / "settings.json")
    monkeypatch.setattr(selftest, "log_dir", lambda: tmp_path / "logs")
    monkeypatch.setattr(selftest, "ASSETS", ("assets/missing.wav",))
    assert selftest.run_self_test() == 1
    assert "missing.wav" in capsys.readouterr().err


def test_self_test_checks_every_sound():
    from handsdown.chime import sound_file

    assert sound_file("knock", "quiet") in selftest.ASSETS
    assert "assets/chime.wav" not in selftest.ASSETS
