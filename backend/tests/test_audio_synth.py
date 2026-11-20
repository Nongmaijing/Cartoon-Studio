from __future__ import annotations

import wave

from app.services.audio_synth import synthesize_ambience, synthesize_ambient_music


def _stats(path) -> tuple[int, int]:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        raw = handle.readframes(frames)
    peak = max((abs(int.from_bytes(raw[i : i + 2], "little", signed=True)) for i in range(0, len(raw), 2)), default=0)
    return frames, peak


def test_ambience_beds_are_audible(tmp_path):
    for kind in ("birds", "wind", "rain", "stream", "fire"):
        path = tmp_path / f"{kind}.wav"
        result = synthesize_ambience(path, kind, 1.0, 16000)
        assert result["effect"] == kind
        frames, peak = _stats(path)
        assert frames == 16000
        assert peak > 1000


def test_ambient_score_is_audible(tmp_path):
    path = tmp_path / "score.wav"
    result = synthesize_ambient_music(path, 2.0, 16000)
    assert result["kind"] == "music"
    frames, peak = _stats(path)
    assert frames == 32000
    assert peak > 1000
