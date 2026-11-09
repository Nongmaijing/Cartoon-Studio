from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..config import load_config
from ..services import resource_manager

router = APIRouter(prefix="/api/v1/resources", tags=["resources"])


@router.get("/status")
async def status() -> dict[str, Any]:
    return await resource_manager.snapshot()


@router.post("/free")
async def free() -> dict[str, Any]:
    return await resource_manager.free_vram()


@router.post("/estimate")
async def estimate(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_id = str(payload.get("workflow_id") or "")
    if not workflow_id:
        raise HTTPException(status_code=400, detail="workflow_id is required.")
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    return resource_manager.estimate_job(load_config(), workflow_id, params)
