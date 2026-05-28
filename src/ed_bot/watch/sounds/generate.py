"""Generate placeholder ed-watch sound files using only stdlib.

Run from this directory:
    python generate.py

Outputs four .wav files. Replace with real CC0 audio when convenient."""
from __future__ import annotations

import math
import pathlib
import struct
import wave

SAMPLE_RATE = 44100


def write_wav(path: pathlib.Path, samples: list[int]) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"".join(struct.pack("<h", s) for s in samples))


def tone(freq: float, duration_s: float, *, wave_shape: str = "sine", amp: float = 0.4) -> list[int]:
    n = int(SAMPLE_RATE * duration_s)
    samples = []
    peak = int(32767 * amp)
    for i in range(n):
        t = i / SAMPLE_RATE
        if wave_shape == "sine":
            v = math.sin(2 * math.pi * freq * t)
        elif wave_shape == "square":
            v = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0
        else:
            raise ValueError(wave_shape)
        # Simple linear fade-in/out to avoid clicks
        fade = min(i, n - i, int(0.01 * SAMPLE_RATE)) / max(int(0.01 * SAMPLE_RATE), 1)
        samples.append(int(peak * v * min(fade, 1.0)))
    return samples


def main():
    here = pathlib.Path(__file__).parent

    # new.wav — single ding (440 Hz, 200 ms)
    write_wav(here / "new.wav", tone(440, 0.20))

    # followup.wav — two ascending tones (523, 659 Hz, 150 ms each)
    write_wav(here / "followup.wav", tone(523, 0.15) + tone(659, 0.15))

    # escalation.wav — three descending squares (880, 659, 440 Hz, 120 ms each)
    write_wav(
        here / "escalation.wav",
        tone(880, 0.12, wave_shape="square")
        + tone(659, 0.12, wave_shape="square")
        + tone(440, 0.12, wave_shape="square"),
    )

    # error.wav — low buzz (220 Hz square, 400 ms)
    write_wav(here / "error.wav", tone(220, 0.40, wave_shape="square"))

    print("Generated 4 .wav files in", here)


if __name__ == "__main__":
    main()
