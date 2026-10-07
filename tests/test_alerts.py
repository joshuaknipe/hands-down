import sys
import types
import wave

import numpy as np

from handsdown import alerts, chime
from handsdown.alerts import Alerter
from handsdown.paths import resource_path
from handsdown.settings import SOUNDS, VOLUMES, Settings


def test_chime_is_short_soft_and_starts_silent():
    samples = chime.chime()
    assert 0.5 < len(samples) / chime.RATE < 1.5
    assert np.abs(samples).max() <= 0.3
    assert abs(samples[0]) < 0.01


def test_write_wav_round_trip(tmp_path):
    path = tmp_path / "c.wav"
    chime.write_wav(path, chime.chime())
    with wave.open(str(path)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, chime.RATE)
        assert w.getnframes() == len(chime.chime())


def test_every_setting_sound_has_a_generator():
    assert set(chime.SOUNDS) == set(SOUNDS)


def test_every_sound_is_short_soft_and_starts_silent():
    for name in SOUNDS:
        samples = chime.SOUNDS[name]()
        assert 0.2 < len(samples) / chime.RATE < 1.5, name
        assert 0.1 < np.abs(samples).max() <= 0.3, name
        assert abs(samples[0]) < 0.01, name


def test_volumes_get_louder_up_to_full():
    gains = [chime.VOLUME_GAINS[v] for v in VOLUMES]
    assert gains == sorted(gains) and gains[-1] == 1.0


def test_every_sound_file_is_committed():
    for name in SOUNDS:
        for volume in VOLUMES:
            assert resource_path(chime.sound_file(name, volume)).stat().st_size > 10_000


def test_play_chime_on_mac_uses_afplay():
    calls = []
    alerts.play_chime("bell", "quiet", platform="darwin", runner=calls.append)
    assert calls == [["afplay", str(resource_path("assets/sounds/bell-quiet.wav"))]]


def test_play_chime_on_windows_plays_asynchronously(monkeypatch):
    played = []
    fake = types.SimpleNamespace(SND_FILENAME=1, SND_ASYNC=2, SND_NODEFAULT=4,
                                 PlaySound=lambda path, flags: played.append((path, flags)))
    monkeypatch.setitem(sys.modules, "winsound", fake)
    alerts.play_chime(platform="win32")
    assert played == [(str(resource_path("assets/sounds/chime-normal.wav")), 7)]


def test_mac_notify_is_discreet():
    calls = []
    alerts.mac_notify("Hands Down", "Gentle reminder", runner=calls.append)
    assert calls[0][:2] == ["osascript", "-e"]
    assert 'display notification "Gentle reminder" with title "Hands Down"' in calls[0][2]


class Recorder:
    def __init__(self):
        self.sounds, self.notes, self.warnings = 0, [], []

    def sound(self):
        self.sounds += 1

    def notify(self, title, text):
        self.notes.append((title, text))


def test_alerter_uses_the_alert_types_chosen_in_settings():
    r = Recorder()
    settings = [Settings(chime=True, notification=False)]
    alerter = Alerter(lambda: settings[0], r.sound, r.notify, r.warnings.append)
    alerter.alert("alert")
    settings[0] = Settings(chime=False, notification=True)
    alerter.alert("reminder")
    assert r.sounds == 1
    assert r.notes == [(alerts.NOTIFICATION_TITLE, alerts.NOTIFICATION_TEXT)]


def test_alerter_survives_failing_outputs():
    warnings = []

    def broken(*args):
        raise OSError("no audio device")

    alerter = Alerter(lambda: Settings(chime=True, notification=True), broken, broken, warnings.append)
    alerter.alert("alert")
    assert len(warnings) == 2 and "no audio device" in warnings[0]


def test_every_sound_is_about_as_audible_as_the_chime():
    def energy(samples):
        return float(np.sum(samples ** 2)) / chime.RATE

    reference = energy(chime.chime())
    for name in SOUNDS:
        assert energy(chime.SOUNDS[name]()) >= reference / 2, name
