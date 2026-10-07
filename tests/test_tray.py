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
    assert actions == ["pause_call", "pause_15", "pause_60", "false_alert", "settings", "open_log", "quit"]


def test_menu_when_paused_offers_resume_first():
    items = menu_items("paused", paused=True)
    assert [i.action for i in items[1:3]] == ["resume", "false_alert"]
    assert "pause_call" not in [i.action for i in items]


def test_settings_command_runs_this_module_from_source():
    assert app.settings_command() == [sys.executable, "-m", "handsdown", "--settings"]


def test_settings_command_in_a_frozen_build(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert app.settings_command() == [sys.executable, "--settings"]
