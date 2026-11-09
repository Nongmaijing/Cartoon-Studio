from __future__ import annotations

import json
import uuid
from typing import Any

from ..db import execute, now, query


def log(
    actor: str,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    execute(
        """INSERT INTO audit_logs (id, actor, action, entity_type, entity_id, detail_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            uuid.uuid4().hex[:12],
            actor or "user",
            action,
            entity_type,
            entity_id,
            json.dumps(detail or {}),
            now(),
        ),
    )


def list_logs(
    limit: int = 100,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM audit_logs"
    clauses: list[str] = []
    params: list[Any] = []
    if entity_type:
        clauses.append("entity_type = ?")
        params.append(entity_type)
    if entity_id:
        clauses.append("entity_id = ?")
        params.append(entity_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = query(sql, params)
    for row in rows:
        row["detail"] = json.loads(row.pop("detail_json") or "{}")
    return rows
