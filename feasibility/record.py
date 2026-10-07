"""Record labelled clips while showing live hand and face tracking.

The preview shows landmarks; the saved video is the raw camera frames.
"""

import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from feasibility.clips import LABELS, Clip, ClipMeta, assign_split, count_clips, new_clip_paths, save_meta
from handsdown.camera import Backend, open_camera
from handsdown.landmarks import Observation, Tracker

MIN_CLIP_FRAMES = 15  # shorter recordings are accidental key presses and are discarded
NOMINAL_FPS = 30.0  # written into the file header only; real frame times are kept in the metadata
PREVIEW_TRACK_EVERY = 3  # track every 3rd frame so the preview keeps up on a laptop CPU
MAX_FAILED_READS = 50
WINDOW = "Hands Down - clip recorder"
FONT = cv2.FONT_HERSHEY_SIMPLEX


def open_writer(path: Path, fps: float, size: tuple[int, int]):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    if not writer.isOpened():
        raise RuntimeError(f"Could not open a video writer for {path}")
    return writer


class ClipRecorder:
    def __init__(self, clips_dir: Path, label: str, backend: str, size: tuple[int, int],
                 writer_factory=open_writer, clock=time.monotonic, now=datetime.now):
        if label not in LABELS:
            raise ValueError(f"Unknown label {label!r}; expected one of {', '.join(LABELS)}")
        self._clips_dir = clips_dir
        self._label = label
        self._backend = backend
        self._size = size
        self._writer_factory = writer_factory
        self._clock = clock
        self._now = now
        self._writer = None
        self.saved = count_clips(clips_dir, label)

    @property
    def recording(self) -> bool:
        return self._writer is not None

    def start(self) -> None:
        if self.recording:
            return
        stamp = self._now()
        self._video, self._meta_path = new_clip_paths(self._clips_dir, self._label, stamp)
        self._video.parent.mkdir(parents=True, exist_ok=True)
        self._recorded_at = stamp.isoformat(timespec="seconds")
        self._timestamps: list[int] = []
        self._started = self._clock()
        self._writer = self._writer_factory(self._video, NOMINAL_FPS, self._size)

    def add(self, frame: np.ndarray) -> None:
        if not self.recording:
            return
        if (frame.shape[1], frame.shape[0]) != self._size:
            # VideoWriter silently drops frames of the wrong size, which would desync the timestamps
            frame = cv2.resize(frame, self._size)
        self._writer.write(frame)
        self._timestamps.append(int(round((self._clock() - self._started) * 1000)))

    def stop(self) -> Clip | None:
        """Finish the clip. Returns None, and deletes the video, if it was too short to keep."""
        if not self.recording:
            return None
        self._writer.release()
        self._writer = None
        if len(self._timestamps) < MIN_CLIP_FRAMES:
            self._video.unlink(missing_ok=True)
            return None
        meta = ClipMeta(
            self._label, assign_split(self.saved), self._recorded_at, self._backend,
            self._size[0], self._size[1], list(self._timestamps),
        )
        save_meta(self._meta_path, meta)
        self.saved += 1
        return Clip(self._video, meta)


def draw_overlay(frame: np.ndarray, observation: Observation | None, recording: bool, label: str, saved: int) -> np.ndarray:
    h, w = frame.shape[:2]
    if observation is not None:
        for hand in observation.hands:
            for x, y in hand:
                cv2.circle(frame, (int(x * w), int(y * h)), 3, (0, 255, 0), -1)
        status = f"hand: {'yes' if observation.hand_found else 'no'}   face: {'yes' if observation.face_found else 'no'}"
        cv2.putText(frame, status, (10, h - 15), FONT, 0.6, (255, 255, 255), 2)
    cv2.putText(frame, f"{label}   saved: {saved}", (10, 25), FONT, 0.6, (255, 255, 255), 2)
    if recording:
        cv2.circle(frame, (w - 25, 25), 10, (0, 0, 255), -1)
    return frame


def _report(clip: Clip | None) -> None:
    if clip is None:
        print(f"  discarded (under {MIN_CLIP_FRAMES} frames)")
    else:
        seconds = clip.meta.timestamps_ms[-1] / 1000
        print(f"  saved {clip.video.name}: {len(clip.meta.timestamps_ms)} frames, {seconds:.1f} s, {clip.meta.split}")


def run_record(label: str, camera_index: int, backend: Backend, clips_dir: Path) -> int:
    result = open_camera(camera_index, backend)
    if not result.ok:
        print(f"Could not open camera {camera_index} with {backend.name}: {result.error}")
        return 1
    capture = result.capture
    ok, frame = capture.read()
    if not ok:
        print("The camera stopped delivering frames.")
        capture.release()
        return 1
    recorder = ClipRecorder(clips_dir, label, backend.name, (frame.shape[1], frame.shape[0]))
    print(f"Recording '{label}' ({recorder.saved} saved so far). SPACE starts and stops a clip; Q or Esc quits.")
    observation = None
    frame_no = 0
    failed = 0
    started = time.monotonic()
    try:
        with Tracker() as tracker:
            while True:
                ok, frame = capture.read()
                if not ok:
                    failed += 1
                    if failed >= MAX_FAILED_READS:
                        print("The camera stopped delivering frames.")
                        break
                    continue
                failed = 0
                recorder.add(frame)
                if frame_no % PREVIEW_TRACK_EVERY == 0:
                    observation = tracker.process(frame, int((time.monotonic() - started) * 1000))
                frame_no += 1
                cv2.imshow(WINDOW, draw_overlay(frame.copy(), observation, recorder.recording, label, recorder.saved))
                key = cv2.waitKey(1) & 0xFF
                if key == ord(" "):
                    if recorder.recording:
                        _report(recorder.stop())
                    else:
                        recorder.start()
                        print("  recording...")
                elif key in (ord("q"), 27):
                    break
                if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break  # window closed with the mouse
    finally:
        if recorder.recording:  # Q, a closed window, Ctrl+C or a crash mid-clip still finalises the file
            _report(recorder.stop())
        capture.release()
        cv2.destroyAllWindows()
    return 0
