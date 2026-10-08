import sys

import pytest

from handsdown import app
from handsdown.tray import STATE_COLOURS, STATE_LABELS, draw_icon, menu_items


@pytest.mark.parametrize("state", list(STATE_COLOURS))
def test_icon_is_a_ring_in_the_state_colour(state):
    image = draw_icon(state)
    assert image.size == (64, 64) and image.mode == "RGBA"
    assert image.getpixel((32, 32))[3] == 0  # centre is transparent
    assert image.getpixel((32, 9))[:3] == STATE_COLOURS[state]  # on the ring
    assert image.getpixel((1, 1))[3] == 0  # corner is transparent


def test_every_state_has_a_plain_label():
    for state in STATE_COLOURS:
        assert STATE_LABELS[state]
    joined = " ".join(STATE_LABELS.values()).lower()
    assert "hair" not in joined and "pull" not in joined


def test_menu_when_watching():
    items = menu_items("watching", paused=False)
    assert items[0].label == STATE_LABELS["watching"] and not items[0].enabled
    actions = [i.action for i in items[1:]]
    assert actions == ["pause_call", "pause_15", "pause_60", "false_alert", "show_camera", "summary", "settings",
                       "open_log", "quit"]


def test_menu_when_paused_offers_resume_first():
    items = menu_items("paused", paused=True)
    assert [i.action for i in items[1:3]] == ["resume", "false_alert"]
    assert "pause_call" not in [i.action for i in items]


def test_settings_command_runs_this_module_from_source():
    assert app.settings_command() == [sys.executable, "-m", "handsdown", "--settings"]


def test_settings_command_in_a_frozen_build(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert app.settings_command() == [sys.executable, "--settings"]


def test_camera_view_command_runs_this_module_from_source():
    assert app.camera_view_command() == [sys.executable, "-m", "handsdown", "--camera-view"]


def test_menu_offers_hide_camera_while_the_view_is_open():
    actions = [i.action for i in menu_items("watching", paused=False, camera_open=True)]
    assert "hide_camera" in actions and "show_camera" not in actions
    assert "show_camera" in [i.action for i in menu_items("watching", paused=False)]


def test_border_command_runs_this_module_from_source():
    assert app.border_command() == [sys.executable, "-m", "handsdown", "--border"]


def test_summary_command_runs_this_module_from_source():
    assert app.summary_command() == [sys.executable, "-m", "handsdown", "--summary"]


class FakeDefaults:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def objectForKey_(self, key):
        return self.values.get(key)

    def setFloat_forKey_(self, value, key):
        self.values[key] = value


def test_menu_bar_position_is_set_near_the_clock_on_first_run():
    from handsdown.tray import MENU_BAR_POSITION_KEY, place_menu_bar_icon

    defaults = FakeDefaults()
    place_menu_bar_icon(defaults)
    assert defaults.values[MENU_BAR_POSITION_KEY] > 0


def test_menu_bar_position_chosen_by_the_user_is_kept():
    from handsdown.tray import MENU_BAR_POSITION_KEY, place_menu_bar_icon

    defaults = FakeDefaults({MENU_BAR_POSITION_KEY: 812.0})
    place_menu_bar_icon(defaults)
    assert defaults.values[MENU_BAR_POSITION_KEY] == 812.0
