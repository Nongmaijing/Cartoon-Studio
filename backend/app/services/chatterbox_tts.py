"""Chatterbox TTS integration: humanlike speech and zero-shot voice cloning.

Chatterbox runs in an isolated virtual environment under ``tools/chatterbox`` so
its pinned torch/transformers/numpy versions cannot disturb the main backend.
The model stays loaded in a persistent worker process; this module sends one
JSON request per line and returns the generated WAV path.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from ..config import BASE_DIR, load_config
from ..logging_setup import logger

# Chatterbox's exaggeration control; a cloned narrator sits near 0.4–0.6.
EXAGGERATION = {
    "neutral": 0.50,
    "happy": 0.65,
    "excited": 0.80,
    "sad": 0.35,
    "angry": 0.70,
    "scared": 0.75,
    "surprised": 0.70,
    "calm": 0.30,
    "whisper": 0.25,
}
CFG_WEIGHT = {
    "neutral": 0.50,
    "happy": 0.45,
    "excited": 0.40,
    "sad": 0.55,
    "angry": 0.45,
    "scared": 0.40,
    "surprised": 0.45,
    "calm": 0.55,
    "whisper": 0.60,
}

_PROCESS: asyncio.subprocess.Process | None = None
_LOG_HANDLE: Any = None
_LOCK = asyncio.Lock()


def _settings(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config()
    section = (config.get("tts") or {}).get("chatterbox") or {}
    return {
        "python": Path(
            str(section.get("python") or BASE_DIR / "tools" / "chatterbox" / ".venv" / "Scripts" / "python.exe")
        ),
        "worker": Path(str(section.get("worker") or BASE_DIR / "scripts" / "chatterbox_worker.py")),
        "voices_dir": Path(str(section.get("voices_dir") or BASE_DIR / "tools" / "chatterbox" / "voices")),
        "model": str(section.get("model") or "original"),
        "device": str(section.get("device") or "auto"),
        "timeout": float(section.get("timeout_seconds") or 600),
    }


def info(config: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = _settings(config)
    voices = []
    if settings["voices_dir"].is_dir():
        for path in sorted(settings["voices_dir"].iterdir()):
            if path.suffix.lower() not in {".wav", ".mp3", ".flac", ".m4a", ".ogg"}:
                continue
            voices.append(
                {
                    "id": path.stem,
                    "name": path.stem.replace("_", " ").replace("-", " "),
                    "locale": "",
                    "gender": "",
                    "age": "",
                    "path": str(path),
                }
            )
    available = settings["python"].exists() and settings["worker"].exists()
    return {
        "id": "chatterbox",
        "name": "Chatterbox (voice cloning)",
        "available": available,
        "executable": str(settings["python"]),
        "voices": voices,
        "free_form": False,
        "notes": (
            f"Zero-shot cloning with the '{settings['model']}' model. "
            f"Add 10–20 s reference clips as WAV/MP3 in {settings['voices_dir']}. "
            "Runs in tools/chatterbox; outputs carry a Perth watermark."
            if available
            else "Run the Chatterbox installer to enable humanlike cloned voices."
        ),
    }


async def _stop() -> None:
    global _PROCESS, _LOG_HANDLE
    if _PROCESS and _PROCESS.returncode is None:
        _PROCESS.kill()
        await _PROCESS.wait()
    _PROCESS = None
    if _LOG_HANDLE is not None:
        _LOG_HANDLE.close()
        _LOG_HANDLE = None


async def _read_message(
    process: asyncio.subprocess.Process,
    timeout: float,
    key: str,
) -> dict[str, Any]:
    """Read stdout until a JSON line containing ``key`` arrives.

    Chatterbox and HuggingFace print warnings and progress bars on stdout; they
    must not desynchronise the request/response protocol.
    """
    assert process.stdout is not None
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise asyncio.TimeoutError
        try:
            line = await asyncio.wait_for(process.stdout.readline(), timeout=remaining)
        except asyncio.TimeoutError:
            raise
        if not line:
            raise RuntimeError("Chatterbox worker closed its output stream.")
        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            logger.debug("Chatterbox: %s", text[:300])
            continue
        if isinstance(message, dict) and key in message:
            return message


async def _ensure_process(settings: dict[str, Any]) -> asyncio.subprocess.Process:
    global _PROCESS, _LOG_HANDLE
    if _PROCESS is not None and _PROCESS.returncode is None:
        return _PROCESS
    if not settings["python"].exists():
        raise RuntimeError(
            "Chatterbox is not installed. Run scripts/install_chatterbox.ps1 first."
        )
    log_path = BASE_DIR / "logs" / "chatterbox.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _LOG_HANDLE = open(log_path, "ab")
    env = os.environ.copy()
    env.setdefault("HF_HOME", str(BASE_DIR / "models" / "huggingface"))
    env.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    _PROCESS = await asyncio.create_subprocess_exec(
        str(settings["python"]),
        str(settings["worker"]),
        "--model",
        settings["model"],
        "--device",
        settings["device"],
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=_LOG_HANDLE,
        env=env,
    )
    assert _PROCESS.stdout is not None
    try:
        ready = await _read_message(_PROCESS, 900, "ready")
    except asyncio.TimeoutError as exc:
        await _stop()
        raise RuntimeError("Chatterbox did not finish loading within 900 s.") from exc
    except RuntimeError as exc:
        await _stop()
        raise RuntimeError(f"Chatterbox failed to start: {exc}") from exc
    logger.info(
        "Chatterbox ready: model=%s device=%s sample_rate=%s",
        ready.get("model"),
        ready.get("device"),
        ready.get("sample_rate"),
    )
    return _PROCESS


async def synthesize(
    *,
    text: str,
    out_path: Path,
    voice: str = "",
    emotion: str = "neutral",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = _settings(config)
    reference = None
    if voice:
        candidate = Path(voice)
        if not candidate.exists():
            candidate = settings["voices_dir"] / f"{voice}.wav"
        if not candidate.exists():
            candidate = settings["voices_dir"] / f"{voice}.mp3"
        if candidate.exists():
            reference = str(candidate)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    request = {
        "text": text,
        "out": str(out_path),
        "reference": reference,
        "exaggeration": EXAGGERATION.get(emotion, 0.5),
        "cfg_weight": CFG_WEIGHT.get(emotion, 0.5),
    }

    async with _LOCK:
        process = await _ensure_process(settings)
        assert process.stdin is not None and process.stdout is not None
        try:
            process.stdin.write((json.dumps(request) + "\n").encode("utf-8"))
            await process.stdin.drain()
            response = await _read_message(process, settings["timeout"], "ok")
        except asyncio.TimeoutError as exc:
            await _stop()
            raise RuntimeError(
                f"Chatterbox timed out after {settings['timeout']:.0f} s."
            ) from exc
        except RuntimeError as exc:
            await _stop()
            raise RuntimeError(f"Chatterbox stopped unexpectedly: {exc}") from exc
        if not response.get("ok"):
            logger.error("Chatterbox failed: %s", response.get("traceback") or response.get("error"))
            raise RuntimeError(f"Chatterbox error: {response.get('error')}")
        return {
            "engine": "chatterbox",
            "voice": voice,
            "reference": reference,
            "sample_rate": response.get("sample_rate"),
            "seconds": response.get("seconds"),
        }


async def shutdown() -> None:
    async with _LOCK:
        await _stop()


__all__ = ["info", "synthesize", "shutdown", "EXAGGERATION", "CFG_WEIGHT"]
