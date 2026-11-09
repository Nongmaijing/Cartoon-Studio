from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from ..db import query_one
from ..providers.registry import registry
from .assets import store_asset_from_path
from .audit_service import log
from .errors import NotFoundError, ServiceError


async def generate_sfx(project_id: str, kind: str = "sparkle", actor: str = "user") -> dict[str, Any]:
    if not query_one("SELECT id FROM projects WHERE id = ?", (project_id,)):
        raise NotFoundError("Project not found.")
    provider = registry.get("audio")
    with tempfile.TemporaryDirectory(prefix="cartoon_studio_sfx_") as tmp:
        path = Path(tmp) / f"sfx_{kind}.wav"
        result = await provider.generate_sound_effect(out_path=path, kind=kind)
        asset = store_asset_from_path(
            project_id=project_id,
            subdir="audio",
            filename=f"sfx_{kind}.wav",
            source_path=path,
            kind="audio",
            mime="audio/wav",
            meta={"kind": "sfx", "effect": kind, "duration_ms": result.get("duration_ms"), "provider": "kokoro"},
        )
    log(actor, "generate_sound_effect", "project", project_id, {"asset_id": asset["id"], "kind": kind})
    return {"asset": asset, "asset_id": asset["id"], "provider": result.get("provider")}


async def generate_music(project_id: str, duration: float = 30.0, actor: str = "user") -> dict[str, Any]:
    if not query_one("SELECT id FROM projects WHERE id = ?", (project_id,)):
        raise NotFoundError("Project not found.")
    provider = registry.get("audio")
    with tempfile.TemporaryDirectory(prefix="cartoon_studio_music_") as tmp:
        path = Path(tmp) / "music.wav"
        result = await provider.generate_music(out_path=path, duration=duration)
        asset = store_asset_from_path(
            project_id=project_id,
            subdir="audio",
            filename="background_music.wav",
            source_path=path,
            kind="audio",
            mime="audio/wav",
            meta={"kind": "music", "duration_ms": int(duration * 1000), "provider": "kokoro"},
        )
    log(actor, "generate_music", "project", project_id, {"asset_id": asset["id"]})
    return {"asset": asset, "asset_id": asset["id"], "provider": result.get("provider")}


async def generate_voice_asset(
    project_id: str,
    text: str,
    *,
    engine: str | None = None,
    voice: str | None = None,
    rate: int = 0,
    pitch: int = 0,
    volume: int = 100,
    actor: str = "user",
) -> dict[str, Any]:
    if not query_one("SELECT id FROM projects WHERE id = ?", (project_id,)):
        raise NotFoundError("Project not found.")
    provider = registry.get("audio")
    with tempfile.TemporaryDirectory(prefix="cartoon_studio_voice_") as tmp:
        path = Path(tmp) / "voice.wav"
        result = await provider.generate_speech(
            out_path=path,
            text=text,
            engine=engine,
            voice=voice,
            rate=rate,
            pitch=pitch,
            volume=volume,
        )
        asset = store_asset_from_path(
            project_id=project_id,
            subdir="voice",
            filename="voice.wav",
            source_path=path,
            kind="audio",
            mime="audio/wav",
            meta={"kind": "voice", "text": text, "engine": result.get("engine"), "voice": result.get("voice")},
        )
    log(actor, "generate_voice_asset", "project", project_id, {"asset_id": asset["id"]})
    return {"asset": asset, "asset_id": asset["id"], "provider": result.get("provider"), "engine": result.get("engine"), "voice": result.get("voice")}
