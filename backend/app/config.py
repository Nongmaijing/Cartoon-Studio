from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = BASE_DIR / "config" / "config.json"


def default_config() -> dict[str, Any]:
    """Defaults derived from the actual project location, not a hardcoded drive."""
    return {
        "comfyui": {
            "server_url": "http://127.0.0.1:8188",
            "install_path": "",
            "output_dir": "",
            "models_dirs": [],
            "auto_discover": True,
            "request_timeout_seconds": 120,
        },
        "paths": {
            "workflow_dir": str(BASE_DIR / "workflows"),
            "output_dir": str(BASE_DIR / "outputs"),
            "assets_dir": str(BASE_DIR / "assets"),
            "projects_dir": str(BASE_DIR / "projects"),
            "logs_dir": str(BASE_DIR / "logs"),
            "data_dir": str(BASE_DIR / "data"),
        },
        "generation": {
            "default_workflow": "sd15_txt2img",
            "width": 768,
            "height": 768,
            "steps": 28,
            "cfg": 6.5,
            "sampler": "dpmpp_2m",
            "scheduler": "karras",
            "batch_size": 1,
            "seed": -1,
            "negative_prompt": "photo, photorealistic, 3d render, blurry, low quality, deformed, extra limbs, extra fingers, extra tails, duplicate body parts, floating limbs, malformed paws, bad anatomy, watermark, text, signature, artist signature, logo, initials, monogram, cropped, jpeg artifacts",
            "timeout_seconds": 1800,
            "max_concurrent_jobs": 1,
        },
        "ffmpeg": {"path": ""},
        "tts": {
            "default_engine": "kokoro",
            "default_voice": "",
            "preview_text": "Hello! I am ready for my close-up.",
            "piper_path": "",
            "piper_model_dir": "",
            "kokoro_model": str(BASE_DIR / "tools" / "kokoro" / "kokoro-v1.0.onnx"),
            "kokoro_voices": str(BASE_DIR / "tools" / "kokoro" / "voices-v1.0.bin"),
            "timeout_seconds": 120,
        },
        "server": {"host": "127.0.0.1", "port": 8010},
        "ui": {"poll_interval_ms": 2000},
        "ai": {
            "enabled": True,
            "model": "",
            "base_url": "https://api.openai.com/v1",
            "max_tool_rounds": 8,
            "timeout_seconds": 120,
            "max_context_chars": 60000,
        },
        "mcp": {
            "enabled": False,
            "host": "127.0.0.1",
            "port": 8020,
            "public_url": "",
            "transport": "streamable-http",
            "auth_mode": "bearer",
        },
        "providers": {
            "allow_cloud": False,
            "default_image": "comfyui",
            "default_video": "comfyui",
            "default_audio": "kokoro",
            "default_editing": "ffmpeg",
        },
        "security": {
            "rate_limit_per_minute": 60,
            "require_confirmation": True,
        },
    }


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> dict[str, Any]:
    defaults = default_config()
    if CONFIG_PATH.exists():
        try:
            stored = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return _deep_merge(defaults, stored)
        except (json.JSONDecodeError, OSError):
            # Never crash the app because of a malformed config; keep defaults.
            return defaults
    return defaults


def save_config(config: dict[str, Any]) -> dict[str, Any]:
    merged = _deep_merge(default_config(), config)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_PATH)
    return merged


def ensure_dirs(config: dict[str, Any]) -> None:
    for key in ("workflow_dir", "output_dir", "assets_dir", "projects_dir", "logs_dir", "data_dir"):
        Path(config["paths"][key]).mkdir(parents=True, exist_ok=True)


def path_of(config: dict[str, Any], key: str) -> Path:
    return Path(config["paths"][key])
