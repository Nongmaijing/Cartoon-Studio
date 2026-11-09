from __future__ import annotations

import json
from typing import Any

from ..db import execute, now, query, query_one
from . import dialogue_service, episode_service, scene_service
from .audit_service import log
from .errors import ServiceError


def _character_map(project_id: str) -> dict[str, dict[str, Any]]:
    rows = query("SELECT id, name FROM characters WHERE project_id = ?", (project_id,))
    return {str(row["name"]).strip().lower(): row for row in rows}


def _background_map(project_id: str) -> dict[str, dict[str, Any]]:
    rows = query("SELECT id, name FROM backgrounds WHERE project_id = ?", (project_id,))
    return {str(row["name"]).strip().lower(): row for row in rows}


async def create_storyboard(episode_id: str, actor: str = "user") -> dict[str, Any]:
    episode = episode_service.get_episode(episode_id)
    project_id = episode["project_id"]
    script = (episode.get("script") or {}).get("scenes") or (episode.get("production") or {}).get("script", {}).get("scenes")
    if not script:
        raise ServiceError("Generate and approve a script before creating a storyboard.")
    characters = _character_map(project_id)
    backgrounds = _background_map(project_id)
    storyboard: list[dict[str, Any]] = []
    for index, item in enumerate(script):
        cast_names = item.get("characters") or []
        cast_ids = [
            characters[name.strip().lower()]["id"]
            for name in cast_names
            if name.strip().lower() in characters
        ]
        background = backgrounds.get(str(item.get("background") or "").strip().lower())
        title = str(item.get("title") or f"Scene {index + 1}").strip()
        description = str(item.get("summary") or "").strip()
        action = str(item.get("action") or "").strip()
        camera = str(item.get("camera") or "").strip()
        duration = float(item.get("duration_seconds") or 5.0)
        dialogue_text = "\n".join(
            f"{line.get('speaker', 'Narrator')}: {line.get('text', '')}"
            for line in (item.get("dialogue") or [])
            if line.get("text")
        )
        scene = scene_service.create_scene(
            project_id,
            name=title,
            description=description,
            dialogue_text=dialogue_text,
            action=action,
            camera=camera,
            duration=duration,
            background_id=background["id"] if background else None,
            character_ids=cast_ids,
            settings={},
            actor=actor,
        )
        for line_index, line in enumerate(item.get("dialogue") or []):
            text = str(line.get("text") or "").strip()
            if not text:
                continue
            speaker = str(line.get("speaker") or "Narrator").strip()
            character = characters.get(speaker.lower())
            await dialogue_service.create_line(
                scene["id"],
                character_id=character["id"] if character else None,
                text=text,
                emotion=str(line.get("emotion") or "neutral"),
                start_ms=line_index * 2500,
                actor=actor,
            )
        storyboard.append(
            {
                "scene_id": scene["id"],
                "number": index + 1,
                "title": title,
                "summary": description,
                "duration_seconds": duration,
                "character_ids": cast_ids,
                "background_id": background["id"] if background else None,
            }
        )
    execute(
        "UPDATE episodes SET storyboard_json = ?, production_json = ?, updated_at = ? WHERE id = ?",
        (
            json.dumps(storyboard),
            json.dumps({**(episode.get("production") or {}), "storyboard": storyboard}),
            now(),
            episode_id,
        ),
    )
    log(actor, "create_storyboard", "episode", episode_id, {"scenes": len(storyboard)})
    return {"episode_id": episode_id, "storyboard": storyboard, "scenes": [scene_service.get_scene_details(row["scene_id"]) for row in storyboard]}


def get_storyboard(episode_id: str) -> dict[str, Any]:
    episode = episode_service.get_episode(episode_id)
    storyboard = episode.get("storyboard") or []
    scenes = [scene_service.get_scene_details(row["scene_id"]) for row in storyboard if row.get("scene_id")]
    return {"episode_id": episode_id, "storyboard": storyboard, "scenes": scenes}
