from __future__ import annotations

from typing import Any

from ..db import query_one
from . import dialogue
from .audit_service import log
from .errors import NotFoundError


def list_lines(scene_id: str) -> list[dict[str, Any]]:
    if not query_one("SELECT id FROM scenes WHERE id = ?", (scene_id,)):
        raise NotFoundError("Scene not found.")
    return dialogue.list_lines(scene_id)


def get_line(line_id: str) -> dict[str, Any]:
    line = dialogue.get_line(line_id)
    if not line:
        raise NotFoundError("Dialogue line not found.")
    return line


async def create_line(
    scene_id: str,
    *,
    character_id: str | None,
    text: str,
    emotion: str = "neutral",
    start_ms: int = 0,
    actor: str = "user",
) -> dict[str, Any]:
    if not query_one("SELECT id FROM scenes WHERE id = ?", (scene_id,)):
        raise NotFoundError("Scene not found.")
    line = await dialogue.create_line(
        scene_id,
        character_id=character_id,
        text=text,
        emotion=emotion,
        start_ms=start_ms,
    )
    log(actor, "create_dialogue_line", "scene", scene_id, {"line_id": line.get("id")})
    return line


async def update_line(line_id: str, payload: Any, actor: str = "user") -> dict[str, Any]:
    get_line(line_id)
    line = dialogue.update_line(line_id, payload)
    log(actor, "update_dialogue_line", "dialogue", line_id)
    return line


async def generate_line(line_id: str, actor: str = "user") -> dict[str, Any]:
    get_line(line_id)
    line = await dialogue.generate_line(line_id)
    log(actor, "generate_dialogue_audio", "dialogue", line_id, {"asset_id": line.get("audio_asset_id")})
    return line


async def generate_scene(scene_id: str, actor: str = "user") -> dict[str, Any]:
    if not query_one("SELECT id FROM scenes WHERE id = ?", (scene_id,)):
        raise NotFoundError("Scene not found.")
    result = await dialogue.generate_scene(scene_id)
    log(actor, "generate_scene_dialogue", "scene", scene_id, {"generated": result.get("generated")})
    return result


def audio_status(scene_id: str) -> dict[str, Any]:
    lines = list_lines(scene_id)
    return {
        "scene_id": scene_id,
        "lines": lines,
        "total": len(lines),
        "with_audio": sum(1 for line in lines if line.get("audio_asset_id")),
        "missing_audio": [line["id"] for line in lines if not line.get("audio_asset_id")],
    }
