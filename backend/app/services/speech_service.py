from __future__ import annotations

import asyncio
import importlib.util
import os
from pathlib import Path
from typing import Any

from ..config import BASE_DIR
from .assets import asset_file, get_asset

_MODEL_CACHE: dict[str, Any] = {}


def model_dir() -> Path:
    override = os.environ.get("WHISPER_MODEL_DIR")
    if override:
        return Path(override)
    return Path(BASE_DIR) / "models" / "asr" / "faster-whisper-small"


def availability() -> dict[str, Any]:
    package = importlib.util.find_spec("faster_whisper") is not None
    directory = model_dir()
    model_present = (directory / "model.bin").exists() and (directory / "config.json").exists()
    return {
        "available": package and model_present,
        "package_installed": package,
        "model_installed": model_present,
        "model_path": str(directory),
        "model_name": directory.name,
        "device": os.environ.get("WHISPER_DEVICE", "cpu"),
        "compute_type": os.environ.get("WHISPER_COMPUTE_TYPE", "int8"),
    }


def _load_model():
    status = availability()
    if not status["package_installed"]:
        raise ValueError("faster-whisper is not installed.")
    if not status["model_installed"]:
        raise ValueError(f"No faster-whisper model at {status['model_path']}.")
    key = f"{status['model_path']}|{status['device']}|{status['compute_type']}"
    if key not in _MODEL_CACHE:
        from faster_whisper import WhisperModel

        _MODEL_CACHE[key] = WhisperModel(
            status["model_path"],
            device=status["device"],
            compute_type=status["compute_type"],
        )
    return _MODEL_CACHE[key]


def to_srt(segments: list[dict[str, Any]]) -> str:
    def stamp(seconds: float) -> str:
        millis = int(round(max(0.0, seconds) * 1000))
        hours, rem = divmod(millis, 3_600_000)
        minutes, rem = divmod(rem, 60_000)
        secs, ms = divmod(rem, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"

    lines: list[str] = []
    for index, segment in enumerate(segments, start=1):
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        lines.append(str(index))
        lines.append(f"{stamp(segment['start'])} --> {stamp(segment['end'])}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).strip() + ("\n" if lines else "")


def _transcribe_sync(path: Path, language: str | None, vad: bool) -> dict[str, Any]:
    model = _load_model()
    segments_iter, info = model.transcribe(
        str(path),
        language=language or None,
        vad_filter=vad,
        beam_size=5,
    )
    segments: list[dict[str, Any]] = []
    parts: list[str] = []
    for segment in segments_iter:
        text = str(segment.text or "").strip()
        segments.append(
            {
                "start": round(float(segment.start), 3),
                "end": round(float(segment.end), 3),
                "text": text,
            }
        )
        if text:
            parts.append(text)
    status = availability()
    return {
        "text": " ".join(parts).strip(),
        "language": getattr(info, "language", None) or language,
        "language_probability": round(float(getattr(info, "language_probability", 0.0) or 0.0), 4),
        "duration": round(float(getattr(info, "duration", 0.0) or 0.0), 3),
        "segments": segments,
        "model": status["model_name"],
        "provider": "faster-whisper",
        "device": status["device"],
        "compute_type": status["compute_type"],
    }


async def transcribe_asset(
    asset_id: str,
    *,
    language: str | None = None,
    vad: bool = True,
    include_srt: bool = True,
) -> dict[str, Any]:
    asset = get_asset(asset_id)
    if not asset:
        raise ValueError("Asset not found.")
    kind = str(asset.get("kind") or "")
    mime = str(asset.get("mime") or "")
    if kind not in ("audio", "voice") and not mime.startswith("audio/"):
        raise ValueError("Only audio assets can be transcribed.")
    resolved = asset_file(asset_id)
    if not resolved:
        raise ValueError("Asset file was not found on disk.")
    path, _ = resolved
    result = await asyncio.to_thread(_transcribe_sync, path, language, vad)
    result["asset_id"] = asset_id
    result["project_id"] = asset.get("project_id")
    result["source_filename"] = asset.get("filename")
    if include_srt:
        result["srt"] = to_srt(result["segments"])
    return result
