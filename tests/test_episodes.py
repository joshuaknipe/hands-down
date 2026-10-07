import pytest

from handsdown.episodes import EpisodeTracker, Timing


def run(tracker, start, end, contact, step=0.1):
    """Feed frames every `step` seconds from `start` to `end`; returns all events."""
    events = []
    t = start
    while t < end - 1e-9:
        events += tracker.update(round(t, 3), contact)
        t += step
    return events


def kinds(events):
    return [e.kind for e in events]


def test_a_brush_shorter_than_dwell_never_alerts():
    tracker = EpisodeTracker(Timing())
    events = run(tracker, 0.0, 0.3, True) + run(tracker, 0.3, 3.0, False)
    assert events == [] and tracker.state == "idle"


def test_held_contact_alerts_once_at_the_dwell_time():
    tracker = EpisodeTracker(Timing())
    events = run(tracker, 0.0, 5.0, True)
    assert kinds(events) == ["alert"]
    assert events[0].time == pytest.approx(0.5)


def test_gap_shorter_than_grace_keeps_the_episode():
    tracker = EpisodeTracker(Timing())
    events = run(tracker, 0.0, 1.0, True) + run(tracker, 1.0, 1.8, False) + run(tracker, 1.8, 3.0, True)
    assert kinds(events) == ["alert"]
    assert tracker.state == "active"


def test_gap_during_candidate_shorter_than_grace_still_alerts():
    tracker = EpisodeTracker(Timing())
    events = run(tracker, 0.0, 0.3, True) + run(tracker, 0.3, 0.6, False) + run(tracker, 0.6, 1.0, True)
    assert kinds(events) == ["alert"]


def test_episode_ends_after_release_time_without_contact():
    tracker = EpisodeTracker(Timing())
    events = run(tracker, 0.0, 2.0, True) + run(tracker, 2.0, 6.0, False)
    assert kinds(events) == ["alert", "episode"]
    episode = events[1].episode
    assert episode.start == 0.0 and episode.duration_s == pytest.approx(1.9)
    assert episode.alerted and episode.ended == "released"
    assert tracker.state == "idle"


def test_a_new_episode_can_alert_after_the_last_one_ends():
    tracker = EpisodeTracker(Timing())
    events = run(tracker, 0.0, 1.0, True) + run(tracker, 1.0, 5.0, False) + run(tracker, 5.0, 6.0, True)
    assert kinds(events) == ["alert", "episode", "alert"]


def test_reminder_repeats_the_alert_during_a_long_episode():
    tracker = EpisodeTracker(Timing(reminder_s=2.0))
    events = run(tracker, 0.0, 5.0, True)
    assert kinds(events) == ["alert", "reminder", "reminder"]
    assert [round(e.time, 1) for e in events] == [0.5, 2.5, 4.5]


def test_reset_interrupts_an_active_episode():
    tracker = EpisodeTracker(Timing())
    run(tracker, 0.0, 1.0, True)
    events = tracker.reset(1.5)
    assert kinds(events) == ["episode"] and events[0].episode.ended == "interrupted"
    assert tracker.state == "idle" and tracker.reset(2.0) == []


def test_reset_drops_a_candidate_silently():
    tracker = EpisodeTracker(Timing())
    run(tracker, 0.0, 0.3, True)
    assert tracker.reset(0.3) == [] and tracker.state == "idle"


def test_timing_changes_apply_immediately():
    tracker = EpisodeTracker(Timing(dwell_s=2.0))
    assert run(tracker, 0.0, 1.0, True) == []
    tracker.timing = Timing(dwell_s=0.5)
    assert kinds(run(tracker, 1.0, 1.2, True)) == ["alert"]


def test_reminder_never_fires_after_the_hand_has_left():
    tracker = EpisodeTracker(Timing(reminder_s=2.0))
    events = run(tracker, 0.0, 1.0, True) + run(tracker, 1.0, 5.0, False)
    assert kinds(events) == ["alert", "episode"]


def test_reminder_waits_for_contact_to_come_back_within_the_episode():
    tracker = EpisodeTracker(Timing(reminder_s=2.0))
    events = run(tracker, 0.0, 1.0, True) + run(tracker, 1.0, 3.0, False) + run(tracker, 3.0, 3.5, True)
    assert kinds(events) == ["alert", "reminder"]
    assert events[1].time == pytest.approx(3.0)
