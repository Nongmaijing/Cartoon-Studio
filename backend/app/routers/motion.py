from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException

from ..db import query_one
from ..schemas_ai import CameraClipRequest, CutoutRequest, ParallaxRequest
from ..services import motion_service

router = APIRouter(prefix="/api/v1/motion", tags=["motion"])

_CAMERA_NOTES = {
    "static": "Locked camera; only the subject moves.",
    "push_in": "Slow push toward the subject.",
    "pull_out": "Slow pull away from the subject.",
    "pan_left": "Camera drifts right-to-left across the plate.",
    "pan_right": "Camera drifts left-to-right across the plate.",
    "drift": "Gentle diagonal drift with a slight push.",
}


@router.get("/presets")
async def presets() -> dict[str, Any]:
    return {
        "cameras": [
            {"id": key, "note": _CAMERA_NOTES.get(key, "")}
            for key in motion_service.CAMERA_PRESETS
        ],
        "defaults": {
            "duration": 6.0,
            "fps": 24,
            "width": 1280,
            "height": 720,
            "camera": "push_in",
            "subject_height": 0.62,
            "subject_x": 0.5,
            "subject_y": 0.94,
            "motion_strength": 1.0,
            "bob_period": 2.6,
            "shadow": True,
        },
    }


def _require_project(project_id: str) -> None:
    if not query_one("SELECT id FROM projects WHERE id = ?", (project_id,)):
        raise HTTPException(status_code=404, detail="Project not found.")


@router.post("/cutout", status_code=201)
async def cutout(payload: CutoutRequest) -> dict[str, Any]:
    _require_project(payload.project_id)
    try:
        asset = await asyncio.to_thread(
            motion_service.cutout_asset,
            payload.project_id,
            payload.asset_id,
            engine=payload.engine,
            tolerance=payload.tolerance,
            feather=payload.feather,
            padding=payload.padding,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"asset": asset}


@router.post("/camera", status_code=201)
async def camera(payload: CameraClipRequest) -> dict[str, Any]:
    _require_project(payload.project_id)
    try:
        asset = await asyncio.to_thread(
            motion_service.camera_clip_asset,
            payload.project_id,
            payload.asset_id,
            duration=payload.duration,
            fps=payload.fps,
            width=payload.width,
            height=payload.height,
            camera=payload.camera,
            motion_strength=payload.motion_strength,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"asset": asset}


@router.post("/parallax", status_code=201)
async def parallax(payload: ParallaxRequest) -> dict[str, Any]:
    _require_project(payload.project_id)
    try:
        asset = await asyncio.to_thread(
            motion_service.parallax_asset,
            payload.project_id,
            payload.background_asset_id,
            payload.foreground_asset_id,
            duration=payload.duration,
            fps=payload.fps,
            width=payload.width,
            height=payload.height,
            camera=payload.camera,
            subject_height=payload.subject_height,
            subject_x=payload.subject_x,
            subject_y=payload.subject_y,
            motion_strength=payload.motion_strength,
            bob_period=payload.bob_period,
            shadow=payload.shadow,
            scene_id=payload.scene_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"asset": asset}
