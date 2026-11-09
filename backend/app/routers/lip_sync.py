from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..services import lip_sync_service
from ..services.errors import ServiceError

router = APIRouter(prefix="/api/v1/lip-sync", tags=["lip-sync"])


@router.post("/lines/{line_id}/generate")
async def generate_line(line_id: str) -> dict[str, Any]:
    try:
        return lip_sync_service.generate_for_line(line_id, actor="user")
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/lines/{line_id}")
async def get_line(line_id: str) -> dict[str, Any]:
    try:
        return lip_sync_service.get_for_line(line_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.put("/lines/{line_id}")
async def update_line(line_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    cues = payload.get("cues") if isinstance(payload.get("cues"), list) else []
    try:
        return lip_sync_service.update_cues(line_id, cues, actor="user")
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/scenes/{scene_id}/generate")
async def generate_scene(scene_id: str) -> dict[str, Any]:
    try:
        return lip_sync_service.generate_for_scene(scene_id, actor="user")
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
