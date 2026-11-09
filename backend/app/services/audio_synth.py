from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


def _write_mono(path: Path, samples: list[float], sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    peak = max((abs(value) for value in samples), default=1.0) or 1.0
    scale = 0.78 / peak
    frames = b"".join(
        struct.pack("<h", int(max(-1.0, min(1.0, value * scale)) * 32767))
        for value in samples
    )
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(frames)


def synthesize_music(path: Path, duration: float = 30.0, sample_rate: int = 22050) -> dict:
    """Generate a gentle, original children's music bed locally."""
    total = int(duration * sample_rate)
    buffer = [0.0] * total
    chords = [
        (261.63, 329.63, 392.00),
        (196.00, 246.94, 293.66),
        (220.00, 261.63, 329.63),
        (174.61, 220.00, 261.63),
    ]
    chord_seconds = 4.0
    chord_samples = int(chord_seconds * sample_rate)
    for block in range(0, total, chord_samples):
        chord = chords[(block // chord_samples) % len(chords)]
        end = min(total, block + chord_samples)
        for index in range(block, end):
            t = (index - block) / sample_rate
            env = min(1.0, t / 0.25, (chord_seconds - t) / 0.25)
            value = sum(math.sin(2 * math.pi * freq * t) * 0.050 for freq in chord)
            value += math.sin(2 * math.pi * (chord[0] / 2) * t) * 0.035
            value *= 0.85 + 0.15 * math.sin(2 * math.pi * 0.25 * t)
            buffer[index] += value * max(0.0, env)
    melody = [
        523.25, 659.25, 783.99, 659.25, 880.00, 783.99, 659.25, 587.33,
        523.25, 659.25, 783.99, 880.00, 783.99, 659.25, 587.33, 523.25,
    ]
    note_seconds = 0.5
    note_samples = int(note_seconds * sample_rate)
    for index in range(int(duration / note_seconds) + 1):
        freq = melody[index % len(melody)]
        start = index * note_samples
        end = min(total, start + note_samples)
        for sample_index in range(start, end):
            t = (sample_index - start) / sample_rate
            env = math.exp(-4.2 * t) * min(1.0, t / 0.012)
            value = math.sin(2 * math.pi * freq * t) * 0.070
            value += math.sin(2 * math.pi * freq * 2 * t) * 0.018
            buffer[sample_index] += value * env
    _write_mono(path, buffer, sample_rate)
    return {"kind": "music", "duration_ms": int(duration * 1000), "sample_rate": sample_rate}


def synthesize_sound_effect(path: Path, kind: str = "sparkle", sample_rate: int = 22050) -> dict:
    if kind not in ("sparkle", "chime"):
        kind = "sparkle"
    duration = 1.2
    total = int(duration * sample_rate)
    buffer = [0.0] * total
    for freq in (1200.0, 1800.0, 2400.0, 3200.0):
        for index in range(total):
            t = index / sample_rate
            env = math.exp(-5.5 * t) * min(1.0, t / 0.01)
            buffer[index] += math.sin(2 * math.pi * freq * t) * 0.16 * env
    _write_mono(path, buffer, sample_rate)
    return {"kind": "sfx", "effect": kind, "duration_ms": int(duration * 1000), "sample_rate": sample_rate}
