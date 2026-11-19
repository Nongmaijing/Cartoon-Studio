from __future__ import annotations

import json
import uuid
from typing import Any

from ..db import execute, now, query, query_one
from .audit_service import log
from .canonical_service import validate_canonical_asset
from .errors import NotFoundError


def snapshot_character(character_id: str, approved: bool = False) -> dict[str, Any]:
    character = query_one("SELECT * FROM characters WHERE id = ?", (character_id,))
    if not character:
        raise NotFoundError("Character not found.")
    version_row = query_one(
        "SELECT COALESCE(MAX(version), 0) AS version FROM character_versions WHERE character_id = ?",
        (character_id,),
    )
    version = int(version_row["version"] if version_row else 0) + 1
    snapshot = {
        key: character.get(key)
        for key in (
            "name",
            "description",
            "style",
            "clothing",
            "appearance",
            "canonical_asset_id",
            "voice_engine",
            "voice_name",
            "voice_rate",
            "voice_pitch",
            "voice_volume",
            "memory_json",
        )
    }
    snapshot["version"] = version
    snapshot["approved"] = approved
    record = {
        "id": uuid.uuid4().hex[:12],
        "character_id": character_id,
        "version": version,
        "snapshot_json": json.dumps(snapshot),
        "approved": 1 if approved else 0,
        "created_at": now(),
    }
    execute(
        """INSERT INTO character_versions (id, character_id, version, snapshot_json, approved, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            record["id"],
            record["character_id"],
            record["version"],
            record["snapshot_json"],
            record["approved"],
            record["created_at"],
        ),
    )
    return record


def approve_character(character_id: str, actor: str = "user") -> dict[str, Any]:
    character = query_one("SELECT * FROM characters WHERE id = ?", (character_id,))
    if not character:
        raise NotFoundError("Character not found.")
    validate_canonical_asset(character, character.get("canonical_asset_id"))
    execute(
        "UPDATE characters SET approval_status = 'approved', approved_at = ?, updated_at = ? WHERE id = ?",
        (now(), now(), character_id),
    )
    snapshot = snapshot_character(character_id, approved=True)
    log(actor, "approve_character", "character", character_id, {"version": snapshot["version"]})
    return {"character_id": character_id, "status": "approved", "version": snapshot["version"]}


def approve_scene(scene_id: str, actor: str = "user", notes: str = "") -> dict[str, Any]:
    scene = query_one("SELECT * FROM scenes WHERE id = ?", (scene_id,))
    if not scene:
        raise NotFoundError("Scene not found.")
    execute(
        "UPDATE scenes SET approval_status = 'approved', approved_at = ?, updated_at = ? WHERE id = ?",
        (now(), now(), scene_id),
    )
    execute(
        """INSERT INTO scene_reviews (id, scene_id, status, notes, actor, quality_json, created_at)
           VALUES (?, ?, 'approved', ?, ?, '{}', ?)""",
        (uuid.uuid4().hex[:12], scene_id, notes, actor, now()),
    )
    log(actor, "approve_scene", "scene", scene_id, {"notes": notes})
    return {"scene_id": scene_id, "status": "approved"}


def reject_scene(scene_id: str, actor: str = "user", notes: str = "") -> dict[str, Any]:
    scene = query_one("SELECT * FROM scenes WHERE id = ?", (scene_id,))
    if not scene:
        raise NotFoundError("Scene not found.")
    execute(
        "UPDATE scenes SET approval_status = 'rejected', updated_at = ? WHERE id = ?",
        (now(), scene_id),
    )
    execute(
        """INSERT INTO scene_reviews (id, scene_id, status, notes, actor, quality_json, created_at)
           VALUES (?, ?, 'rejected', ?, ?, '{}', ?)""",
        (uuid.uuid4().hex[:12], scene_id, notes, actor, now()),
    )
    log(actor, "reject_scene", "scene", scene_id, {"notes": notes})
    return {"scene_id": scene_id, "status": "rejected"}


def record_scene_review(scene_id: str, report: dict[str, Any], actor: str = "quality_control") -> None:
    execute(
        "UPDATE scenes SET quality_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(report), now(), scene_id),
    )
    execute(
        """INSERT INTO scene_reviews (id, scene_id, status, notes, actor, quality_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            uuid.uuid4().hex[:12],
            scene_id,
            str(report.get("status") or "reviewed"),
            str(report.get("summary") or ""),
            actor,
            json.dumps(report),
            now(),
        ),
    )


def approve_script(episode_id: str, actor: str = "user") -> dict[str, Any]:
    episode = query_one("SELECT * FROM episodes WHERE id = ?", (episode_id,))
    if not episode:
        raise NotFoundError("Episode not found.")
    try:
        production = json.loads(episode.get("production_json") or "{}")
    except json.JSONDecodeError:
        production = {}
    production["script_approved"] = True
    execute(
        "UPDATE episodes SET production_json = ?, approved_at = ?, approved_by = ?, updated_at = ? WHERE id = ?",
        (json.dumps(production), now(), actor, now(), episode_id),
    )
    log(actor, "approve_script", "episode", episode_id)
    return {"episode_id": episode_id, "script_approved": True}


def restore_character_version(character_id: str, version_id: str, actor: str = "user") -> dict[str, Any]:
    row = query_one(
        "SELECT * FROM character_versions WHERE id = ? AND character_id = ?",
        (version_id, character_id),
    )
    if not row:
        raise NotFoundError("Character version not found.")
    snapshot = json.loads(row.get("snapshot_json") or "{}")
    fields = [
        "name",
        "description",
        "style",
        "clothing",
        "appearance",
        "canonical_asset_id",
        "voice_engine",
        "voice_name",
        "voice_rate",
        "voice_pitch",
        "voice_volume",
        "memory_json",
    ]
    updates = [f"{field} = ?" for field in fields if field in snapshot]
    params = [snapshot[field] for field in fields if field in snapshot]
    updates.append("updated_at = ?")
    params.extend([now(), character_id])
    execute(f"UPDATE characters SET {', '.join(updates)} WHERE id = ?", params)
    log(actor, "restore_character_version", "character", character_id, {"version_id": version_id})
    return {"character_id": character_id, "restored_version": snapshot.get("version")}
