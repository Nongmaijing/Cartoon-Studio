from __future__ import annotations

import json
from typing import Any

from ..db import query, query_one
from .media import cover_asset_id, media_counts


def raw_scene(scene_id: str) -> dict[str, Any] | None:
    return query_one("SELECT * FROM scenes WHERE id = ?", (scene_id,))


def scene_settings(scene: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(scene.get("settings_json") or "{}")
    except json.JSONDecodeError:
        value = {}
    return value if isinstance(value, dict) else {}


def scene_background(settings: dict[str, Any]) -> dict[str, Any] | None:
    background_id = settings.get("background_id")
    if not background_id:
        return None
    background = query_one("SELECT * FROM backgrounds WHERE id = ?", (background_id,))
    if not background:
        return None
    cover = cover_asset_id("background", background_id)
    return {
        "id": background["id"],
        "name": background["name"],
        "description": background["description"],
        "width": background["width"],
        "height": background["height"],
        "cover_url": f"/api/assets/{cover}/file" if cover else None,
    }


def scene_characters(scene_id: str) -> list[dict[str, Any]]:
    return query(
        """SELECT c.* FROM scene_cast sc
           JOIN characters c ON c.id = sc.character_id
           WHERE sc.scene_id = ?
           ORDER BY sc.created_at ASC""",
        (scene_id,),
    )


def scene_cast(scene_id: str) -> list[dict[str, Any]]:
    rows = query(
        """SELECT sc.id AS cast_id, sc.role AS cast_role,
                  c.id AS character_id, c.name, c.description, c.appearance, c.clothing
           FROM scene_cast sc
           JOIN characters c ON c.id = sc.character_id
           WHERE sc.scene_id = ?
           ORDER BY sc.created_at ASC""",
        (scene_id,),
    )
    result: list[dict[str, Any]] = []
    for row in rows:
        cover = cover_asset_id("character", row["character_id"])
        result.append(
            {
                "id": row["cast_id"],
                "character_id": row["character_id"],
                "name": row["name"],
                "description": row["description"],
                "role": row["cast_role"],
                "cover_url": f"/api/assets/{cover}/file" if cover else None,
            }
        )
    return result


def decorate_scene(row: dict[str, Any]) -> dict[str, Any]:
    settings = scene_settings(row)
    counts = media_counts("scene", row["id"])
    cover = cover_asset_id("scene", row["id"], role="keyframe") or cover_asset_id("scene", row["id"])
    dialogue = query_one(
        """SELECT COUNT(*) AS n, COALESCE(SUM(duration_ms), 0) AS duration
           FROM dialogue_lines WHERE scene_id = ?""",
        (row["id"],),
    )
    row["settings"] = settings
    row["background"] = scene_background(settings)
    row["cast"] = scene_cast(row["id"])
    row["keyframe_count"] = counts.get("keyframe", 0)
    row["video_count"] = counts.get("video", 0)
    row["dialogue_count"] = int(dialogue["n"]) if dialogue else 0
    row["dialogue_duration_ms"] = int(dialogue["duration"]) if dialogue else 0
    try:
        row["quality"] = json.loads(row.get("quality_json") or "{}")
    except json.JSONDecodeError:
        row["quality"] = {}
    row["cover_asset_id"] = cover
    row["cover_url"] = f"/api/assets/{cover}/file" if cover else None
    return row


def get_scene(scene_id: str) -> dict[str, Any] | None:
    row = raw_scene(scene_id)
    return decorate_scene(row) if row else None
