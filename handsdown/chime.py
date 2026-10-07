"""The alert sounds: short, soft generated tones. Run this module to regenerate assets/sounds/."""

import wave
from pathlib import Path

import numpy as np

from handsdown.settings import SOUNDS as SOUND_NAMES
from handsdown.settings import VOLUMES

RATE = 44100
VOLUME_GAINS = {"quiet": 0.35, "medium": 0.65, "normal": 1.0}


def _tone(freq: float, seconds: float, volume: float, decay: float = 6.0) -> np.ndarray:
    t = np.arange(int(RATE * seconds)) / RATE
    envelope = np.minimum(1.0, t / 0.01) * np.exp(-t * decay)  # 10 ms fade-in, then a soft decay
    return volume * envelope * np.sin(2 * np.pi * freq * t)


def chime() -> np.ndarray:
    return np.concatenate([_tone(880, 0.35, 0.25), _tone(660, 0.6, 0.25)])


def bell() -> np.ndarray:
    return _tone(784, 1.2, 0.2, decay=4.0) + _tone(1568, 1.2, 0.06, decay=6.0)


def knock() -> np.ndarray:
    # around 1 kHz so laptop speakers carry it; a lower, shorter tap was nearly inaudible
    tap = _tone(1000, 0.3, 0.24, decay=10.0) + _tone(2000, 0.3, 0.04, decay=20.0)
    return np.concatenate([tap, np.zeros(int(RATE * 0.08)), tap])


def rising() -> np.ndarray:
    return np.concatenate([_tone(660, 0.35, 0.25), _tone(880, 0.6, 0.25)])


SOUNDS = {"chime": chime, "bell": bell, "knock": knock, "rising": rising}


def sound_file(name: str, volume: str) -> str:
    """The sound's path relative to the resource root."""
    return f"assets/sounds/{name}-{volume}.wav"


def write_wav(path: Path, samples: np.ndarray) -> None:
    data = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    (root / "assets" / "sounds").mkdir(parents=True, exist_ok=True)
    for name in SOUND_NAMES:
        for volume in VOLUMES:
            write_wav(root / sound_file(name, volume), SOUNDS[name]() * VOLUME_GAINS[volume])
    print(f"Wrote {len(SOUND_NAMES) * len(VOLUMES)} sounds to {root / 'assets' / 'sounds'}")
