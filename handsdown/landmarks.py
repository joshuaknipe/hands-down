"""Run MediaPipe's hand and face landmarkers on video frames."""

from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core.base_options import BaseOptions

from handsdown.paths import model_path

Point = tuple[float, float]


@dataclass(frozen=True)
class Observation:
    timestamp_ms: int
    hands: tuple[tuple[Point, ...], ...]  # per hand, normalised (x, y) landmarks
    face_found: bool

    @property
    def hand_found(self) -> bool:
        return len(self.hands) > 0


class TimestampGuard:
    """MediaPipe VIDEO mode rejects timestamps that do not strictly increase; nudge them forward."""

    def __init__(self):
        self._last: int | None = None

    def next(self, timestamp_ms: int) -> int:
        if self._last is not None and timestamp_ms <= self._last:
            timestamp_ms = self._last + 1
        self._last = timestamp_ms
        return timestamp_ms


class Tracker:
    """Hand and face landmarkers in VIDEO mode, which tracks between frames instead of re-detecting.

    Use one Tracker per video stream: VIDEO mode keeps state between frames.
    """

    def __init__(self, num_hands: int = 2):
        self._hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path("hand_landmarker.task"))),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=num_hands,
        ))
        self._face = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path("face_landmarker.task"))),
            running_mode=vision.RunningMode.VIDEO,
        ))
        self._guard = TimestampGuard()

    def process(self, frame_bgr: np.ndarray, timestamp_ms: int) -> Observation:
        timestamp_ms = self._guard.next(int(timestamp_ms))
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        hands = self._hands.detect_for_video(image, timestamp_ms)
        face = self._face.detect_for_video(image, timestamp_ms)
        return Observation(
            timestamp_ms,
            tuple(tuple((lm.x, lm.y) for lm in hand) for hand in hands.hand_landmarks),
            bool(face.face_landmarks),
        )

    def close(self) -> None:
        self._hands.close()
        self._face.close()

    def __enter__(self) -> "Tracker":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
