import sys

import pytest

from handsdown import startup
from handsdown.settings import Settings
from handsdown.settings_window import REMINDER_CHOICES, ZONE_CHOICES, form_values, settings_from_form


def test_form_shows_current_settings_in_plain_choices():
    values = form_values(Settings(reminder_s=60.0, zone_margin=0.8, chime=False))
    assert values["reminder"] == "Every minute" and values["zone"] == "Large"
    assert values["chime"] is False and values["dwell_s"] == 0.5


def test_unusual_values_show_the_closest_choice():
    assert form_values(Settings(reminder_s=50.0))["reminder"] == "Every minute"
    assert form_values(Settings(zone_margin=0.45))["zone"] == "Medium"


def test_form_round_trip_keeps_hidden_settings():
    base = Settings(grace_s=2.0, release_s=5.0)
    values = form_values(base) | {"dwell_s": 1.25, "notification": True, "reminder": "Off", "zone": "Small"}
    result = settings_from_form(values, base)
    assert result.dwell_s == 1.25 and result.notification and result.reminder_s == 0.0
    assert result.zone_margin == ZONE_CHOICES["Small"]
    assert (result.grace_s, result.release_s) == (2.0, 5.0)


def test_form_values_are_clamped():
    result = settings_from_form(form_values(Settings()) | {"dwell_s": 99.0, "camera_index": 42}, Settings())
    assert result.dwell_s == 5.0 and result.camera_index == 9


def test_every_choice_is_within_limits():
    assert set(REMINDER_CHOICES.values()) <= {0.0, 30.0, 60.0, 120.0}
    assert all(0.1 <= v <= 1.5 for v in ZONE_CHOICES.values())


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
