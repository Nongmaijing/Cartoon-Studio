from __future__ import annotations

from fastapi import APIRouter

from ..comfy.client import ComfyClient, ComfyError
from ..config import load_config
from ..db import query_one
from ..services.assets import list_assets
from ..services.jobs import current_job, list_jobs
from ..services.stats import system_stats

router = APIRouter(prefix="/api", tags=["dashboard"])


def _count(table: str, where: str = "") -> int:
    row = query_one(f"SELECT COUNT(*) AS n FROM {table} {where}")
    return int(row["n"]) if row else 0


@router.get("/dashboard")
async def dashboard() -> dict:
    config = load_config()
    client = ComfyClient(
        config["comfyui"]["server_url"],
        timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
    )
    comfy: dict = {"connected": False, "server_url": config["comfyui"]["server_url"]}
    try:
        stats = await client.system_stats()
        comfy.update(
            connected=True,
            version=(stats.get("system") or {}).get("comfyui_version"),
            ram_total=(stats.get("system") or {}).get("ram_total"),
            ram_free=(stats.get("system") or {}).get("ram_free"),
            devices=stats.get("devices") or [],
        )
    except ComfyError as exc:
        comfy["error"] = str(exc)

    return {
        "counts": {
            "projects": _count("projects", "WHERE archived = 0"),
            "characters": _count("characters"),
            "backgrounds": _count("backgrounds"),
            "scenes": _count("scenes"),
            "episodes": _count("episodes", "WHERE status = 'completed'"),
            "assets": _count("assets"),
            "jobs_completed": _count("jobs", "WHERE status = 'completed'"),
        },
        "comfyui": comfy,
        "system": system_stats(),
        "current_job": current_job(),
        "recent_jobs": list_jobs(limit=10),
        "recent_assets": list_assets(limit=12),
    }
