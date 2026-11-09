from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter

from ..config import _deep_merge, default_config, ensure_dirs, load_config, save_config
from ..schemas import SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _payload() -> dict:
    config = load_config()
    return {
        "config": config,
        "defaults": default_config(),
        "ffmpeg_detected": shutil.which("ffmpeg") or "",
        "paths_exist": {
            key: Path(value).exists()
            for key, value in (config.get("paths") or {}).items()
            if isinstance(value, str)
        },
    }


@router.get("")
async def get_settings() -> dict:
    return _payload()


@router.put("")
async def update_settings(payload: SettingsUpdate) -> dict:
    current = load_config()
    changes = payload.model_dump(exclude_none=True)
    merged = _deep_merge(current, changes)

    server_url = (merged.get("comfyui") or {}).get("server_url", "")
    if not server_url.startswith(("http://", "https://")):
        raise ValueError("ComfyUI server URL must start with http:// or https://.")

    saved = save_config(merged)
    ensure_dirs(saved)
    return _payload()
