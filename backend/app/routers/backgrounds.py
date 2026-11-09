from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from ..db import execute, now, query, query_one
from ..schemas import BackgroundCreate, BackgroundGenerateRequest, BackgroundUpdate, MediaAttach
from ..services.creative import BACKGROUND_NEGATIVE, background_prompt
from ..services.generation import submit_image
from ..services.media import cover_asset_id, link_asset, list_media, media_counts

router = APIRouter(prefix="/api/backgrounds", tags=["backgrounds"])


def _decorate(row: dict[str, Any]) -> dict[str, Any]:
    counts = media_counts("background", row["id"])
    row["image_count"] = sum(counts.values())
    cover = cover_asset_id("background", row["id"])
    row["cover_asset_id"] = cover
    row["cover_url"] = f"/api/assets/{cover}/file" if cover else None
    return row


def _get(background_id: str) -> dict[str, Any]:
    row = query_one("SELECT * FROM backgrounds WHERE id = ?", (background_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Background not found.")
    return _decorate(row)


def _require_project(project_id: str) -> None:
    if not query_one("SELECT id FROM projects WHERE id = ?", (project_id,)):
        raise HTTPException(status_code=404, detail="Project not found.")


@router.get("")
async def list_backgrounds(project_id: str | None = None) -> list[dict[str, Any]]:
    if project_id:
        rows = query(
            "SELECT * FROM backgrounds WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        )
    else:
        rows = query("SELECT * FROM backgrounds ORDER BY created_at DESC")
    return [_decorate(row) for row in rows]


@router.post("", status_code=201)
async def create_background(payload: BackgroundCreate) -> dict[str, Any]:
    _require_project(payload.project_id)
    background_id = uuid.uuid4().hex[:12]
    execute(
        """INSERT INTO backgrounds
           (id, project_id, name, description, aspect_ratio, width, height, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            background_id,
            payload.project_id,
            payload.name.strip(),
            payload.description.strip(),
            payload.aspect_ratio,
            payload.width,
            payload.height,
            now(),
        ),
    )
    return _get(background_id)


@router.get("/{background_id}")
async def get_background(background_id: str) -> dict[str, Any]:
    return _get(background_id)


@router.patch("/{background_id}")
async def update_background(background_id: str, payload: BackgroundUpdate) -> dict[str, Any]:
    _get(background_id)
    updates: list[str] = []
    params: list[Any] = []
    for field in ("name", "description", "aspect_ratio"):
        value = getattr(payload, field)
        if value is not None:
            updates.append(f"{field} = ?")
            params.append(value.strip())
    for field in ("width", "height"):
        value = getattr(payload, field)
        if value is not None:
            updates.append(f"{field} = ?")
            params.append(value)
    if updates:
        params.append(background_id)
        execute(f"UPDATE backgrounds SET {', '.join(updates)} WHERE id = ?", params)
    return _get(background_id)


@router.get("/{background_id}/media")
async def background_media(background_id: str) -> list[dict[str, Any]]:
    _get(background_id)
    return list_media("background", background_id)


@router.post("/{background_id}/media", status_code=201)
async def attach_background_media(background_id: str, payload: MediaAttach) -> dict[str, Any]:
    background = _get(background_id)
    asset = query_one("SELECT id, project_id FROM assets WHERE id = ?", (payload.asset_id,))
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")
    if asset["project_id"] and background["project_id"] and asset["project_id"] != background["project_id"]:
        raise HTTPException(status_code=400, detail="Asset belongs to a different project.")
    try:
        link = link_asset(
            "background",
            background_id,
            payload.asset_id,
            role="background",
            label=payload.label.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**link, "background_id": background_id}


@router.post("/{background_id}/generate", status_code=202)
async def generate_background(background_id: str, payload: BackgroundGenerateRequest) -> dict[str, Any]:
    background = _get(background_id)
    if not background["project_id"]:
        raise HTTPException(status_code=400, detail="Background is not attached to a project.")

    prompt = background_prompt(background, payload.prompt)
    use_preset = bool(payload.use_preset and payload.width is None and payload.height is None)
    try:
        job = await submit_image(
            project_id=background["project_id"],
            prompt=prompt,
            negative_prompt=payload.negative_prompt or BACKGROUND_NEGATIVE,
            width=None if use_preset else (payload.width or background["width"]),
            height=None if use_preset else (payload.height or background["height"]),
            steps=payload.steps,
            cfg=payload.cfg,
            seed=payload.seed,
            workflow_id=payload.workflow_id,
            architecture=payload.architecture,
            checkpoint=payload.checkpoint,
            vae=payload.vae,
            lora_name=payload.lora_name,
            lora_strength=payload.lora_strength,
            purpose="background",
            attach={
                "owner_type": "background",
                "owner_id": background_id,
                "role": "background",
                "label": background["aspect_ratio"],
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job": job, "background_id": background_id, "prompt": prompt, "model": job.get("model")}


@router.get("/{background_id}/jobs")
async def background_jobs(background_id: str, limit: int = 20) -> list[dict[str, Any]]:
    _get(background_id)
    from ..services.jobs import list_jobs

    matches = [
        job
        for job in list_jobs(limit=200)
        if ((job.get("params") or {}).get("attach") or {}).get("owner_id") == background_id
    ]
    return matches[: min(limit, 100)]
