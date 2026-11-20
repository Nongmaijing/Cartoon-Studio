from __future__ import annotations

from app.services.episode_export import meta_cues


def test_transcript_cues_are_offset_and_clamped():
    meta = {
        "cues": [
            {"start_ms": 0, "end_ms": 2000, "text": "First line."},
            {"start_ms": 2000, "end_ms": 4500, "text": "Second line."},
        ]
    }
    cues = meta_cues(meta, 10_000, 13_000)
    assert cues == [
        (10_000, 12_000, "First line."),
        (12_000, 13_000, "Second line."),
    ]


def test_transcript_cues_within_total():
    meta = {
        "cues": [
            {"start_ms": 0, "end_ms": 1000, "text": "A."},
            {"start_ms": 1000, "end_ms": 2000, "text": "B."},
        ]
    }
    assert meta_cues(meta, 0, 5000) == [(0, 1000, "A."), (1000, 2000, "B.")]


def test_falls_back_to_single_text_cue():
    assert meta_cues({"text": "One line.", "duration_ms": 1500}, 500, 5000) == [
        (500, 2000, "One line.")
    ]


def test_empty_meta_returns_nothing():
    assert meta_cues({}, 0, 5000) == []
