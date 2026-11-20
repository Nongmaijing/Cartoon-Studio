from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..comfy.client import ComfyClient, ComfyError
from ..config import load_config
from ..db import query_one
from ..schemas import AssetUpscaleRequest
from ..services.assets import asset_file, get_asset, list_assets
from ..services.generation import submit_image, upload_start_image

router = APIRouter(prefix="/api/assets", tags=["assets"])

INLINE_TEXT_TYPES = {"text/plain", "application/x-subrip"}


def inline_media(mime: str, download: bool) -> bool:
    """Media plays in the browser; everything else downloads."""
    return not download and (
        mime.startswith(("image/", "video/", "audio/")) or mime in INLINE_TEXT_TYPES
    )


@router.get("")
async def assets(limit: int = 50, project_id: str | None = None, kind: str | None = None) -> list[dict]:
    return list_assets(limit=min(limit, 200), project_id=project_id, kind=kind)


@router.get("/{asset_id}")
async def asset(asset_id: str) -> dict:
    result = get_asset(asset_id)
    if not result:
        raise HTTPException(status_code=404, detail="Asset not found.")
    return result


@router.get("/{asset_id}/file")
async def asset_content(asset_id: str, download: bool = False) -> FileResponse:
    resolved = asset_file(asset_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Asset file not found.")
    path, asset = resolved
    mime = str(asset.get("mime") or "application/octet-stream")
    inline = inline_media(mime, download)
    if inline:
        # No filename argument: Starlette then omits the attachment header and
        # the browser displays images/video/audio inline.
        return FileResponse(path, media_type=mime, content_disposition_type="inline")
    return FileResponse(
        path,
        media_type=mime,
        filename=asset["filename"],
        content_disposition_type="attachment",
    )


@router.post("/{asset_id}/upscale", status_code=202)
async def upscale_asset(asset_id: str, payload: AssetUpscaleRequest) -> dict:
    asset = get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")
    if asset.get("kind") != "image" and not str(asset.get("mime") or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image assets can be upscaled.")
    project_id = asset.get("project_id")
    if not project_id:
        raise HTTPException(status_code=400, detail="Asset is not attached to a project.")

    attach: dict[str, str] = {}
    if payload.owner_type and payload.owner_id:
        table = {"character": "characters", "scene": "scenes", "background": "backgrounds"}[payload.owner_type]
        owner = query_one(
            f"SELECT id FROM {table} WHERE id = ? AND project_id = ?",
            (payload.owner_id, project_id),
        )
        if not owner:
            raise HTTPException(status_code=400, detail="Owner is not part of this project.")
        default_role = "keyframe" if payload.owner_type == "scene" else "reference"
        attach = {
            "owner_type": payload.owner_type,
            "owner_id": payload.owner_id,
            "role": payload.role or default_role,
            "label": payload.label or "upscaled",
        }

    config = load_config()
    client = ComfyClient(
        config["comfyui"]["server_url"],
        timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
    )
    try:
        input_image = await upload_start_image(config, client, asset_id, project_id)
        job = await submit_image(
            project_id=project_id,
            prompt="4x UltraSharp upscale",
            attach=attach,
            workflow_id=payload.workflow_id or "upscale_4x",
            input_image=input_image,
        )
    except (ValueError, ComfyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "job": job,
        "asset_id": asset_id,
        "mode": "upscale",
        "input_image": input_image,
    }
