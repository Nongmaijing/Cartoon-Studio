from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..comfy.client import ComfyClient, ComfyError
from ..config import load_config
from ..db import query_one
from ..schemas import AnimationGenerateRequest
from ..services.engines import detect_engines
from ..services.generation import submit_video, upload_start_image
from ..services.jobs import list_jobs
from ..services.workflow_checks import workflow_readiness
from ..workflows.registry import list_workflows

router = APIRouter(prefix="/api/animation", tags=["animation"])


def _client(config: dict[str, Any]) -> ComfyClient:
    return ComfyClient(
        config["comfyui"]["server_url"],
        timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
    )


@router.get("/engines")
async def engines() -> dict[str, Any]:
    config = load_config()
    try:
        object_info = await _client(config).object_info()
    except ComfyError as exc:
        raise HTTPException(status_code=503, detail=f"ComfyUI unavailable: {exc}") from exc
    result = detect_engines(object_info)
    video_workflows = []
    for entry in list_workflows(config):
        if entry["format"] != "api" or entry["kind"] != "video":
            continue
        item = {
            "id": entry["id"],
            "name": entry["name"],
            "engine": entry["engine"],
            "valid": entry["valid"],
            "errors": entry["errors"],
            "runnable": False,
            "missing_nodes": [],
        }
        if entry["valid"]:
            try:
                readiness = workflow_readiness(config, entry, object_info)
                item["runnable"] = readiness["runnable"]
                item["missing_nodes"] = readiness["missing_nodes"]
                item["models"] = readiness["models"]
            except Exception as exc:  # noqa: BLE001
                item["errors"].append(str(exc))
        video_workflows.append(item)
    result["workflows"] = video_workflows
    return result


@router.post("/generate", status_code=202)
async def generate_animation(payload: AnimationGenerateRequest) -> dict[str, Any]:
    config = load_config()
    if not query_one("SELECT id FROM projects WHERE id = ?", (payload.project_id,)):
        raise HTTPException(status_code=404, detail="Project not found.")

    if payload.scene_id:
        scene = query_one(
            "SELECT id FROM scenes WHERE id = ? AND project_id = ?",
            (payload.scene_id, payload.project_id),
        )
        if not scene:
            raise HTTPException(status_code=400, detail="Scene is not part of this project.")

    input_image = None
    try:
        if payload.start_image:
            input_image = await upload_start_image(
                config,
                _client(config),
                payload.start_image,
                payload.project_id,
            )
        job = await submit_video(
            project_id=payload.project_id,
            prompt=payload.prompt,
            negative_prompt=payload.negative_prompt,
            width=payload.width,
            height=payload.height,
            steps=payload.steps,
            cfg=payload.cfg,
            seed=payload.seed,
            length=payload.length,
            fps=payload.fps,
            sampler=payload.sampler,
            scheduler=payload.scheduler,
            input_image=input_image,
            workflow_id=payload.workflow_id,
            scene_id=payload.scene_id,
            attach=(
                {
                    "owner_type": "scene",
                    "owner_id": payload.scene_id,
                    "role": "video",
                    "label": "animation",
                }
                if payload.scene_id
                else {}
            ),
        )
    except (ValueError, ComfyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "job": job,
        "mode": "image-to-video" if input_image else "text-to-video",
        "input_image": input_image,
    }


@router.get("/jobs")
async def animation_jobs(project_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    config = load_config()
    video_ids = {
        entry["id"]
        for entry in list_workflows(config)
        if entry["format"] == "api" and entry["kind"] == "video"
    }
    jobs = list_jobs(limit=min(limit * 3, 300), project_id=project_id)
    return [job for job in jobs if job["workflow_id"] in video_ids][: min(limit, 100)]
