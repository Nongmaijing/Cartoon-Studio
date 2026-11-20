from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import numpy as np


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


def _write_mono_np(path: Path, samples: np.ndarray, sample_rate: int, peak: float = 0.72) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    maximum = float(np.max(np.abs(samples))) or 1.0
    audio = np.clip(samples / maximum * peak, -1.0, 1.0)
    pcm = (audio * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def _shaped_noise(length: int, sample_rate: int, shape, rng: np.random.Generator) -> np.ndarray:
    white = rng.standard_normal(length)
    spectrum = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(length, 1.0 / sample_rate)
    spectrum *= shape(freqs)
    out = np.fft.irfft(spectrum, length)
    peak = float(np.max(np.abs(out))) or 1.0
    return out / peak


def _add_chirp(buffer: np.ndarray, sample_rate: int, start: int, seconds: float, f0: float, f1: float, gain: float) -> None:
    length = max(8, int(seconds * sample_rate))
    if start + length >= buffer.size:
        return
    t = np.arange(length) / sample_rate
    freq = f0 + (f1 - f0) * (t / seconds)
    phase = 2.0 * np.pi * np.cumsum(freq) / sample_rate
    envelope = np.sin(np.pi * t / seconds) ** 2
    buffer[start : start + length] += np.sin(phase) * envelope * gain


def synthesize_ambience(
    path: Path,
    kind: str = "birds",
    duration: float = 30.0,
    sample_rate: int = 24000,
) -> dict:
    """Generate an original ambience bed (birds, wind, rain, stream, fire)."""
    n = max(1, int(duration * sample_rate))
    t = np.arange(n) / sample_rate
    rng = np.random.default_rng(20261120)
    if kind == "wind":
        base = _shaped_noise(n, sample_rate, lambda f: 1.0 / (1.0 + (f / 180.0) ** 2), rng)
        audio = base * (0.55 + 0.45 * np.sin(2 * np.pi * 0.07 * t + 0.6)) * 0.60
    elif kind == "rain":
        base = _shaped_noise(n, sample_rate, lambda f: 0.25 + 0.75 * np.clip(f / 9000.0, 0.0, 1.0), rng)
        audio = base * 0.55
        for _ in range(max(8, int(duration * 8))):
            start = int(rng.integers(0, max(1, n - 800)))
            length = max(8, int(0.02 * sample_rate))
            env = np.exp(-np.arange(length) / (0.004 * sample_rate))
            audio[start : start + length] += rng.standard_normal(length) * env * 0.30
    elif kind == "stream":
        base = _shaped_noise(
            n,
            sample_rate,
            lambda f: np.exp(-((f - 1400.0) / 900.0) ** 2) + 0.25 * np.exp(-((f - 3200.0) / 1200.0) ** 2),
            rng,
        )
        audio = base * 0.65
        for _ in range(max(4, int(duration * 1.8))):
            start = int(rng.integers(0, max(1, n - int(0.25 * sample_rate))))
            _add_chirp(audio, sample_rate, start, 0.08, rng.uniform(600, 900), rng.uniform(400, 700), 0.02)
    elif kind == "birds":
        audio = _shaped_noise(n, sample_rate, lambda f: 1.0 / (1.0 + (f / 400.0) ** 2), rng) * 0.18
        for _ in range(max(8, int(duration * 0.45))):
            start = int(rng.integers(0, max(1, n - int(0.4 * sample_rate))))
            f0 = float(rng.uniform(1900, 2700))
            _add_chirp(audio, sample_rate, start, float(rng.uniform(0.06, 0.16)), f0, f0 * float(rng.uniform(1.15, 1.7)), 0.10)
            if rng.random() < 0.5:
                _add_chirp(audio, sample_rate, start + int(0.18 * sample_rate), 0.08, f0 * 1.1, f0 * 0.9, 0.06)
    elif kind == "fire":
        audio = _shaped_noise(n, sample_rate, lambda f: 1.0 / (1.0 + (f / 300.0) ** 2), rng) * 0.25
        for _ in range(max(10, int(duration * 12))):
            start = int(rng.integers(0, max(1, n - 500)))
            length = max(4, int(rng.uniform(0.004, 0.02) * sample_rate))
            audio[start : start + length] += rng.standard_normal(length) * rng.uniform(0.1, 0.35)
    else:
        raise ValueError(f"Unknown ambience kind '{kind}'.")
    _write_mono_np(path, audio, sample_rate, peak=0.55)
    return {
        "kind": "ambience",
        "effect": kind,
        "duration_ms": int(duration * 1000),
        "sample_rate": sample_rate,
    }


def synthesize_ambient_music(
    path: Path,
    duration: float = 64.0,
    sample_rate: int = 24000,
) -> dict:
    """Generate a slow, wordless ambient score for lifestyle episodes."""
    n = max(1, int(duration * sample_rate))
    t = np.arange(n) / sample_rate
    buffer = np.zeros(n, dtype=np.float64)
    chords = [
        (130.81, 164.81, 196.00, 246.94),  # Cmaj7
        (110.00, 130.81, 164.81, 196.00),  # Am7
        (87.31, 110.00, 130.81, 174.61),   # Fmaj7
        (98.00, 123.47, 146.83, 196.00),   # G
    ]
    block_seconds = 8.0
    block = int(block_seconds * sample_rate)
    for index in range(0, n, block):
        end = min(n, index + block)
        local = (np.arange(end - index)) / sample_rate
        chord = chords[(index // block) % len(chords)]
        envelope = np.minimum(1.0, local / 2.0) * np.minimum(1.0, (block_seconds - local) / 2.0)
        envelope = np.clip(envelope, 0.0, 1.0)
        pad = np.zeros(end - index, dtype=np.float64)
        for freq in chord:
            pad += np.sin(2 * np.pi * freq * local) * 0.040
            pad += np.sin(2 * np.pi * freq * 1.003 * local) * 0.020
        pad += np.sin(2 * np.pi * chord[0] / 2.0 * local) * 0.030
        buffer[index:end] += pad * envelope
    # A very quiet high shimmer keeps the bed from sounding like a test tone.
    buffer += np.sin(2 * np.pi * 1046.5 * t) * (0.004 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.03 * t)))
    _write_mono_np(path, buffer, sample_rate, peak=0.55)
    return {"kind": "music", "duration_ms": int(duration * 1000), "sample_rate": sample_rate}
