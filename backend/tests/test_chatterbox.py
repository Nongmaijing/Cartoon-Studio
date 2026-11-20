from __future__ import annotations

from pathlib import Path

from app.services import chatterbox_tts


def test_info_lists_reference_voices(tmp_path):
    python = tmp_path / "python.exe"
    worker = tmp_path / "worker.py"
    python.write_text("")
    worker.write_text("")
    voices = tmp_path / "voices"
    voices.mkdir()
    (voices / "narrator_gura.wav").write_bytes(b"RIFF")

    info = chatterbox_tts.info(
        {
            "tts": {
                "chatterbox": {
                    "python": str(python),
                    "worker": str(worker),
                    "voices_dir": str(voices),
                }
            }
        }
    )
    assert info["available"] is True
    assert info["id"] == "chatterbox"
    assert [voice["id"] for voice in info["voices"]] == ["narrator_gura"]


def test_info_reports_missing_install(tmp_path):
    info = chatterbox_tts.info(
        {
            "tts": {
                "chatterbox": {
                    "python": str(tmp_path / "nope.exe"),
                    "worker": str(tmp_path / "nope.py"),
                    "voices_dir": str(tmp_path / "voices"),
                }
            }
        }
    )
    assert info["available"] is False


def test_emotion_controls_cover_dialogue_labels():
    for emotion in ("neutral", "happy", "excited", "sad", "angry", "scared", "surprised", "calm", "whisper"):
        assert emotion in chatterbox_tts.EXAGGERATION
        assert emotion in chatterbox_tts.CFG_WEIGHT
