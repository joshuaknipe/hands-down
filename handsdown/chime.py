"""The alert sound: two soft descending tones. Run this module to regenerate assets/chime.wav."""

import wave
from pathlib import Path

import numpy as np

RATE = 44100


def _tone(freq: float, seconds: float, volume: float) -> np.ndarray:
    t = np.arange(int(RATE * seconds)) / RATE
    envelope = np.minimum(1.0, t / 0.01) * np.exp(-t * 6)  # 10 ms fade-in, then a soft decay
    return volume * envelope * np.sin(2 * np.pi * freq * t)


def chime() -> np.ndarray:
    return np.concatenate([_tone(880, 0.35, 0.25), _tone(660, 0.6, 0.25)])


def write_wav(path: Path, samples: np.ndarray) -> None:
    data = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "assets" / "chime.wav"
    out.parent.mkdir(exist_ok=True)
    write_wav(out, chime())
    print(f"Wrote {out}")
