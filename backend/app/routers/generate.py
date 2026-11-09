from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..config import load_config
from ..db import query_one
from ..schemas import GenerateRequest
from ..services.jobs import get_job, list_jobs, queue_state, runner
from ..workflows.registry import find_workflow

router = APIRouter(prefix="/api", tags=["generation"])


@router.post("/generate", status_code=202)
async def generate(payload: GenerateRequest) -> dict:
    config = load_config()
    if not query_one("SELECT id FROM projects WHERE id = ?", (payload.project_id,)):
        raise HTTPException(status_code=404, detail="Project not found.")

    entry = find_workflow(config, payload.workflow_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    if entry["format"] != "api":
        raise HTTPException(status_code=400, detail="Workflow is not in ComfyUI API format.")
    if not entry["valid"]:
        raise HTTPException(status_code=400, detail="; ".join(entry["errors"]) or "Workflow is not valid.")

    generation = config["generation"]
    params: dict = {
        "positive_prompt": payload.prompt,
        "negative_prompt": payload.negative_prompt or generation.get("negative_prompt"),
        "seed": payload.seed if payload.seed is not None else generation.get("seed", -1),
        "scene_id": payload.scene_id,
    }

    if entry["kind"] == "image":
        params.update(
            {
                "width": payload.width or generation.get("width", 512),
                "height": payload.height or generation.get("height", 512),
                "steps": payload.steps or generation.get("steps", 20),
                "cfg": payload.cfg if payload.cfg is not None else generation.get("cfg", 7.0),
                "sampler": payload.sampler or generation.get("sampler", "euler"),
                "scheduler": payload.scheduler or generation.get("scheduler", "normal"),
                "batch_size": payload.batch_size or generation.get("batch_size", 1),
            }
        )
    else:
        for key in ("width", "height", "steps", "cfg", "sampler", "scheduler", "batch_size", "length", "fps", "input_image", "output_format"):
            value = getattr(payload, key)
            if value is not None:
                params[key] = value

    job = await runner.submit(
        project_id=payload.project_id,
        workflow_id=payload.workflow_id,
        workflow_name=entry["name"],
        params=params,
    )
    return job


@router.get("/jobs")
async def jobs(limit: int = 50, status: str | None = None, project_id: str | None = None) -> list[dict]:
    return list_jobs(limit=min(limit, 200), status=status, project_id=project_id)


@router.get("/jobs/queue")
async def queue() -> dict:
    return queue_state()


@router.get("/jobs/{job_id}")
async def job(job_id: str) -> dict:
    result = get_job(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found.")
    return result


@router.post("/jobs/{job_id}/cancel")
async def cancel(job_id: str) -> dict:
    result = get_job(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found.")
    status = await runner.cancel(job_id)
    return {"job_id": job_id, "status": status}
