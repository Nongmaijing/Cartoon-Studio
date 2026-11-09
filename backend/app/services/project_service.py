from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from ..config import load_config
from ..db import execute, now, query, query_one
from .audit_service import log
from .errors import NotFoundError

PROJECT_SELECT = """
SELECT p.*,
    (SELECT COUNT(*) FROM characters c WHERE c.project_id = p.id) AS character_count,
    (SELECT COUNT(*) FROM backgrounds b WHERE b.project_id = p.id) AS background_count,
    (SELECT COUNT(*) FROM scenes s WHERE s.project_id = p.id) AS scene_count,
    (SELECT COUNT(*) FROM jobs j WHERE j.project_id = p.id) AS job_count,
    (SELECT COUNT(*) FROM assets a WHERE a.project_id = p.id) AS asset_count
FROM projects p
"""


def _make_dirs(config: dict[str, Any], project_id: str) -> None:
    base = Path(config["paths"]["projects_dir"]) / project_id
    for sub in ("characters", "backgrounds", "scenes", "episodes", "storyboards"):
        (base / sub).mkdir(parents=True, exist_ok=True)


def _parse_memory(row: dict[str, Any]) -> dict[str, Any]:
    try:
        row["memory"] = json.loads(row.get("memory_json") or "{}")
    except json.JSONDecodeError:
        row["memory"] = {}
    return row


def get_project(project_id: str) -> dict[str, Any]:
    row = query_one(PROJECT_SELECT + " WHERE p.id = ?", (project_id,))
    if not row:
        raise NotFoundError("Project not found.")
    return _parse_memory(row)


def list_projects(include_archived: bool = False) -> list[dict[str, Any]]:
    sql = PROJECT_SELECT
    if not include_archived:
        sql += " WHERE p.archived = 0"
    sql += " ORDER BY p.updated_at DESC"
    return [_parse_memory(row) for row in query(sql)]


def create_project(name: str, description: str = "", actor: str = "user") -> dict[str, Any]:
    project_id = uuid.uuid4().hex[:12]
    timestamp = now()
    execute(
        "INSERT INTO projects (id, name, description, memory_json, created_at, updated_at, archived) VALUES (?, ?, ?, ?, ?, ?, 0)",
        (project_id, name.strip(), description.strip(), "{}", timestamp, timestamp),
    )
    _make_dirs(load_config(), project_id)
    log(actor, "create_project", "project", project_id, {"name": name})
    return get_project(project_id)


def update_project(
    project_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    archived: bool | None = None,
    memory: dict[str, Any] | None = None,
    actor: str = "user",
) -> dict[str, Any]:
    get_project(project_id)
    updates: list[str] = []
    params: list[Any] = []
    if name is not None:
        updates.append("name = ?")
        params.append(name.strip())
    if description is not None:
        updates.append("description = ?")
        params.append(description.strip())
    if archived is not None:
        updates.append("archived = ?")
        params.append(1 if archived else 0)
    if memory is not None:
        updates.append("memory_json = ?")
        params.append(json.dumps(memory))
    if updates:
        updates.append("updated_at = ?")
        params.extend([now(), project_id])
        execute(f"UPDATE projects SET {', '.join(updates)} WHERE id = ?", params)
    log(actor, "update_project", "project", project_id, {"fields": list(updates)})
    return get_project(project_id)


def archive_project(project_id: str, actor: str = "user") -> dict[str, Any]:
    get_project(project_id)
    execute("UPDATE projects SET archived = 1, updated_at = ? WHERE id = ?", (now(), project_id))
    log(actor, "archive_project", "project", project_id)
    return get_project(project_id)
