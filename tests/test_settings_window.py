import sys

import pytest

from handsdown import startup
from handsdown.settings import LIMITS, SOUNDS, Settings, load_settings
from handsdown.settings_window import (RELEASE_CHOICES, REMINDER_CHOICES, SOUND_CHOICES, AutoSaver,
                                       form_values, settings_from_form)


def test_form_shows_current_settings_in_plain_choices():
    values = form_values(Settings(reminder_s=60.0, zone_margin=0.8, chime=False))
    assert values["reminder"] == "Every minute" and values["zone_margin"] == 0.8
    assert values["chime"] is False and values["dwell_s"] == 0.5


def test_unusual_values_show_the_closest_choice():
    assert form_values(Settings(reminder_s=50.0))["reminder"] == "Every minute"


def test_form_round_trip_keeps_hidden_settings():
    base = Settings(grace_s=2.0, release_s=5.0)
    values = form_values(base) | {"dwell_s": 1.25, "notification": True, "screen_border": True, "reminder": "Never",
                                  "zone_margin": 0.3}
    result = settings_from_form(values, base)
    assert result.dwell_s == 1.25 and result.notification and result.screen_border and result.reminder_s == 0.0
    assert result.zone_margin == 0.3
    assert (result.grace_s, result.release_s) == (2.0, 5.0)


def test_form_values_are_clamped():
    result = settings_from_form(form_values(Settings()) | {"dwell_s": 99.0, "camera_index": 42}, Settings())
    assert result.dwell_s == 5.0 and result.camera_index == 9


def test_every_choice_is_within_limits():
    assert list(REMINDER_CHOICES.values()) == [0.0, 1.5, 3.0, 5.0, 10.0, 15.0, 30.0, 60.0]
    low, high = LIMITS["release_s"]
    assert all(low <= v <= high for v in RELEASE_CHOICES.values())
    assert list(SOUND_CHOICES.values()) == list(SOUNDS)


def test_form_shows_sound_volume_release_and_lock():
    values = form_values(Settings(sound="knock", volume=40, release_s=10.0, pause_when_locked=False))
    assert values["sound"] == "Soft knock" and values["volume"] == 40
    assert values["release"] == "10 seconds" and values["pause_when_locked"] is False


def test_form_round_trip_of_the_new_choices():
    values = form_values(Settings()) | {"sound": "Bell", "volume": 62.7, "release": "5 seconds",
                                        "pause_when_locked": False}
    result = settings_from_form(values, Settings())
    assert (result.sound, result.volume, result.release_s, result.pause_when_locked) == ("bell", 63, 5.0, False)


class FakeKey:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


class FakeWinreg:
    HKEY_CURRENT_USER = "HKCU"
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self):
        self.values = {}

    def OpenKey(self, root, path, reserved, access):
        assert (root, path) == ("HKCU", startup.RUN_KEY)
        return FakeKey()

    def SetValueEx(self, key, name, reserved, kind, value):
        self.values[name] = value

    def DeleteValue(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


def test_packaged_build_registers_and_unregisters(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\HandsDown\HandsDown.exe")
    reg = FakeWinreg()
    assert startup.set_start_with_windows(True, winreg=reg) is True
    assert reg.values == {"Hands Down": r'"C:\Apps\HandsDown\HandsDown.exe"'}
    assert startup.set_start_with_windows(False, winreg=reg) is False
    assert reg.values == {}
    assert startup.set_start_with_windows(False, winreg=reg) is False  # already off is fine


def test_running_from_source_never_registers():
    reg = FakeWinreg()
    assert startup.launch_command() is None
    assert startup.set_start_with_windows(True, winreg=reg) is False
    assert reg.values == {}


@pytest.mark.skipif(sys.platform == "win32", reason="checks the non-Windows path")
def test_start_with_windows_does_nothing_elsewhere():
    assert startup.set_start_with_windows(True) is False


def test_zone_sliders_round_trip_and_clamp():
    values = form_values(Settings(zone_above=0.4, zone_below=1.2, chin_cutout=0.0))
    assert (values["zone_above"], values["zone_below"], values["chin_cutout"]) == (0.4, 1.2, 0.0)
    result = settings_from_form(values | {"zone_above": 0.333, "zone_below": 99.0, "chin_cutout": 1.5}, Settings())
    assert (result.zone_above, result.zone_below, result.chin_cutout) == (0.33, LIMITS["zone_below"][1], 1.5)


def test_autosaver_saves_each_change(tmp_path):
    path = tmp_path / "settings.json"
    saver = AutoSaver(path, Settings())
    saver.update(form_values(Settings()) | {"dwell_s": 1.0})
    assert load_settings(path).dwell_s == 1.0
    saver.update(form_values(Settings()) | {"dwell_s": 1.0, "zone_above": 0.2})
    assert load_settings(path).zone_above == 0.2


def test_autosaver_skips_values_that_did_not_change(tmp_path):
    saves = []
    saver = AutoSaver(tmp_path / "settings.json", Settings(), save=lambda path, settings: saves.append(settings))
    saver.update(form_values(Settings()))
    assert saves == []
    saver.update(form_values(Settings()) | {"chime": False})
    saver.update(form_values(Settings()) | {"chime": False})
    assert len(saves) == 1


def test_autosaver_only_touches_startup_when_that_box_changes(tmp_path):
    calls = []

    def startup(enabled):
        calls.append(enabled)
        return False  # e.g. running from source: registering is refused

    saver = AutoSaver(tmp_path / "settings.json", Settings(), set_startup=startup)
    saver.update(form_values(Settings()) | {"dwell_s": 2.0})
    assert calls == []
    saver.update(form_values(Settings()) | {"dwell_s": 2.0, "start_with_windows": True})
    assert calls == [True]
    assert load_settings(tmp_path / "settings.json").start_with_windows is False


def fake_app(monkeypatch, tmp_path):
    executable = tmp_path / "Applications" / "HandsDown.app" / "Contents" / "MacOS" / "HandsDown"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    return executable.parents[2]


def test_packaged_mac_app_adds_and_removes_a_login_item(monkeypatch, tmp_path):
    import plistlib

    bundle = fake_app(monkeypatch, tmp_path)
    agents = tmp_path / "LaunchAgents"
    assert startup.set_start_at_login_mac(True, agents_dir=agents) is True
    plist = plistlib.loads((agents / startup.LAUNCH_AGENT_FILE).read_bytes())
    assert plist["ProgramArguments"] == ["/usr/bin/open", "-a", str(bundle)]
    assert plist["RunAtLoad"] is True and plist["Label"] == startup.LAUNCH_AGENT_LABEL
    assert startup.set_start_at_login_mac(False, agents_dir=agents) is False
    assert not (agents / startup.LAUNCH_AGENT_FILE).exists()
    assert startup.set_start_at_login_mac(False, agents_dir=agents) is False  # already off is fine


def test_mac_from_source_never_adds_a_login_item(tmp_path):
    agents = tmp_path / "LaunchAgents"
    assert startup.set_start_at_login_mac(True, agents_dir=agents) is False
    assert not agents.exists()


def test_start_at_login_picks_the_platform(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(startup, "set_start_with_windows", lambda enabled: calls.append(("win", enabled)) or True)
    monkeypatch.setattr(startup, "set_start_at_login_mac", lambda enabled: calls.append(("mac", enabled)) or True)
    assert startup.set_start_at_login(True, platform="win32") is True
    assert startup.set_start_at_login(True, platform="darwin") is True
    assert startup.set_start_at_login(True, platform="linux") is False
    assert calls == [("win", True), ("mac", True)]


def test_startup_label_names_the_platform():
    assert startup.startup_label("win32") == "Start with Windows"
    assert startup.startup_label("darwin") == "Start at login"
    assert startup.startup_label("linux") is None


def test_screen_effect_form_is_saved_and_clamped(tmp_path):
    base = Settings()
    values = form_values(base) | {"border_color": "#0088ff", "border_width": 17.6,
                                 "screen_text": True, "custom_text": "Relax your hands",
                                 "screen_blur": True, "blur_level": 22.4}
    saver = AutoSaver(tmp_path / "settings.json", base)
    result = saver.update(values)
    assert result.border_color == "#0088ff" and result.border_width == 18
    assert result.screen_text and result.custom_text == "Relax your hands"
    assert result.screen_blur and result.blur_level == 22
    assert load_settings(tmp_path / "settings.json") == result


def test_live_preview_changes_immediately_and_closes_when_leaving_tab():
    from handsdown import settings_window
    from tests.test_border import make_border
    from handsdown.border import Border
    import json

    overlay, processes, _ = make_border()
    preview = settings_window.SettingsPreview(overlay)
    values = form_values(Settings(screen_border=True))
    preview.update(values, active=False)
    assert not processes
    preview.update(values, active=True)
    preview.update(values | {"border_width": 30, "custom_text": "Relax"}, active=True)
    lines = processes[0].stdin.getvalue().decode().splitlines()
    assert lines[1] == "show"
    assert json.loads(lines[-1].removeprefix("configure "))["border_width"] == 30
    preview.update(values, active=False)
    assert processes[0].stdin.closed_by_border
    preview.update(values, active=True)
    preview.close()
    assert processes[1].stdin.closed_by_border


def test_preview_mode_is_sent_to_overlay_renderer():
    import json
    from tests.test_border import FakeProcess
    from handsdown.border import Border
    process = FakeProcess()
    overlay = Border(["border"], popen=lambda *a, **kw: process, preview=True)
    overlay.update(Settings(screen_text=True), True)
    config = json.loads(process.stdin.getvalue().decode().splitlines()[0].removeprefix("configure "))
    assert config["preview"] is True


def test_text_style_form_and_preview_forward_all_options(tmp_path):
    import json
    from handsdown.settings_window import SettingsPreview
    from tests.test_border import make_border
    base = Settings()
    values = form_values(base) | {"screen_text": True, "border_width": 450, "text_size": 63.6,
                                 "text_color": "#ff8800", "text_background": False,
                                 "text_background_color": "#112233", "text_padding_x": 50,
                                 "text_padding_y": 25, "text_position": "Top left"}
    result = AutoSaver(tmp_path / "settings.json", base).update(values)
    assert result.text_size == 64 and result.text_position == "top-left"
    assert result.text_color == "#ff8800" and not result.text_background
    assert result.text_padding_x == 50 and result.text_padding_y == 25
    assert form_values(result)["text_position"] == "Top left"
    overlay, processes, _ = make_border()
    SettingsPreview(overlay).update(values, active=True)
    config = json.loads(processes[0].stdin.getvalue().decode().splitlines()[0].removeprefix("configure "))
    assert config["text_position"] == "top-left" and config["text_size"] == 64
    assert config["text_background"] is False and config["border_width"] == 450


def test_pause_for_calls_is_saved_from_the_form(tmp_path):
    path = tmp_path / "settings.json"
    saver = AutoSaver(path, Settings())
    result = saver.update(form_values(Settings()) | {"pause_for_calls": True})
    assert result.pause_for_calls and load_settings(path).pause_for_calls


def test_settings_preserves_a_tray_call_toggle_when_an_unrelated_control_changes(tmp_path):
    from handsdown.settings import save_settings
    path = tmp_path / "settings.json"
    original = Settings()
    save_settings(path, original)
    saver = AutoSaver(path, original)
    save_settings(path, Settings(pause_for_calls=True))  # tray changed it while the form was open
    saver.update(form_values(original) | {"volume": 80})
    assert load_settings(path).pause_for_calls and load_settings(path).volume == 80
    saver.update(form_values(original) | {"volume": 85})
    assert load_settings(path).pause_for_calls
    # Once the form observes the new value, an explicit checkbox change still wins.
    saver.update(form_values(load_settings(path)))
    saver.update(form_values(load_settings(path)) | {"pause_for_calls": False})
    assert not load_settings(path).pause_for_calls
