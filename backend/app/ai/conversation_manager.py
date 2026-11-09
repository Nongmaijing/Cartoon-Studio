from __future__ import annotations

import json
import uuid
from typing import Any

from ..db import execute, now, query, query_one
from ..services.audit_service import log
from ..services.errors import NotFoundError


def create_conversation(
    project_id: str | None = None,
    episode_id: str | None = None,
    title: str = "",
    model: str = "",
    actor: str = "user",
) -> dict[str, Any]:
    conversation_id = uuid.uuid4().hex[:12]
    timestamp = now()
    execute(
        """INSERT INTO ai_conversations
           (id, project_id, episode_id, title, model, context_json, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, '{}', ?, ?)""",
        (conversation_id, project_id, episode_id, title.strip() or "New conversation", model, timestamp, timestamp),
    )
    log(actor, "create_ai_conversation", "ai_conversation", conversation_id)
    return get_conversation(conversation_id)


def list_conversations(project_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    if project_id:
        rows = query(
            "SELECT * FROM ai_conversations WHERE project_id = ? ORDER BY updated_at DESC LIMIT ?",
            (project_id, limit),
        )
    else:
        rows = query("SELECT * FROM ai_conversations ORDER BY updated_at DESC LIMIT ?", (limit,))
    return rows


def get_conversation(conversation_id: str) -> dict[str, Any]:
    row = query_one("SELECT * FROM ai_conversations WHERE id = ?", (conversation_id,))
    if not row:
        raise NotFoundError("AI conversation not found.")
    row["messages"] = query(
        "SELECT * FROM ai_messages WHERE conversation_id = ? ORDER BY created_at ASC",
        (conversation_id,),
    )
    for message in row["messages"]:
        try:
            message["tool_calls"] = json.loads(message.pop("tool_calls_json") or "[]")
        except json.JSONDecodeError:
            message["tool_calls"] = []
    row["tool_executions"] = query(
        "SELECT * FROM ai_tool_executions WHERE conversation_id = ? ORDER BY created_at ASC",
        (conversation_id,),
    )
    for execution in row["tool_executions"]:
        for key in ("arguments_json", "result_json"):
            try:
                execution[key.replace("_json", "")] = json.loads(execution.pop(key) or "{}")
            except json.JSONDecodeError:
                execution[key.replace("_json", "")] = {}
    return row


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    tool_calls: list[dict[str, Any]] | None = None,
    response_id: str | None = None,
) -> dict[str, Any]:
    message_id = uuid.uuid4().hex[:12]
    execute(
        """INSERT INTO ai_messages (id, conversation_id, role, content, tool_calls_json, response_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (message_id, conversation_id, role, content, json.dumps(tool_calls or []), response_id, now()),
    )
    execute("UPDATE ai_conversations SET updated_at = ? WHERE id = ?", (now(), conversation_id))
    return {"id": message_id, "conversation_id": conversation_id, "role": role, "content": content, "tool_calls": tool_calls or []}


def update_conversation(
    conversation_id: str,
    *,
    last_response_id: str | None = None,
    context: dict[str, Any] | None = None,
    project_id: str | None = None,
    episode_id: str | None = None,
) -> None:
    parts = ["updated_at = ?"]
    params: list[Any] = [now()]
    if last_response_id is not None:
        parts.append("last_response_id = ?")
        params.append(last_response_id)
    if context is not None:
        parts.append("context_json = ?")
        params.append(json.dumps(context))
    if project_id is not None:
        parts.append("project_id = ?")
        params.append(project_id)
    if episode_id is not None:
        parts.append("episode_id = ?")
        params.append(episode_id)
    params.append(conversation_id)
    execute(f"UPDATE ai_conversations SET {', '.join(parts)} WHERE id = ?", params)


def add_context_snapshot(conversation_id: str, project_id: str | None, context: dict[str, Any]) -> None:
    execute(
        """INSERT INTO ai_context_snapshots (id, conversation_id, project_id, snapshot_json, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (uuid.uuid4().hex[:12], conversation_id, project_id, json.dumps(context), now()),
    )


def list_tool_executions(conversation_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    if conversation_id:
        rows = query(
            "SELECT * FROM ai_tool_executions WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?",
            (conversation_id, limit),
        )
    else:
        rows = query("SELECT * FROM ai_tool_executions ORDER BY created_at DESC LIMIT ?", (limit,))
    for row in rows:
        for key in ("arguments_json", "result_json"):
            try:
                row[key.replace("_json", "")] = json.loads(row.pop(key) or "{}")
            except json.JSONDecodeError:
                row[key.replace("_json", "")] = {}
    return rows
