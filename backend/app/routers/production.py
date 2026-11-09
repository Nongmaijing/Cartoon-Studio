from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..config import load_config
from ..core.security import rate_limiter
from ..providers.registry import registry
from ..schemas_ai import ApprovalRequest, ProductionRegenerateRequest, ProductionStartRequest
from ..services import production_service, quality_control_service, scene_service
from ..services.errors import ServiceError

router = APIRouter(prefix="/api/v1/production", tags=["production"])


def _raise(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/start", status_code=202)
async def start(payload: ProductionStartRequest) -> dict[str, Any]:
    limit = int((load_config().get("security") or {}).get("rate_limit_per_minute", 60))
    try:
        await rate_limiter.check(f"production:{payload.episode_id}", limit)
        return production_service.start_production(
            payload.project_id,
            payload.episode_id,
            plan=payload.plan,
            actor="user",
            confirm=payload.confirm,
            idempotency_key=payload.idempotency_key,
        )
    except ServiceError as exc:
        _raise(exc)


@router.post("/pause/{run_id}")
async def pause(run_id: str) -> dict[str, Any]:
    try:
        return production_service.pause_production(run_id, actor="user")
    except ServiceError as exc:
        _raise(exc)


@router.post("/resume/{run_id}")
async def resume(run_id: str) -> dict[str, Any]:
    try:
        return production_service.resume_production(run_id, actor="user")
    except ServiceError as exc:
        _raise(exc)


@router.post("/cancel/{run_id}")
async def cancel(run_id: str, payload: ApprovalRequest | None = None) -> dict[str, Any]:
    try:
        return production_service.cancel_production(run_id, actor="user", confirm=True)
    except ServiceError as exc:
        _raise(exc)


@router.get("/status/{run_id}")
async def status(run_id: str) -> dict[str, Any]:
    try:
        return production_service.get_status(run_id)
    except ServiceError as exc:
        _raise(exc)


@router.get("/queue")
async def queue(project_id: str | None = None) -> list[dict[str, Any]]:
    return production_service.get_queue(project_id)


@router.get("/overview")
async def overview(project_id: str | None = None) -> dict[str, Any]:
    scenes = scene_service.list_scenes(project_id) if project_id else []
    completed = [scene for scene in scenes if scene.get("approval_status") == "approved" or scene.get("keyframe_count")]
    failed = [scene for scene in scenes if scene.get("approval_status") == "rejected" or (scene.get("quality") or {}).get("status") == "failed"]
    runs = production_service.get_queue(project_id)
    provider_status = await registry.status()
    return {
        "project_id": project_id,
        "scenes": {
            "total": len(scenes),
            "completed": len(completed),
            "pending": max(0, len(scenes) - len(completed) - len(failed)),
            "failed": len(failed),
        },
        "production_runs": {
            "running": sum(1 for run in runs if run["status"] == "running"),
            "paused": sum(1 for run in runs if run["status"] == "paused"),
            "failed": sum(1 for run in runs if run["status"] == "failed"),
            "completed": sum(1 for run in runs if run["status"] == "completed"),
            "recent": [
                {
                    "run_id": run["run_id"],
                    "episode_id": run["episode_id"],
                    "state": run["state"],
                    "status": run["status"],
                    "progress": run["progress"],
                    "current_stage": run.get("current_stage"),
                }
                for run in runs[:10]
            ],
        },
        "providers": provider_status,
    }


@router.get("/jobs/{job_id}")
async def job_status(job_id: str) -> dict[str, Any]:
    return production_service.get_job_status(job_id)


@router.get("/logs/{run_id}")
async def logs(run_id: str, limit: int = 200) -> dict[str, Any]:
    try:
        return production_service.get_logs(run_id, limit)
    except ServiceError as exc:
        _raise(exc)


@router.post("/regenerate-failed/{episode_id}")
async def regenerate_failed(episode_id: str, payload: ProductionRegenerateRequest) -> dict[str, Any]:
    try:
        return production_service.regenerate_failed_scenes(episode_id, actor="user", confirm=payload.confirm)
    except ServiceError as exc:
        _raise(exc)


@router.post("/scenes/{scene_id}/approve")
async def approve_scene(scene_id: str, payload: ApprovalRequest | None = None) -> dict[str, Any]:
    try:
        return scene_service.approve_scene(scene_id, actor="user", notes=(payload.notes if payload else ""))
    except ServiceError as exc:
        _raise(exc)


@router.post("/scenes/{scene_id}/reject")
async def reject_scene(scene_id: str, payload: ApprovalRequest | None = None) -> dict[str, Any]:
    try:
        return scene_service.reject_scene(scene_id, actor="user", notes=(payload.notes if payload else ""))
    except ServiceError as exc:
        _raise(exc)


@router.post("/scenes/{scene_id}/review")
async def review_scene(scene_id: str) -> dict[str, Any]:
    try:
        return quality_control_service.review_scene(scene_id, actor="user")
    except ServiceError as exc:
        _raise(exc)
