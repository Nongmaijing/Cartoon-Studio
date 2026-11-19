from __future__ import annotations

import asyncio
import importlib.util
import os
import shutil
import subprocess
import tempfile
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import BASE_DIR, load_config
from ..logging_setup import logger

SAPI_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
  if ($env:CS_TTS_VOICE) { $s.SelectVoice($env:CS_TTS_VOICE) }
  $s.Rate = [int]$env:CS_TTS_RATE
  $s.Volume = [int]$env:CS_TTS_VOLUME
  $text = Get-Content -Raw -Encoding UTF8 $env:CS_TTS_TEXT_FILE
  $s.SetOutputToWaveFile($env:CS_TTS_OUT)
  $pitch = [int]$env:CS_TTS_PITCH
  if ($pitch -ne 0) {
    $escaped = [System.Security.SecurityElement]::Escape($text)
    $ssml = '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US"><prosody pitch="' + $pitch + '%">' + $escaped + '</prosody></speak>'
    try { $s.SpeakSsml($ssml) } catch { $s.Speak($text) }
  } else {
    $s.Speak($text)
  }
} finally {
  $s.Dispose()
}
"""

VOICE_SCRIPT = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.GetInstalledVoices() | ForEach-Object {
  $i = $_.VoiceInfo
  [PSCustomObject]@{
    id = $i.Name
    name = $i.Name
    locale = $i.Culture.Name
    gender = $i.Gender.ToString()
    age = $i.Age.ToString()
  }
} | ConvertTo-Json -Compress
"""

EMOTIONS: dict[str, dict[str, int]] = {
    "neutral": {"rate": 0, "pitch": 0, "volume": 0},
    "happy": {"rate": 1, "pitch": 8, "volume": 3},
    "excited": {"rate": 2, "pitch": 15, "volume": 6},
    "sad": {"rate": -2, "pitch": -10, "volume": -4},
    "angry": {"rate": 1, "pitch": -8, "volume": 10},
    "scared": {"rate": 2, "pitch": 12, "volume": -2},
    "surprised": {"rate": 1, "pitch": 10, "volume": 5},
    "calm": {"rate": -2, "pitch": -3, "volume": -2},
    "whisper": {"rate": -1, "pitch": -5, "volume": -30},
}

KOKORO_VOICES = [
    # US English — female
    {"id": "af_heart", "name": "Heart · warm female", "locale": "en-US", "gender": "Female", "age": "Adult"},
    {"id": "af_bella", "name": "Bella · bright female", "locale": "en-US", "gender": "Female", "age": "Adult"},
    {"id": "af_nicole", "name": "Nicole · soft female", "locale": "en-US", "gender": "Female", "age": "Adult"},
    {"id": "af_alloy", "name": "Alloy · neutral female", "locale": "en-US", "gender": "Female", "age": "Adult"},
    {"id": "af_aoede", "name": "Aoede · expressive female", "locale": "en-US", "gender": "Female", "age": "Adult"},
    {"id": "af_jessica", "name": "Jessica · clear female", "locale": "en-US", "gender": "Female", "age": "Adult"},
    {"id": "af_kore", "name": "Kore · bright female", "locale": "en-US", "gender": "Female", "age": "Young"},
    {"id": "af_nova", "name": "Nova · youthful female", "locale": "en-US", "gender": "Female", "age": "Young"},
    {"id": "af_river", "name": "River · soft female", "locale": "en-US", "gender": "Female", "age": "Young"},
    {"id": "af_sarah", "name": "Sarah · narration female", "locale": "en-US", "gender": "Female", "age": "Adult"},
    {"id": "af_sky", "name": "Sky · youthful female", "locale": "en-US", "gender": "Female", "age": "Young"},
    # US English — male
    {"id": "am_michael", "name": "Michael · friendly male", "locale": "en-US", "gender": "Male", "age": "Adult"},
    {"id": "am_fenrir", "name": "Fenrir · warm male", "locale": "en-US", "gender": "Male", "age": "Adult"},
    {"id": "am_adam", "name": "Adam · deep male", "locale": "en-US", "gender": "Male", "age": "Adult"},
    {"id": "am_echo", "name": "Echo · neutral male", "locale": "en-US", "gender": "Male", "age": "Adult"},
    {"id": "am_eric", "name": "Eric · friendly male", "locale": "en-US", "gender": "Male", "age": "Adult"},
    {"id": "am_liam", "name": "Liam · young male", "locale": "en-US", "gender": "Male", "age": "Young"},
    {"id": "am_onyx", "name": "Onyx · deep male", "locale": "en-US", "gender": "Male", "age": "Adult"},
    {"id": "am_puck", "name": "Puck · playful male", "locale": "en-US", "gender": "Male", "age": "Young"},
    {"id": "am_santa", "name": "Santa · older male", "locale": "en-US", "gender": "Male", "age": "Senior"},
    # British English — female
    {"id": "bf_emma", "name": "Emma · British female", "locale": "en-GB", "gender": "Female", "age": "Adult"},
    {"id": "bf_isabella", "name": "Isabella · British female", "locale": "en-GB", "gender": "Female", "age": "Adult"},
    {"id": "bf_alice", "name": "Alice · British female", "locale": "en-GB", "gender": "Female", "age": "Adult"},
    {"id": "bf_lily", "name": "Lily · youthful British female", "locale": "en-GB", "gender": "Female", "age": "Young"},
    # British English — male
    {"id": "bm_george", "name": "George · British male", "locale": "en-GB", "gender": "Male", "age": "Adult"},
    {"id": "bm_fable", "name": "Fable · British male", "locale": "en-GB", "gender": "Male", "age": "Adult"},
    {"id": "bm_daniel", "name": "Daniel · British male", "locale": "en-GB", "gender": "Male", "age": "Adult"},
    {"id": "bm_lewis", "name": "Lewis · British male", "locale": "en-GB", "gender": "Male", "age": "Adult"},
]


class TTSError(RuntimeError):
    pass


_cache: dict[str, Any] | None = None
_cache_at: datetime | None = None
_cache_lock = asyncio.Lock()
_synth_lock = asyncio.Lock()
_kokoro_model: Any = None
_kokoro_paths: tuple[str, str] | None = None
_kokoro_load_lock = asyncio.Lock()


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _semitones(pitch: int) -> float:
    """Map the UI pitch percentage to semitones (100% == one octave)."""
    return _clamp(pitch, -100, 100) * 0.12


async def _shift_pitch(path: Path, semitones: float, timeout: float) -> None:
    """Shift pitch without changing duration.

    Neural engines such as Kokoro and Piper have fixed adult voices. Resampling
    the output up a few semitones raises both pitch and formants, which is what
    makes a young/adult voice read as a child.
    """
    if abs(semitones) < 0.15:
        return
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.warning("ffmpeg is not on PATH; pitch adjustment skipped")
        return
    try:
        with wave.open(str(path), "rb") as handle:
            sample_rate = handle.getframerate()
            channels = handle.getnchannels()
    except (OSError, wave.Error) as exc:
        logger.warning("Could not read %s for pitch shift: %s", path, exc)
        return
    ratio = 2 ** (semitones / 12.0)
    shifted = path.with_name(f"{path.stem}_pitch{path.suffix}")
    filters = (
        f"asetrate={sample_rate * ratio:.3f},aresample={sample_rate},"
        f"atempo={1.0 / ratio:.6f}"
    )
    code, _, stderr = await _run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-filter:a",
            filters,
            "-ac",
            str(channels),
            "-c:a",
            "pcm_s16le",
            str(shifted),
        ],
        timeout=timeout,
    )
    if code != 0 or not shifted.exists():
        logger.warning("Pitch shift failed: %s", _decode(stderr)[:200])
        shifted.unlink(missing_ok=True)
        return
    shifted.replace(path)


def _powershell() -> str | None:
    return shutil.which("powershell") or shutil.which("pwsh")


def _creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


async def _run(
    cmd: list[str],
    *,
    timeout: float,
    env: dict[str, str] | None = None,
    stdin: bytes | None = None,
) -> tuple[int, bytes, bytes]:
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        creationflags=_creation_flags(),
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(stdin), timeout=timeout)
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.wait()
        raise TTSError("Speech synthesis timed out.") from exc
    return process.returncode or 0, stdout, stderr


def _decode(value: bytes) -> str:
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return value.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return value.decode("utf-8", errors="replace").strip()


async def _sapi_voices() -> list[dict[str, str]]:
    ps = _powershell()
    if not ps:
        return []
    try:
        code, stdout, stderr = await _run(
            [ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", VOICE_SCRIPT],
            timeout=15,
        )
    except (OSError, TTSError) as exc:
        logger.warning("SAPI voice discovery failed: %s", exc)
        return []
    if code != 0:
        logger.warning("SAPI voice discovery exited %s: %s", code, _decode(stderr)[:300])
        return []
    payload = _decode(stdout)
    if not payload:
        return []
    import json

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        parsed = [parsed]
    voices: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        voices.append(
            {
                "id": str(item.get("id") or item.get("name") or ""),
                "name": str(item.get("name") or item.get("id") or ""),
                "locale": str(item.get("locale") or ""),
                "gender": str(item.get("gender") or ""),
                "age": str(item.get("age") or ""),
            }
        )
    return [voice for voice in voices if voice["id"]]


def _piper_info(config: dict[str, Any]) -> tuple[str, list[Path]]:
    tts = config.get("tts") or {}
    exe = str(tts.get("piper_path") or "").strip() or shutil.which("piper") or shutil.which("piper.exe") or ""
    models: list[Path] = []
    if exe:
        candidates = []
        model_dir = str(tts.get("piper_model_dir") or "").strip()
        if model_dir:
            candidates.append(Path(model_dir))
        exe_path = Path(exe)
        candidates.extend([exe_path.parent, exe_path.parent / "voices"])
        seen: set[str] = set()
        for directory in candidates:
            key = str(directory).lower()
            if key in seen or not directory.exists():
                continue
            seen.add(key)
            models.extend(sorted(directory.glob("*.onnx")))
    return exe, models


def _kokoro_info(config: dict[str, Any]) -> tuple[str, str, bool]:
    tts = config.get("tts") or {}
    model = str(tts.get("kokoro_model") or "").strip() or str(
        BASE_DIR / "tools" / "kokoro" / "kokoro-v1.0.onnx"
    )
    voices = str(tts.get("kokoro_voices") or "").strip() or str(
        BASE_DIR / "tools" / "kokoro" / "voices-v1.0.bin"
    )
    available = (
        Path(model).exists()
        and Path(voices).exists()
        and importlib.util.find_spec("kokoro_onnx") is not None
    )
    return model, voices, available


async def _load_kokoro(model_path: str, voices_path: str) -> Any:
    global _kokoro_model, _kokoro_paths
    async with _kokoro_load_lock:
        if _kokoro_model is None or _kokoro_paths != (model_path, voices_path):
            from kokoro_onnx import Kokoro

            _kokoro_model = await asyncio.to_thread(Kokoro, model_path, voices_path)
            _kokoro_paths = (model_path, voices_path)
            logger.info("Kokoro TTS model loaded from %s", model_path)
    return _kokoro_model


def _espeak_path() -> str:
    return shutil.which("espeak-ng") or shutil.which("espeak") or ""


async def detect_engines(config: dict[str, Any] | None = None, refresh: bool = False) -> dict[str, Any]:
    global _cache, _cache_at
    config = config or load_config()
    now = datetime.now(timezone.utc)
    async with _cache_lock:
        if (
            not refresh
            and _cache is not None
            and _cache_at is not None
            and (now - _cache_at).total_seconds() < 60
        ):
            return _cache

    engines: list[dict[str, Any]] = []

    kokoro_model, kokoro_voices, kokoro_available = _kokoro_info(config)
    engines.append(
        {
            "id": "kokoro",
            "name": "Kokoro-82M",
            "available": kokoro_available,
            "executable": kokoro_model,
            "voices": KOKORO_VOICES,
            "free_form": False,
            "notes": (
                "Local neural TTS with natural narration and multiple voices. Runs on the CPU."
                if kokoro_available
                else "Install kokoro-onnx and place kokoro-v1.0.onnx + voices-v1.0.bin in tools/kokoro."
            ),
        }
    )

    sapi_voices = await _sapi_voices()
    ps = _powershell()
    engines.append(
        {
            "id": "sapi",
            "name": "Windows SAPI",
            "available": bool(sapi_voices),
            "executable": ps or "",
            "voices": sapi_voices,
            "free_form": False,
            "notes": (
                "Built into Windows. Voices are read from System.Speech; no download is required."
                if sapi_voices
                else "No Windows SAPI voices were found on this machine."
            ),
        }
    )

    piper_exe, piper_models = _piper_info(config)
    piper_voices = [
        {
            "id": model.stem,
            "name": model.stem.replace("_", " "),
            "locale": "",
            "gender": "",
            "age": "",
            "path": str(model),
        }
        for model in piper_models
    ]
    engines.append(
        {
            "id": "piper",
            "name": "Piper",
            "available": bool(piper_exe and piper_voices),
            "executable": piper_exe,
            "voices": piper_voices,
            "free_form": False,
            "notes": (
                "Piper is installed and voice models are available."
                if piper_exe and piper_voices
                else "Install Piper and point Settings at a folder containing .onnx voice models."
            ),
        }
    )

    coqui_exe = shutil.which("tts") or shutil.which("tts.exe") or ""
    engines.append(
        {
            "id": "coqui",
            "name": "Coqui TTS",
            "available": bool(coqui_exe),
            "executable": coqui_exe,
            "voices": [],
            "free_form": True,
            "notes": (
                "Coqui TTS is installed. Enter a model name or leave it empty for the default voice."
                if coqui_exe
                else "Install Coqui TTS (the 'tts' command) to use it."
            ),
        }
    )

    espeak_exe = _espeak_path()
    engines.append(
        {
            "id": "espeak",
            "name": "eSpeak NG",
            "available": bool(espeak_exe),
            "executable": espeak_exe,
            "voices": [],
            "free_form": True,
            "notes": (
                "eSpeak NG is installed. Enter a voice code such as en-us, or leave it empty."
                if espeak_exe
                else "Install eSpeak NG to use it."
            ),
        }
    )

    tts = config.get("tts") or {}
    preferred = str(tts.get("default_engine") or "sapi")
    available = [engine for engine in engines if engine["available"]]
    default_engine = next((engine for engine in available if engine["id"] == preferred), None)
    if default_engine is None and available:
        default_engine = available[0]
    default_engine_id = default_engine["id"] if default_engine else ""
    preferred_voice = str(tts.get("default_voice") or "")
    default_voice = ""
    if default_engine:
        voice_ids = [voice["id"] for voice in default_engine["voices"]]
        default_voice = preferred_voice if preferred_voice in voice_ids else (voice_ids[0] if voice_ids else "")

    result = {
        "engines": engines,
        "default_engine": default_engine_id,
        "default_voice": default_voice,
        "detected_at": now.isoformat(),
    }
    async with _cache_lock:
        _cache = result
        _cache_at = now
    return result


async def resolve_voice(
    config: dict[str, Any],
    engine: str | None,
    voice: str | None,
    *,
    refresh: bool = False,
) -> tuple[str, str]:
    info = await detect_engines(config, refresh=refresh)
    engines = {item["id"]: item for item in info["engines"]}
    engine_id = str(engine or "").strip() or info["default_engine"]
    selected = engines.get(engine_id)
    if not selected or not selected["available"]:
        engine_id = info["default_engine"]
        selected = engines.get(engine_id)
    if not selected:
        raise TTSError("No local text-to-speech engine is available.")
    voice_id = str(voice or "").strip()
    voice_ids = [item["id"] for item in selected["voices"]]
    if not voice_id or (not selected["free_form"] and voice_id not in voice_ids):
        if engine_id == info["default_engine"] and info["default_voice"]:
            voice_id = info["default_voice"]
        elif voice_ids:
            voice_id = voice_ids[0]
        else:
            voice_id = ""
    return engine_id, voice_id


def emotion_offsets(emotion: str | None) -> dict[str, int]:
    return EMOTIONS.get(str(emotion or "neutral").lower(), EMOTIONS["neutral"])


async def _sapi_synth(
    text: str,
    voice: str,
    rate: int,
    pitch: int,
    volume: int,
    out_path: Path,
    timeout: float,
) -> None:
    ps = _powershell()
    if not ps:
        raise TTSError("PowerShell is not available, so Windows SAPI cannot be used.")
    with tempfile.TemporaryDirectory(prefix="cartoon_studio_tts_") as tmp:
        tmpdir = Path(tmp)
        text_file = tmpdir / "text.txt"
        script_file = tmpdir / "synth.ps1"
        text_file.write_text(text, encoding="utf-8")
        script_file.write_text(SAPI_SCRIPT, encoding="utf-8")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(
            {
                "CS_TTS_VOICE": voice,
                "CS_TTS_RATE": str(_clamp(rate, -10, 10)),
                "CS_TTS_PITCH": str(_clamp(pitch, -100, 100)),
                "CS_TTS_VOLUME": str(_clamp(volume, 0, 100)),
                "CS_TTS_TEXT_FILE": str(text_file),
                "CS_TTS_OUT": str(out_path),
            }
        )
        code, _, stderr = await _run(
            [ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script_file)],
            timeout=timeout,
            env=env,
        )
        if code != 0:
            raise TTSError(f"Windows SAPI failed: {_decode(stderr)[:400] or 'unknown error'}")


def _piper_model(config: dict[str, Any], voice: str) -> Path:
    _, models = _piper_info(config)
    for model in models:
        if model.stem == voice or model.name == voice:
            return model
    if models:
        return models[0]
    raise TTSError("No Piper voice model is available. Set the Piper model folder in Settings.")


async def _piper_synth(
    config: dict[str, Any],
    text: str,
    voice: str,
    rate: int,
    pitch: int,
    volume: int,
    out_path: Path,
    timeout: float,
) -> None:
    exe, _ = _piper_info(config)
    if not exe:
        raise TTSError("Piper is not installed.")
    model = _piper_model(config, voice)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    length_scale = 1.0 + (-rate) * 0.05
    code, _, stderr = await _run(
        [
            exe,
            "--model",
            str(model),
            "--output_file",
            str(out_path),
            "--length_scale",
            f"{length_scale:.2f}",
        ],
        timeout=timeout,
        stdin=text.encode("utf-8"),
    )
    if code != 0:
        raise TTSError(f"Piper failed: {_decode(stderr)[:400] or 'unknown error'}")
    if pitch:
        await _shift_pitch(out_path, _semitones(pitch), timeout)


async def _coqui_synth(
    text: str,
    voice: str,
    rate: int,
    pitch: int,
    volume: int,
    out_path: Path,
    timeout: float,
) -> None:
    exe = shutil.which("tts") or shutil.which("tts.exe")
    if not exe:
        raise TTSError("Coqui TTS is not installed.")
    with tempfile.TemporaryDirectory(prefix="cartoon_studio_tts_") as tmp:
        text_file = Path(tmp) / "text.txt"
        text_file.write_text(text, encoding="utf-8")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [exe, "--text_file", str(text_file), "--out_path", str(out_path)]
        if voice:
            cmd.extend(["--model_name", voice])
        if rate:
            cmd.extend(["--speed", f"{1.0 + rate * 0.05:.2f}"])
        code, _, stderr = await _run(cmd, timeout=timeout)
        if code != 0:
            raise TTSError(f"Coqui TTS failed: {_decode(stderr)[:400] or 'unknown error'}")


async def _espeak_synth(
    text: str,
    voice: str,
    rate: int,
    pitch: int,
    volume: int,
    out_path: Path,
    timeout: float,
) -> None:
    exe = _espeak_path()
    if not exe:
        raise TTSError("eSpeak NG is not installed.")
    with tempfile.TemporaryDirectory(prefix="cartoon_studio_tts_") as tmp:
        text_file = Path(tmp) / "text.txt"
        text_file.write_text(text, encoding="utf-8")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        speed = _clamp(175 + rate * 15, 80, 320)
        pitch_value = _clamp(50 + round(pitch * 0.5), 0, 99)
        cmd = [
            exe,
            "-w",
            str(out_path),
            "-s",
            str(speed),
            "-p",
            str(pitch_value),
            "-a",
            str(_clamp(volume, 0, 200)),
            "-f",
            str(text_file),
        ]
        if voice:
            cmd.extend(["-v", voice])
        code, _, stderr = await _run(cmd, timeout=timeout)
        if code != 0:
            raise TTSError(f"eSpeak NG failed: {_decode(stderr)[:400] or 'unknown error'}")


async def _kokoro_synth(
    config: dict[str, Any],
    text: str,
    voice: str,
    rate: int,
    pitch: int,
    volume: int,
    out_path: Path,
    timeout: float,
) -> None:
    model_path, voices_path, available = _kokoro_info(config)
    if not available:
        raise TTSError(
            "Kokoro TTS is not available. Install kokoro-onnx and the model files in tools/kokoro."
        )
    kokoro = await _load_kokoro(model_path, voices_path)
    voice_id = voice or "af_heart"
    speed = max(0.6, min(1.4, 1.0 + rate * 0.04))
    lang = "en-gb" if voice_id.startswith(("bf_", "bm_")) else "en-us"
    samples, sample_rate = await asyncio.to_thread(
        kokoro.create, text, voice=voice_id, speed=speed, lang=lang
    )
    import numpy as np

    audio = np.asarray(samples, dtype=np.float32)
    if volume != 100:
        audio = audio * max(0.0, min(1.0, volume / 100.0))
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    if pitch:
        await _shift_pitch(out_path, _semitones(pitch), timeout)


async def synthesize(
    *,
    text: str,
    out_path: Path,
    engine: str | None = None,
    voice: str | None = None,
    rate: int = 0,
    pitch: int = 0,
    volume: int = 100,
    emotion: str = "neutral",
    config: dict[str, Any] | None = None,
    refresh_engines: bool = False,
) -> dict[str, Any]:
    """Synthesize speech to a WAV file and return the resolved voice settings."""
    config = config or load_config()
    text = text.strip()
    if not text:
        raise TTSError("Dialogue text is empty.")
    engine_id, voice_id = await resolve_voice(config, engine, voice, refresh=refresh_engines)
    offsets = emotion_offsets(emotion)
    effective_rate = _clamp(rate + offsets["rate"], -10, 10)
    effective_pitch = _clamp(pitch + offsets["pitch"], -100, 100)
    effective_volume = _clamp(volume + offsets["volume"], 0, 100)
    timeout = float((config.get("tts") or {}).get("timeout_seconds", 120))

    async with _synth_lock:
        if engine_id == "sapi":
            await _sapi_synth(
                text, voice_id, effective_rate, effective_pitch, effective_volume, out_path, timeout
            )
        elif engine_id == "piper":
            await _piper_synth(
                config, text, voice_id, effective_rate, effective_pitch, effective_volume, out_path, timeout
            )
        elif engine_id == "coqui":
            await _coqui_synth(
                text, voice_id, effective_rate, effective_pitch, effective_volume, out_path, timeout
            )
        elif engine_id == "espeak":
            await _espeak_synth(
                text, voice_id, effective_rate, effective_pitch, effective_volume, out_path, timeout
            )
        elif engine_id == "kokoro":
            await _kokoro_synth(
                config, text, voice_id, effective_rate, effective_pitch, effective_volume, out_path, timeout
            )
        else:
            raise TTSError(f"Unsupported TTS engine '{engine_id}'.")

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise TTSError("The speech engine did not produce an audio file.")
    logger.info(
        "TTS synthesized %s chars with %s/%s (emotion=%s)",
        len(text),
        engine_id,
        voice_id,
        emotion,
    )
    return {
        "engine": engine_id,
        "voice": voice_id,
        "rate": effective_rate,
        "pitch": effective_pitch,
        "volume": effective_volume,
        "base_rate": _clamp(rate, -10, 10),
        "base_pitch": _clamp(pitch, -100, 100),
        "base_volume": _clamp(volume, 0, 100),
        "emotion": emotion,
    }


def wav_duration_ms(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate() or 1
            return int(round(frames * 1000 / rate))
    except (wave.Error, OSError):
        return 0
