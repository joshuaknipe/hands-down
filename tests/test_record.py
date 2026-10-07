from datetime import datetime, timedelta

import numpy as np
import pytest

from feasibility.clips import load_clips
from feasibility.record import MIN_CLIP_FRAMES, ClipRecorder, draw_overlay
from handsdown.landmarks import Observation
from tests.helpers import FakeClock

SIZE = (64, 48)


class FakeWriter:
    def __init__(self, path, fps, size):
        self.path, self.size, self.frames, self.released = path, size, [], False
        path.write_bytes(b"video")

    def write(self, frame):
        self.frames.append(frame)

    def release(self):
        self.released = True


def make_recorder(tmp_path, clock, label="hair_scalp"):
    writers = []
    stamp = [datetime(2026, 10, 7, 12, 0, 0)]

    def now():
        stamp[0] += timedelta(seconds=1)
        return stamp[0]

    def factory(path, fps, size):
        writers.append(FakeWriter(path, fps, size))
        return writers[-1]

    recorder = ClipRecorder(tmp_path, label, "dshow", SIZE, writer_factory=factory, clock=clock, now=now)
    return recorder, writers


def frame(value=128):
    return np.full((SIZE[1], SIZE[0], 3), value, np.uint8)


def record_clip(recorder, clock, frames):
    recorder.start()
    for _ in range(frames):
        recorder.add(frame())
        clock.now += 0.033
    return recorder.stop()


def test_recorder_saves_video_and_metadata(tmp_path):
    clock = FakeClock(100.0)
    recorder, writers = make_recorder(tmp_path, clock)
    clip = record_clip(recorder, clock, MIN_CLIP_FRAMES)
    assert clip is not None and clip.video.is_file()
    assert writers[0].released and len(writers[0].frames) == MIN_CLIP_FRAMES
    assert clip.meta.timestamps_ms[:3] == [0, 33, 66]
    assert (clip.meta.label, clip.meta.split, clip.meta.width, clip.meta.height) == ("hair_scalp", "dev", 64, 48)
    assert load_clips(tmp_path)[0].meta == clip.meta
    assert recorder.saved == 1 and not recorder.recording


def test_short_recording_is_discarded(tmp_path):
    clock = FakeClock()
    recorder, writers = make_recorder(tmp_path, clock)
    assert record_clip(recorder, clock, MIN_CLIP_FRAMES - 1) is None
    assert not writers[0].path.exists()
    assert load_clips(tmp_path) == []
    assert recorder.saved == 0


def test_fourth_clip_is_held_out(tmp_path):
    clock = FakeClock()
    recorder, _ = make_recorder(tmp_path, clock)
    splits = [record_clip(recorder, clock, MIN_CLIP_FRAMES).meta.split for _ in range(4)]
    assert splits == ["dev", "dev", "dev", "holdout"]


def test_add_does_nothing_when_not_recording(tmp_path):
    recorder, writers = make_recorder(tmp_path, FakeClock())
    recorder.add(frame())
    assert writers == [] and recorder.stop() is None


def test_recorder_resizes_frames_to_writer_size(tmp_path):
    recorder, writers = make_recorder(tmp_path, FakeClock())
    recorder.start()
    recorder.add(np.full((480, 640, 3), 128, np.uint8))
    assert writers[0].frames[0].shape == (48, 64, 3)


def test_unknown_label_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="waving"):
        make_recorder(tmp_path, FakeClock(), label="waving")


def test_overlay_marks_landmarks_and_recording():
    image = np.zeros((480, 640, 3), np.uint8)
    observation = Observation(0, (((0.5, 0.5),),), True)
    out = draw_overlay(image, observation, recording=True, label="hair_scalp", saved=2)
    assert tuple(out[240, 320]) == (0, 255, 0)  # landmark dot at the centre
    assert tuple(out[25, 615]) == (0, 0, 255)  # red recording dot top right


def test_overlay_without_observation_or_recording():
    out = draw_overlay(np.zeros((480, 640, 3), np.uint8), None, recording=False, label="chin_rest", saved=0)
    assert tuple(out[25, 615]) == (0, 0, 0)
