from __future__ import annotations

import time
from typing import Any

import psutil

from ..comfy.client import ComfyClient, ComfyError
from ..config import load_config
from ..workflows.registry import find_workflow, load_workflow


def _client(config: dict[str, Any]) -> ComfyClient:
    return ComfyClient(
        config["comfyui"]["server_url"],
        timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
    )


def _gpu(stats: dict[str, Any]) -> dict[str, Any]:
    device = (stats.get("devices") or [{}])[0]
    total = int(device.get("vram_total") or 0)
    free = int(device.get("vram_free") or 0)
    return {
        "name": device.get("name") or "",
        "type": device.get("type") or "",
        "vram_total": total,
        "vram_free": free,
        "vram_used": max(0, total - free),
        "vram_total_gb": round(total / (1024**3), 2) if total else None,
        "vram_free_gb": round(free / (1024**3), 2) if free else None,
        "vram_used_gb": round(max(0, total - free) / (1024**3), 2) if total else None,
    }


def classify_workflow(config: dict[str, Any], workflow_id: str | None) -> dict[str, Any]:
    if not workflow_id:
        return {"kind": "unknown", "engine": "unknown", "resource_class": "gpu_image"}
    entry = find_workflow(config, workflow_id)
    if not entry:
        return {"kind": "unknown", "engine": "unknown", "resource_class": "gpu_image"}
    kind = str(entry.get("kind") or "unknown")
    engine = str(entry.get("engine") or "unknown")
    if kind == "video":
        resource_class = "gpu_video"
    elif kind == "audio":
        resource_class = "cpu_audio"
    elif engine == "ffmpeg" or kind == "editing":
        resource_class = "cpu_edit"
    else:
        resource_class = "gpu_image"
    return {"kind": kind, "engine": engine, "resource_class": resource_class}


def estimate_job(config: dict[str, Any], workflow_id: str | None, params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    info = classify_workflow(config, workflow_id)
    engine = info["engine"]
    kind = info["kind"]
    width = int(params.get("width") or 1024)
    height = int(params.get("height") or 1024)
    steps = int(params.get("steps") or 28)
    pixels = max(1, width * height)
    if kind == "video":
        frames = int(params.get("length") or 121)
        vram_gb = 5.8
        seconds = max(30.0, frames * steps * 0.35)
    elif kind == "audio":
        vram_gb = 0.0
        seconds = 5.0
    elif engine == "ffmpeg" or kind == "editing":
        vram_gb = 0.0
        seconds = 15.0
    elif engine == "sdxl":
        vram_gb = 5.4 if pixels <= 1_250_000 else 6.0
        seconds = max(8.0, steps * 1.4 + 8)
    elif engine == "sd15":
        vram_gb = 3.5
        seconds = max(5.0, steps * 0.55 + 4)
    else:
        vram_gb = 4.0
        seconds = max(8.0, steps * 1.0 + 5)
    return {
        **info,
        "workflow_id": workflow_id,
        "width": width,
        "height": height,
        "steps": steps,
        "estimated_seconds": round(seconds, 1),
        "estimated_vram_gb": vram_gb,
        "fits_6gb": vram_gb <= 5.9,
        "note": (
            "Estimated for the RTX 4050 6 GB profile. Actual time varies with model size, offloading and ComfyUI flags."
        ),
    }


async def snapshot() -> dict[str, Any]:
    config = load_config()
    client = _client(config)
    stats: dict[str, Any] = {}
    queue: dict[str, Any] = {}
    connected = False
    error: str | None = None
    try:
        stats = await client.system_stats()
        queue = await client.queue()
        connected = True
    except ComfyError as exc:
        error = str(exc)
    memory = psutil.virtual_memory()
    gpu = _gpu(stats)
    running = queue.get("queue_running") or []
    pending = queue.get("queue_pending") or []
    return {
        "comfyui": {
            "connected": connected,
            "error": error,
            "version": (stats.get("system") or {}).get("comfyui_version"),
            "argv": (stats.get("system") or {}).get("argv") or [],
        },
        "gpu": gpu,
        "ram": {
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "used_gb": round((memory.total - memory.available) / (1024**3), 2),
            "percent": memory.percent,
        },
        "queue": {
            "running": len(running),
            "pending": len(pending),
            "running_ids": [str(item[1]) if isinstance(item, (list, tuple)) and len(item) > 1 else None for item in running],
        },
        "recommendation": (
            "Use --lowvram for SDXL/video on 6 GB. Free VRAM between model families."
            if gpu.get("vram_total_gb") and gpu["vram_total_gb"] < 8
            else "VRAM headroom is adequate for the configured profiles."
        ),
        "captured_at": time.time(),
    }


async def free_vram() -> dict[str, Any]:
    config = load_config()
    client = _client(config)
    try:
        await client.free_memory(unload_models=True, free_memory=True)
    except ComfyError as exc:
        return {"ok": False, "error": str(exc), "status": await snapshot()}
    return {"ok": True, "status": await snapshot()}


async def current_vram_used_mb() -> int | None:
    config = load_config()
    try:
        stats = await _client(config).system_stats()
    except ComfyError:
        return None
    device = (stats.get("devices") or [{}])[0]
    total = int(device.get("vram_total") or 0)
    free = int(device.get("vram_free") or 0)
    if not total:
        return None
    return max(0, (total - free) // (1024 * 1024))


def oom_advice(error: str) -> str:
    lowered = (error or "").lower()
    if "out of memory" in lowered or "cuda error" in lowered or "allocation" in lowered:
        return (
            " The GPU ran out of memory. Use a smaller resolution, batch size 1, tiled VAE, "
            "restart ComfyUI with --lowvram, and free VRAM before retrying."
        )
    return ""
