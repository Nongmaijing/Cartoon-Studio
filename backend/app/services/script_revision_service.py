from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from ..db import connect, now, query, query_one
from .audit_service import log
from .errors import NotFoundError, ServiceError

MAX_SCENES = 100
MAX_DIALOGUE_LINES = 250
MAX_TITLE_LENGTH = 200
MAX_TEXT_LENGTH = 2000
MAX_NOTES_LENGTH = 4000


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _require_string(value: Any, field: str, *, max_length: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ServiceError(f"{field} must be a string.", status_code=400, code="invalid_script")
    text = value.strip()
    if not text and not allow_empty:
        raise ServiceError(f"{field} must not be empty.", status_code=400, code="invalid_script")
    if len(text) > max_length:
        raise ServiceError(
            f"{field} is too long (max {max_length} characters).",
            status_code=400,
            code="invalid_script",
        )
    return text


def validate_script_document(script: Any) -> dict[str, Any]:
    """Validate a script document and return its format and counts.

    Accepts the installed `{"story": {"scenes": [...]}}` shape and the
    generator's top-level `{"scenes": [...]}` shape.
    """
    if not isinstance(script, dict):
        raise ServiceError("script must be a JSON object.", status_code=400, code="invalid_script")

    if isinstance(script.get("story"), dict) and isinstance(script["story"].get("scenes"), list):
        story = script["story"]
        scenes = story["scenes"]
        script_format = "story_scenes"
    elif isinstance(script.get("scenes"), list):
        story = script
        scenes = script["scenes"]
        script_format = "scenes"
    else:
        raise ServiceError(
            "script must contain story.scenes or a top-level scenes list.",
            status_code=400,
            code="invalid_script",
        )

    if not scenes:
        raise ServiceError("script must contain at least one scene.", status_code=400, code="invalid_script")
    if len(scenes) > MAX_SCENES:
        raise ServiceError(
            f"script contains too many scenes (max {MAX_SCENES}).",
            status_code=400,
            code="invalid_script",
        )

    for field in ("title", "logline", "moral"):
        if field in story and story[field] is not None:
            _require_string(story[field], f"story.{field}", max_length=MAX_TEXT_LENGTH, allow_empty=True)

    dialogue_total = 0
    for scene_index, scene in enumerate(scenes, start=1):
        label = f"scenes[{scene_index}]"
        if not isinstance(scene, dict):
            raise ServiceError(f"{label} must be an object.", status_code=400, code="invalid_script")
        _require_string(scene.get("title"), f"{label}.title", max_length=MAX_TITLE_LENGTH)
        for field in ("summary", "action", "camera"):
            if field in scene and scene[field] is not None:
                _require_string(scene[field], f"{label}.{field}", max_length=MAX_TEXT_LENGTH, allow_empty=True)
        if "background" in scene and scene["background"] is not None:
            _require_string(scene["background"], f"{label}.background", max_length=MAX_TITLE_LENGTH, allow_empty=True)
        if "duration_seconds" in scene and scene["duration_seconds"] is not None:
            duration = scene["duration_seconds"]
            if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration < 0:
                raise ServiceError(
                    f"{label}.duration_seconds must be a non-negative number.",
                    status_code=400,
                    code="invalid_script",
                )
        characters = scene.get("characters")
        if not isinstance(characters, list):
            raise ServiceError(f"{label}.characters must be a list.", status_code=400, code="invalid_script")
        for character in characters:
            _require_string(character, f"{label}.characters[]", max_length=MAX_TITLE_LENGTH)
        dialogue = scene.get("dialogue")
        if not isinstance(dialogue, list):
            raise ServiceError(f"{label}.dialogue must be a list.", status_code=400, code="invalid_script")
        if len(dialogue) > MAX_DIALOGUE_LINES:
            raise ServiceError(
                f"{label}.dialogue contains too many lines (max {MAX_DIALOGUE_LINES}).",
                status_code=400,
                code="invalid_script",
            )
        for line_index, line in enumerate(dialogue, start=1):
            line_label = f"{label}.dialogue[{line_index}]"
            if not isinstance(line, dict):
                raise ServiceError(f"{line_label} must be an object.", status_code=400, code="invalid_script")
            _require_string(line.get("speaker"), f"{line_label}.speaker", max_length=MAX_TITLE_LENGTH)
            _require_string(line.get("text"), f"{line_label}.text", max_length=MAX_TEXT_LENGTH)
            if "emotion" in line and line["emotion"] is not None:
                _require_string(line["emotion"], f"{line_label}.emotion", max_length=MAX_TITLE_LENGTH, allow_empty=True)
            dialogue_total += 1

    return {
        "version": 1,
        "script": script,
        "format": script_format,
        "scene_count": len(scenes),
        "dialogue_lines": dialogue_total,
        "sha256": canonical_sha256(script),
    }


def _episode(episode_id: str) -> dict[str, Any]:
    episode = query_one("SELECT * FROM episodes WHERE id = ?", (episode_id,))
    if not episode:
        raise NotFoundError("Episode not found.")
    return episode


def _production(episode: dict[str, Any]) -> dict[str, Any]:
    return _parse_json(episode.get("production_json"))


def get_state(episode_id: str) -> dict[str, Any]:
    episode = _episode(episode_id)
    script = _parse_json(episode.get("script_json"))
    production = _production(episode)
    latest = query_one(
        "SELECT * FROM script_revisions WHERE episode_id = ? ORDER BY revision_number DESC LIMIT 1",
        (episode_id,),
    )
    return {
        "episode_id": episode_id,
        "current_sha256": canonical_sha256(script),
        "current_revision_id": production.get("script_revision_id"),
        "latest_revision_id": latest["id"] if latest else None,
        "latest_revision_number": latest["revision_number"] if latest else 0,
        "script_approved": bool(production.get("script_approved")),
        "has_script": bool(script),
        "storyboard_stale": bool(production.get("storyboard_stale")),
    }


def create_revision(
    episode_id: str,
    script: dict[str, Any],
    *,
    base_revision_id: str | None = None,
    expected_current_sha256: str | None = None,
    notes: str = "",
    actor: str = "user",
) -> dict[str, Any]:
    episode = _episode(episode_id)
    validated = validate_script_document(script)
    current_script = _parse_json(episode.get("script_json"))
    current_sha = canonical_sha256(current_script)

    if expected_current_sha256:
        if expected_current_sha256.strip().lower() != current_sha:
            raise ServiceError(
                "The episode script changed since the expected hash was captured.",
                status_code=409,
                code="script_hash_conflict",
            )
    elif current_script:
        raise ServiceError(
            "expected_current_sha256 is required when replacing an existing script.",
            status_code=409,
            code="script_hash_required",
        )

    latest = query_one(
        "SELECT * FROM script_revisions WHERE episode_id = ? ORDER BY revision_number DESC LIMIT 1",
        (episode_id,),
    )
    if base_revision_id:
        base = query_one(
            "SELECT * FROM script_revisions WHERE id = ? AND episode_id = ?",
            (base_revision_id, episode_id),
        )
        if not base:
            raise ServiceError("base_revision_id was not found for this episode.", status_code=400, code="invalid_base_revision")
        if latest and base["id"] != latest["id"]:
            raise ServiceError(
                "base_revision_id is not the latest revision for this episode.",
                status_code=409,
                code="stale_base_revision",
            )

    if notes and len(notes) > MAX_NOTES_LENGTH:
        raise ServiceError(
            f"notes is too long (max {MAX_NOTES_LENGTH} characters).",
            status_code=400,
            code="invalid_script",
        )

    revision_number = int(latest["revision_number"]) + 1 if latest else 1
    revision_id = uuid.uuid4().hex[:12]
    timestamp = now()
    production = _production(episode)
    production.update(
        {
            "script_approved": False,
            "script_approval_reset_at": timestamp,
            "script_revision_id": revision_id,
            "script_revision_number": revision_number,
            "script_sha256": validated["sha256"],
            "script_format": validated["format"],
            "storyboard_stale": True,
        }
    )
    script_json = json.dumps(script, ensure_ascii=False)
    production_json = json.dumps(production, ensure_ascii=False)

    with connect() as conn:
        conn.execute(
            """INSERT INTO script_revisions
               (id, episode_id, revision_number, script_json, sha256, script_format,
                scene_count, dialogue_lines, base_revision_id, actor, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                revision_id,
                episode_id,
                revision_number,
                script_json,
                validated["sha256"],
                validated["format"],
                validated["scene_count"],
                validated["dialogue_lines"],
                base_revision_id,
                actor,
                notes.strip(),
                timestamp,
            ),
        )
        conn.execute(
            """UPDATE episodes
               SET script_json = ?, production_json = ?, approved_at = NULL,
                   approved_by = NULL, updated_at = ?
               WHERE id = ?""",
            (script_json, production_json, timestamp, episode_id),
        )
        conn.commit()

    log(
        actor,
        "create_script_revision",
        "episode",
        episode_id,
        {
            "revision_id": revision_id,
            "revision_number": revision_number,
            "sha256": validated["sha256"],
            "script_format": validated["format"],
            "scene_count": validated["scene_count"],
            "dialogue_lines": validated["dialogue_lines"],
            "base_revision_id": base_revision_id,
        },
    )
    return {
        "episode_id": episode_id,
        "revision_id": revision_id,
        "revision_number": revision_number,
        "sha256": validated["sha256"],
        "script_format": validated["format"],
        "scene_count": validated["scene_count"],
        "dialogue_lines": validated["dialogue_lines"],
        "base_revision_id": base_revision_id,
        "script_approved": False,
        "approval_reset": True,
        "storyboard_stale": True,
        "created_at": timestamp,
    }


def list_revisions(episode_id: str, *, limit: int = 50, include_script: bool = False) -> list[dict[str, Any]]:
    _episode(episode_id)
    rows = query(
        """SELECT * FROM script_revisions WHERE episode_id = ?
           ORDER BY revision_number DESC LIMIT ?""",
        (episode_id, max(1, min(limit, 100))),
    )
    current_id = _production(_episode(episode_id)).get("script_revision_id")
    result = []
    for row in rows:
        item = {
            "revision_id": row["id"],
            "revision_number": row["revision_number"],
            "sha256": row["sha256"],
            "script_format": row["script_format"],
            "scene_count": row["scene_count"],
            "dialogue_lines": row["dialogue_lines"],
            "base_revision_id": row["base_revision_id"],
            "actor": row["actor"],
            "notes": row["notes"],
            "created_at": row["created_at"],
            "is_current": row["id"] == current_id,
        }
        if include_script:
            item["script"] = _parse_json(row["script_json"])
        result.append(item)
    return result


def get_revision(episode_id: str, revision_id: str) -> dict[str, Any]:
    _episode(episode_id)
    row = query_one(
        "SELECT * FROM script_revisions WHERE id = ? AND episode_id = ?",
        (revision_id, episode_id),
    )
    if not row:
        raise NotFoundError("Script revision not found.")
    current_id = _production(_episode(episode_id)).get("script_revision_id")
    return {
        "revision_id": row["id"],
        "episode_id": row["episode_id"],
        "revision_number": row["revision_number"],
        "sha256": row["sha256"],
        "script_format": row["script_format"],
        "scene_count": row["scene_count"],
        "dialogue_lines": row["dialogue_lines"],
        "base_revision_id": row["base_revision_id"],
        "actor": row["actor"],
        "notes": row["notes"],
        "created_at": row["created_at"],
        "is_current": row["id"] == current_id,
        "script": _parse_json(row["script_json"]),
    }
