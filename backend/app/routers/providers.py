from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from ..db import execute, now, query
from ..providers.registry import registry
from ..schemas_ai import ProviderConfigUpdate
from ..services.stats import system_stats

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])


@router.get("")
async def providers() -> dict[str, Any]:
    return {"providers": [info.as_dict() for info in registry.list_infos()]}


@router.get("/status")
async def status() -> dict[str, Any]:
    result = await registry.status()
    result["system"] = system_stats()
    return result


@router.post("/refresh")
async def refresh() -> dict[str, Any]:
    registry.refresh()
    return {"providers": [info.as_dict() for info in registry.list_infos()]}


@router.get("/configs")
async def configs() -> list[dict[str, Any]]:
    rows = query("SELECT * FROM provider_configs ORDER BY type, name")
    for row in rows:
        try:
            row["config"] = json.loads(row.pop("config_json") or "{}")
        except json.JSONDecodeError:
            row["config"] = {}
    return rows


@router.put("/configs/{config_id}")
async def update_config(config_id: str, payload: ProviderConfigUpdate) -> dict[str, Any]:
    row = query("SELECT * FROM provider_configs WHERE id = ?", (config_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Provider config not found.")
    updates = ["config_json = ?", "updated_at = ?"]
    params: list[Any] = [json.dumps(payload.config), now()]
    if payload.enabled is not None:
        updates.append("enabled = ?")
        params.append(1 if payload.enabled else 0)
    params.append(config_id)
    execute(f"UPDATE provider_configs SET {', '.join(updates)} WHERE id = ?", params)
    registry.refresh()
    return {"id": config_id, "config": payload.config, "enabled": payload.enabled}
