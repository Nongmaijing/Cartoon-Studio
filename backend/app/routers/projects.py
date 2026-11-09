from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..config import load_config
from ..db import execute, now, query, query_one
from ..schemas import ProjectCreate, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["projects"])

PROJECT_SELECT = """
SELECT p.*,
    (SELECT COUNT(*) FROM characters c WHERE c.project_id = p.id) AS character_count,
    (SELECT COUNT(*) FROM backgrounds b WHERE b.project_id = p.id) AS background_count,
    (SELECT COUNT(*) FROM scenes s WHERE s.project_id = p.id) AS scene_count,
    (SELECT COUNT(*) FROM jobs j WHERE j.project_id = p.id) AS job_count,
    (SELECT COUNT(*) FROM assets a WHERE a.project_id = p.id) AS asset_count
FROM projects p
"""


def _get(project_id: str) -> dict:
    row = query_one(PROJECT_SELECT + " WHERE p.id = ?", (project_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Project not found.")
    return row


def _make_project_dirs(config: dict, project_id: str) -> None:
    base = Path(config["paths"]["projects_dir"]) / project_id
    for sub in ("characters", "backgrounds", "scenes", "episodes"):
        (base / sub).mkdir(parents=True, exist_ok=True)


@router.get("")
async def list_projects(include_archived: bool = False) -> list[dict]:
    sql = PROJECT_SELECT
    if not include_archived:
        sql += " WHERE p.archived = 0"
    sql += " ORDER BY p.updated_at DESC"
    return query(sql)


@router.post("", status_code=201)
async def create_project(payload: ProjectCreate) -> dict:
    config = load_config()
    project_id = uuid.uuid4().hex[:12]
    timestamp = now()
    execute(
        "INSERT INTO projects (id, name, description, created_at, updated_at, archived) VALUES (?, ?, ?, ?, ?, 0)",
        (project_id, payload.name.strip(), payload.description.strip(), timestamp, timestamp),
    )
    _make_project_dirs(config, project_id)
    return _get(project_id)


@router.get("/{project_id}")
async def get_project(project_id: str) -> dict:
    return _get(project_id)


@router.patch("/{project_id}")
async def update_project(project_id: str, payload: ProjectUpdate) -> dict:
    _get(project_id)
    updates: list[str] = []
    params: list = []
    if payload.name is not None:
        updates.append("name = ?")
        params.append(payload.name.strip())
    if payload.description is not None:
        updates.append("description = ?")
        params.append(payload.description.strip())
    if payload.archived is not None:
        updates.append("archived = ?")
        params.append(1 if payload.archived else 0)
    if updates:
        updates.append("updated_at = ?")
        params.append(now())
        params.append(project_id)
        execute(f"UPDATE projects SET {', '.join(updates)} WHERE id = ?", params)
    return _get(project_id)


@router.post("/{project_id}/archive")
async def archive_project(project_id: str) -> dict:
    _get(project_id)
    execute("UPDATE projects SET archived = 1, updated_at = ? WHERE id = ?", (now(), project_id))
    return _get(project_id)


@router.post("/{project_id}/duplicate", status_code=201)
async def duplicate_project(project_id: str) -> dict:
    source = _get(project_id)
    config = load_config()
    new_id = uuid.uuid4().hex[:12]
    timestamp = now()
    execute(
        "INSERT INTO projects (id, name, description, created_at, updated_at, archived) VALUES (?, ?, ?, ?, ?, 0)",
        (new_id, f"{source['name']} copy", source["description"], timestamp, timestamp),
    )
    _make_project_dirs(config, new_id)

    # Copy output media, then remap asset rows so the copy owns its files.
    src_output = Path(config["paths"]["output_dir"]) / project_id
    dst_output = Path(config["paths"]["output_dir"]) / new_id
    if src_output.exists():
        shutil.copytree(src_output, dst_output)

    asset_map: dict[str, str] = {}
    for asset in query("SELECT * FROM assets WHERE project_id = ?", (project_id,)):
        new_asset_id = uuid.uuid4().hex[:12]
        rel_path = asset["rel_path"].replace(f"{project_id}/", f"{new_id}/", 1)
        execute(
            """INSERT INTO assets (id, project_id, job_id, kind, filename, rel_path, mime, meta_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_asset_id,
                new_id,
                asset["job_id"],
                asset["kind"],
                asset["filename"],
                rel_path,
                asset["mime"],
                asset["meta_json"],
                now(),
            ),
        )
        asset_map[asset["id"]] = new_asset_id

    # Characters and backgrounds belong to the project, so the copy owns its own rows.
    character_map: dict[str, str] = {}
    for character in query("SELECT * FROM characters WHERE project_id = ?", (project_id,)):
        new_character_id = uuid.uuid4().hex[:12]
        execute(
            """INSERT INTO characters
               (id, project_id, name, description, style, clothing, appearance, canonical_asset_id,
                voice_engine, voice_name, voice_rate, voice_pitch, voice_volume, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_character_id,
                new_id,
                character["name"],
                character["description"],
                character["style"],
                character["clothing"],
                character["appearance"],
                asset_map.get(character.get("canonical_asset_id")),
                character.get("voice_engine") or "",
                character.get("voice_name") or "",
                character.get("voice_rate") or 0,
                character.get("voice_pitch") or 0,
                character.get("voice_volume") if character.get("voice_volume") is not None else 100,
                now(),
                now(),
            ),
        )
        character_map[character["id"]] = new_character_id

    background_map: dict[str, str] = {}
    for background in query("SELECT * FROM backgrounds WHERE project_id = ?", (project_id,)):
        new_background_id = uuid.uuid4().hex[:12]
        execute(
            """INSERT INTO backgrounds
               (id, project_id, name, description, aspect_ratio, width, height, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_background_id,
                new_id,
                background["name"],
                background["description"],
                background["aspect_ratio"],
                background["width"],
                background["height"],
                now(),
            ),
        )
        background_map[background["id"]] = new_background_id

    # Scenes keep their cast and location, remapped to the copied rows.
    scene_map: dict[str, str] = {}
    for scene in query("SELECT * FROM scenes WHERE project_id = ?", (project_id,)):
        new_scene_id = uuid.uuid4().hex[:12]
        try:
            settings = json.loads(scene["settings_json"] or "{}")
        except json.JSONDecodeError:
            settings = {}
        background_id = settings.get("background_id")
        if background_id in background_map:
            settings["background_id"] = background_map[background_id]
        execute(
            """INSERT INTO scenes
               (id, project_id, name, description, dialogue, action, camera, duration,
                settings_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_scene_id,
                new_id,
                scene["name"],
                scene["description"],
                scene["dialogue"],
                scene["action"],
                scene["camera"],
                scene["duration"],
                json.dumps(settings),
                now(),
                now(),
            ),
        )
        scene_map[scene["id"]] = new_scene_id

    for row in query(
        """SELECT sc.* FROM scene_cast sc
           JOIN scenes s ON s.id = sc.scene_id
           WHERE s.project_id = ?""",
        (project_id,),
    ):
        new_scene_id = scene_map.get(row["scene_id"])
        new_character_id = character_map.get(row["character_id"])
        if not new_scene_id or not new_character_id:
            continue
        execute(
            """INSERT INTO scene_cast (id, scene_id, character_id, role, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (uuid.uuid4().hex[:12], new_scene_id, new_character_id, row["role"], now()),
        )

    # Dialogue lines keep their text, voice settings, order and generated audio.
    for line in query("SELECT * FROM dialogue_lines WHERE project_id = ?", (project_id,)):
        new_scene_id = scene_map.get(line["scene_id"])
        if not new_scene_id:
            continue
        new_character_id = character_map.get(line["character_id"]) if line.get("character_id") else None
        new_audio_id = asset_map.get(line["audio_asset_id"]) if line.get("audio_asset_id") else None
        execute(
            """INSERT INTO dialogue_lines
               (id, project_id, scene_id, character_id, order_index, text, emotion,
                voice_engine, voice_name, rate, pitch, volume, start_ms,
                audio_asset_id, duration_ms, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                uuid.uuid4().hex[:12],
                new_id,
                new_scene_id,
                new_character_id,
                line["order_index"],
                line["text"],
                line["emotion"],
                line.get("voice_engine") or "",
                line.get("voice_name") or "",
                line.get("rate") or 0,
                line.get("pitch") or 0,
                line.get("volume") if line.get("volume") is not None else 100,
                line.get("start_ms") or 0,
                new_audio_id,
                line.get("duration_ms") or 0,
                now(),
                now(),
            ),
        )

    # Episodes keep their timeline, with scene and asset ids remapped.
    for episode in query("SELECT * FROM episodes WHERE project_id = ?", (project_id,)):
        try:
            timeline = json.loads(episode.get("timeline_json") or "{}")
        except json.JSONDecodeError:
            timeline = {}
        if isinstance(timeline, list):
            timeline = {"segments": timeline, "audio": [], "settings": {}}
        if not isinstance(timeline, dict):
            timeline = {}
        segments = []
        for segment in timeline.get("segments") or []:
            scene_id = scene_map.get(segment.get("scene_id"))
            asset_id = asset_map.get(segment.get("asset_id"))
            if not scene_id or not asset_id:
                continue
            segments.append({**segment, "scene_id": scene_id, "asset_id": asset_id})
        audio = []
        for item in timeline.get("audio") or []:
            asset_id = asset_map.get(item.get("asset_id"))
            if not asset_id:
                continue
            audio.append({**item, "asset_id": asset_id})
        settings = dict(timeline.get("settings") or {})
        music_id = settings.get("background_music_asset_id")
        if music_id:
            settings["background_music_asset_id"] = asset_map.get(music_id)
        timeline = {**timeline, "segments": segments, "audio": audio, "settings": settings}

        output_asset_id = (
            asset_map.get(episode.get("output_asset_id")) if episode.get("output_asset_id") else None
        )
        output_path = episode.get("output_path")
        if output_path:
            output_path = output_path.replace(f"{project_id}/", f"{new_id}/", 1)
        subtitle_path = episode.get("subtitle_path")
        if subtitle_path:
            subtitle_path = subtitle_path.replace(f"{project_id}/", f"{new_id}/", 1)
        execute(
            """INSERT INTO episodes
               (id, project_id, name, description, status, progress, timeline_json, settings_json,
                output_path, output_asset_id, subtitle_path, duration_ms, error, log,
                started_at, finished_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                uuid.uuid4().hex[:12],
                new_id,
                episode["name"],
                episode.get("description") or "",
                episode.get("status") or "draft",
                episode.get("progress") or 0,
                json.dumps(timeline),
                json.dumps(settings),
                output_path,
                output_asset_id,
                subtitle_path,
                episode.get("duration_ms") or 0,
                episode.get("error"),
                episode.get("log"),
                episode.get("started_at"),
                episode.get("finished_at"),
                now(),
                now(),
            ),
        )

    # Re-point media links at the copied rows and copied assets.
    for link in query(
        "SELECT * FROM media_links WHERE owner_type IN ('character', 'background', 'scene')"
    ):
        if link["owner_type"] == "character":
            owner_id = character_map.get(link["owner_id"])
        elif link["owner_type"] == "background":
            owner_id = background_map.get(link["owner_id"])
        else:
            owner_id = scene_map.get(link["owner_id"])
        asset_id = asset_map.get(link["asset_id"])
        if not owner_id or not asset_id:
            continue
        execute(
            """INSERT INTO media_links (id, asset_id, owner_type, owner_id, role, label, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                uuid.uuid4().hex[:12],
                asset_id,
                link["owner_type"],
                owner_id,
                link["role"],
                link["label"],
                now(),
            ),
        )
    return _get(new_id)
