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


def low() -> np.ndarray:
    # a deep G3; laptop speakers barely play it, so its overtones carry the pitch
    return (_tone(196, 1.2, 0.13, decay=2.5) + _tone(392, 1.2, 0.12, decay=3.0)
            + _tone(588, 1.2, 0.05, decay=4.0))


def _pulse(freq: float, seconds: float, volume: float, harmonics: int = 1) -> np.ndarray:
    """A steady tone that does not fade away, made harsher by odd harmonics (a softened square wave)."""
    t = np.arange(int(RATE * seconds)) / RATE
    envelope = np.minimum(1.0, np.minimum(t, seconds - t) / 0.005)  # 5 ms fades: no clicks
    wave_ = sum(np.sin(2 * np.pi * freq * k * t) / k for k in range(1, 2 * harmonics, 2))
    return volume * envelope * wave_ / np.abs(wave_).max()


def _gap(seconds: float) -> np.ndarray:
    return np.zeros(int(RATE * seconds))


# Harder to ignore than the soft tones above, but still short and not alarm-like.

def buzz() -> np.ndarray:
    pulse = _pulse(160, 0.16, 0.22, harmonics=6)  # like a phone vibrating on a desk
    return np.concatenate([_gap(0.01), pulse, _gap(0.08), pulse, _gap(0.08), pulse])


def beeps() -> np.ndarray:
    beep = _pulse(1800, 0.09, 0.2, harmonics=2)
    return np.concatenate([_gap(0.01), beep, _gap(0.07), beep, _gap(0.07), beep])


def warble() -> np.ndarray:
    notes = [_pulse(960 if i % 2 == 0 else 720, 0.09, 0.2, harmonics=2) for i in range(8)]
    return np.concatenate([_gap(0.01), *notes])


def honk() -> np.ndarray:
    note = _pulse(330, 0.22, 0.24, harmonics=5)
    return np.concatenate([_gap(0.01), note, _gap(0.09), note])


SOUNDS = {"chime": chime, "bell": bell, "knock": knock, "rising": rising, "low": low,
          "buzz": buzz, "beeps": beeps, "warble": warble, "honk": honk}


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
