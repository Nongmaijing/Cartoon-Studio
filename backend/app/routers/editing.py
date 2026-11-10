from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..config import load_config
from ..comfy.client import ComfyError
from ..schemas import EditRequest
from ..services import editing_service
from ..workflows.registry import find_workflow

router = APIRouter(prefix="/api/v1/editing", tags=["editing"])

MASK_NODES = ("LoadImageMask", "VAEEncodeForInpaint")


@router.get("/status")
async def status() -> dict[str, Any]:
    config = load_config()
    client = editing_service.comfy_client(config)
    try:
        object_info = await client.object_info()
        comfy_error = None
    except ComfyError as exc:
        object_info = {}
        comfy_error = str(exc)

    checkpoint = await editing_service.inpaint_checkpoint(config, client) if object_info else ""
    entry = find_workflow(config, "sdxl_inpaint")
    missing_nodes = [name for name in MASK_NODES if object_info and name not in object_info]
    masked_ready = bool(checkpoint) and not missing_nodes and bool(entry and entry.get("valid"))
    whole_entry = find_workflow(config, "sdxl_img2img")
    whole_ready = bool(whole_entry and whole_entry.get("valid"))
    return {
        "ready": whole_ready or masked_ready,
        "whole_image": {
            "ready": whole_ready,
            "workflow": "sdxl_img2img" if whole_ready else "",
        },
        "masked": {
            "ready": masked_ready,
            "workflow": "sdxl_inpaint" if masked_ready else "",
            "checkpoint": checkpoint or "",
            "missing_nodes": missing_nodes,
        },
        "comfyui_error": comfy_error,
    }


@router.post("/edit", status_code=202)
async def edit(payload: EditRequest) -> dict[str, Any]:
    try:
        return await editing_service.edit_image(
            source_asset_id=payload.source_asset_id,
            prompt=payload.prompt,
            mask_asset_id=payload.mask_asset_id,
            negative_prompt=payload.negative_prompt,
            seed=payload.seed,
            steps=payload.steps,
            cfg=payload.cfg,
            denoise=payload.denoise,
            width=payload.width,
            height=payload.height,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

