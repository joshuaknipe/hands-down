# Model files

Downloaded 2026-10-07 from Google's MediaPipe model storage (float16, "latest").
They are committed so builds are reproducible and Hands Down makes no network calls.

| File | Source |
| --- | --- |
| hand_landmarker.task | https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task |
| face_landmarker.task | https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task |

Expected hashes are in `SHA256SUMS`; `tests/test_paths.py` checks them.
