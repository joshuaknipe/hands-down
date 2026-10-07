import numpy as np

from handsdown.landmarks import Observation, TimestampGuard, Tracker, bounding_box


def test_guard_passes_increasing_timestamps():
    guard = TimestampGuard()
    assert [guard.next(t) for t in (0, 33, 66)] == [0, 33, 66]


def test_guard_nudges_repeated_and_backwards_timestamps():
    guard = TimestampGuard()
    assert [guard.next(t) for t in (100, 100, 90, 200)] == [100, 101, 102, 200]


def test_observation_hand_found():
    assert Observation(0, (((0.1, 0.2),),), False).hand_found
    assert not Observation(0, (), True).hand_found


def test_tracker_finds_nothing_in_a_blank_frame():
    with Tracker() as tracker:
        observation = tracker.process(np.zeros((480, 640, 3), np.uint8), 0)
    assert not observation.hand_found
    assert not observation.face_found


def test_tracker_accepts_repeated_timestamps():
    frame = np.zeros((480, 640, 3), np.uint8)
    with Tracker() as tracker:
        tracker.process(frame, 0)
        second = tracker.process(frame, 0)  # MediaPipe alone would raise ValueError here
    assert second.timestamp_ms == 1


def test_bounding_box_of_points():
    assert bounding_box([(0.4, 0.5), (0.6, 0.3), (0.5, 0.7)]) == (0.4, 0.3, 0.6, 0.7)


def test_tracker_reports_no_face_box_without_a_face():
    with Tracker() as tracker:
        assert tracker.process(np.zeros((480, 640, 3), np.uint8), 0).face_box is None


def test_observation_face_box_defaults_to_none():
    assert Observation(0, (), True).face_box is None
