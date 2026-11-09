from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..comfy.client import ComfyClient, ComfyError
from ..comfy.discovery import discover_comfy
from ..config import load_config, save_config

router = APIRouter(prefix="/api/comfy", tags=["comfyui"])


def _client(config: dict) -> ComfyClient:
    return ComfyClient(
        config["comfyui"]["server_url"],
        timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
    )


@router.get("/test")
async def test_connection() -> dict:
    config = load_config()
    client = _client(config)
    try:
        stats = await client.system_stats()
        queue = await client.queue()
        object_info = await client.object_info()
    except ComfyError as exc:
        return {
            "connected": False,
            "server_url": config["comfyui"]["server_url"],
            "error": str(exc),
        }
    system = stats.get("system") or {}
    device = (stats.get("devices") or [{}])[0]
    return {
        "connected": True,
        "server_url": config["comfyui"]["server_url"],
        "version": system.get("comfyui_version"),
        "python": system.get("python_version"),
        "pytorch": system.get("pytorch_version"),
        "os": system.get("os"),
        "ram_total": system.get("ram_total"),
        "ram_free": system.get("ram_free"),
        "device": device.get("name"),
        "vram_total": device.get("vram_total"),
        "vram_free": device.get("vram_free"),
        "queue_running": len(queue.get("queue_running") or []),
        "queue_pending": len(queue.get("queue_pending") or []),
        "node_count": len(object_info),
    }


@router.get("/discovery")
async def discovery() -> dict:
    config = load_config()
    info = discover_comfy(config)
    changed = False
    if info["install_path"] and not config["comfyui"].get("install_path"):
        config["comfyui"]["install_path"] = info["install_path"]
        changed = True
    if info["output_dir"] and not config["comfyui"].get("output_dir"):
        config["comfyui"]["output_dir"] = info["output_dir"]
        changed = True
    if info["model_dirs"] and not config["comfyui"].get("models_dirs"):
        config["comfyui"]["models_dirs"] = info["model_dirs"]
        changed = True
    if changed:
        save_config(config)
    return info


@router.get("/models")
async def models() -> dict:
    config = load_config()
    client = _client(config)
    try:
        object_info = await client.object_info()
    except ComfyError as exc:
        raise HTTPException(status_code=503, detail=f"ComfyUI unavailable: {exc}") from exc

    def options(class_type: str, input_name: str) -> list:
        node = object_info.get(class_type) or {}
        spec = (((node.get("input") or {}).get("required") or {}).get(input_name))
        if not spec:
            return []
        values = spec[0]
        return values if isinstance(values, list) else []

    return {
        "checkpoints": options("CheckpointLoaderSimple", "ckpt_name"),
        "diffusion_models": options("UNETLoader", "unet_name"),
        "text_encoders": options("CLIPLoader", "clip_name"),
        "vaes": options("VAELoader", "vae_name"),
        "samplers": options("KSampler", "sampler_name"),
        "schedulers": options("KSampler", "scheduler"),
    }


@router.get("/queue")
async def queue() -> dict:
    config = load_config()
    try:
        data = await _client(config).queue()
    except ComfyError as exc:
        raise HTTPException(status_code=503, detail=f"ComfyUI unavailable: {exc}") from exc
    return {
        "running": len(data.get("queue_running") or []),
        "pending": len(data.get("queue_pending") or []),
    }


@router.get("/object-info/{node}")
async def object_info(node: str) -> dict:
    config = load_config()
    try:
        return await _client(config).object_info(node)
    except ComfyError as exc:
        raise HTTPException(status_code=503, detail=f"ComfyUI unavailable: {exc}") from exc
