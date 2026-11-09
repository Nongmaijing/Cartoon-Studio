from __future__ import annotations

import json
import uuid
from typing import Any

from ..db import execute, now, query, query_one
from ..logging_setup import logger


def link_asset(owner_type: str, owner_id: str, asset_id: str, role: str = "reference", label: str = "") -> dict[str, Any]:
    """Attach an existing asset to a character/background/scene without copying or deleting it."""
    asset = query_one("SELECT id FROM assets WHERE id = ?", (asset_id,))
    if not asset:
        raise ValueError(f"Asset '{asset_id}' does not exist.")
    link_id = uuid.uuid4().hex[:12]
    execute(
        """INSERT INTO media_links (id, asset_id, owner_type, owner_id, role, label, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (link_id, asset_id, owner_type, owner_id, role, label, now()),
    )
    logger.info("Linked asset %s to %s %s as %s", asset_id, owner_type, owner_id, role)
    return {"id": link_id, "asset_id": asset_id, "role": role, "label": label}


def _decorate(row: dict[str, Any]) -> dict[str, Any]:
    row["meta"] = json.loads(row.pop("meta_json") or "{}")
    row["url"] = f"/api/assets/{row['id']}/file"
    return row


def list_media(owner_type: str, owner_id: str, role: str | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT m.id AS link_id, m.role AS link_role, m.label AS link_label, a.*
        FROM media_links m
        JOIN assets a ON a.id = m.asset_id
        WHERE m.owner_type = ? AND m.owner_id = ?
    """
    params: list[Any] = [owner_type, owner_id]
    if role:
        sql += " AND m.role = ?"
        params.append(role)
    sql += " ORDER BY m.created_at ASC"
    rows = query(sql, params)
    result: list[dict[str, Any]] = []
    for row in rows:
        role_value = row.pop("link_role")
        label = row.pop("link_label")
        item = _decorate(row)
        item["role"] = role_value
        item["label"] = label
        result.append(item)
    return result


def media_counts(owner_type: str, owner_id: str) -> dict[str, int]:
    rows = query(
        "SELECT role, COUNT(*) AS n FROM media_links WHERE owner_type = ? AND owner_id = ? GROUP BY role",
        (owner_type, owner_id),
    )
    return {row["role"]: int(row["n"]) for row in rows}


def cover_asset_id(owner_type: str, owner_id: str, role: str | None = None) -> str | None:
    sql = """SELECT asset_id FROM media_links
             WHERE owner_type = ? AND owner_id = ?"""
    params: list[Any] = [owner_type, owner_id]
    if role:
        sql += " AND role = ?"
        params.append(role)
    sql += " ORDER BY created_at DESC LIMIT 1"
    row = query_one(sql, params)
    return row["asset_id"] if row else None


def delete_links_for_asset(asset_id: str) -> None:
    execute("DELETE FROM media_links WHERE asset_id = ?", (asset_id,))
