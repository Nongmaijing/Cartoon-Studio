from __future__ import annotations

import json
import uuid
from typing import Any

from ..db import execute, now, query
from .assets import asset_file, get_asset, list_assets
from .episodes import get_episode
from .media import list_media


def record_version(
    asset_id: str,
    *,
    parent_asset_id: str | None = None,
    version: int = 1,
    operation: str = "generated",
    approved: bool = False,
) -> dict[str, Any]:
    row = {
        "id": uuid.uuid4().hex[:12],
        "asset_id": asset_id,
        "parent_asset_id": parent_asset_id,
        "version": version,
        "operation": operation,
        "approved": 1 if approved else 0,
        "created_at": now(),
    }
    execute(
        """INSERT INTO asset_versions (id, asset_id, parent_asset_id, version, operation, approved, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            row["id"],
            row["asset_id"],
            row["parent_asset_id"],
            row["version"],
            row["operation"],
            row["approved"],
            row["created_at"],
        ),
    )
    return row


def assets_for_project(project_id: str, kind: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    return list_assets(limit=limit, project_id=project_id, kind=kind)


def assets_for_episode(episode_id: str) -> dict[str, Any]:
    episode = get_episode(episode_id)
    result: dict[str, Any] = {
        "episode_id": episode_id,
        "output": get_asset(episode["output_asset_id"]) if episode.get("output_asset_id") else None,
        "scenes": [],
    }
    seen_scenes: set[str] = set()
    for segment in episode.get("timeline", {}).get("segments", []):
        scene_id = segment.get("scene_id")
        if not scene_id or scene_id in seen_scenes:
            continue
        seen_scenes.add(scene_id)
        media = list_media("scene", scene_id)
        result["scenes"].append(
            {
                "scene_id": scene_id,
                "assets": media,
            }
        )
    return result


__all__ = [
    "asset_file",
    "assets_for_episode",
    "assets_for_project",
    "get_asset",
    "record_version",
]
