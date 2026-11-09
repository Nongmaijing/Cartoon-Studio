from __future__ import annotations

from pathlib import Path
from typing import Any

from ..comfy.client import ComfyClient
from ..config import load_config
from ..workflows.registry import find_workflow, list_workflows, load_workflow
from .assets import asset_file
from .creative import VIDEO_NEGATIVE
from .jobs import runner
from .model_config_service import apply_model_to_params, resolve_image_model, validate_dimensions

VIDEO_DEFAULTS: dict[str, Any] = {
    "width": 832,
    "height": 480,
    "steps": 20,
    "cfg": 5.0,
    "sampler": "uni_pc",
    "scheduler": "simple",
    "length": 121,
    "fps": 24.0,
    "batch_size": 1,
}


def _runnable(entry: dict[str, Any] | None, kind: str) -> dict[str, Any]:
    if not entry:
        raise ValueError("The selected workflow was not found.")
    if entry["format"] != "api":
        raise ValueError("The selected workflow is not a ComfyUI API-format workflow.")
    if not entry["valid"]:
        raise ValueError("; ".join(entry["errors"]) or "The selected workflow is not valid.")
    if entry["kind"] != kind:
        raise ValueError(f"This workflow produces '{entry['kind']}' output, not '{kind}'.")
    return entry


def image_workflow(
    config: dict[str, Any],
    workflow_id: str | None = None,
    require_input_image: bool = False,
) -> dict[str, Any]:
    """Pick an explicitly requested workflow or a matching default image workflow."""
    if workflow_id:
        entry = _runnable(find_workflow(config, workflow_id), "image")
        has_input = _has_input_image(config, entry["id"])
        if require_input_image and not has_input:
            raise ValueError("The selected workflow does not accept a reference image. Choose an image-to-image workflow.")
        if not require_input_image and has_input:
            raise ValueError("The selected workflow needs a reference image. Choose a text-to-image workflow.")
        return entry

    if require_input_image:
        preferred_ids = ["sd15_img2img"]
    else:
        preferred_ids = [
            config["generation"].get("default_workflow") or "sd15_txt2img",
            "sd15_txt2img",
        ]
    for preferred in dict.fromkeys(preferred_ids):
        entry = find_workflow(config, preferred)
        if (
            entry
            and entry["format"] == "api"
            and entry["valid"]
            and entry["kind"] == "image"
            and _has_input_image(config, entry["id"]) == require_input_image
        ):
            return entry

    for candidate in list_workflows(config):
        if candidate["format"] != "api" or not candidate["valid"] or candidate["kind"] != "image":
            continue
        if _has_input_image(config, candidate["id"]) == require_input_image:
            return candidate
    mode = "image-to-image" if require_input_image else "text-to-image"
    raise ValueError(f"No runnable {mode} workflow is available.")


def _has_input_image(config: dict[str, Any], workflow_id: str) -> bool:
    loaded = load_workflow(config, workflow_id)
    return "input_image" in (loaded["mapping"].get("roles") or {})


def video_workflow(
    config: dict[str, Any],
    workflow_id: str | None = None,
    require_input_image: bool = False,
) -> dict[str, Any]:
    """Pick a video workflow, respecting whether a start image is available."""
    if workflow_id:
        entry = _runnable(find_workflow(config, workflow_id), "video")
        has_input = _has_input_image(config, entry["id"])
        if require_input_image and not has_input:
            raise ValueError("The selected workflow does not accept a start image. Choose an image-to-video workflow.")
        if not require_input_image and has_input:
            raise ValueError(
                "The selected workflow needs a start image. Choose a keyframe, or use a text-to-video workflow."
            )
        return entry

    preferred = "wan22_i2v" if require_input_image else "wan22_t2v"
    entry = find_workflow(config, preferred)
    if entry and entry["format"] == "api" and entry["valid"] and entry["kind"] == "video":
        return entry

    for candidate in list_workflows(config):
        if candidate["format"] != "api" or not candidate["valid"] or candidate["kind"] != "video":
            continue
        if _has_input_image(config, candidate["id"]) == require_input_image:
            return candidate
    mode = "image-to-video" if require_input_image else "text-to-video"
    raise ValueError(f"No runnable {mode} workflow is available.")


async def submit_image(
    *,
    project_id: str,
    prompt: str,
    attach: dict[str, str],
    negative_prompt: str | None = None,
    width: int | None = None,
    height: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    seed: int | None = None,
    workflow_id: str | None = None,
    scene_id: str | None = None,
    input_image: str | None = None,
    denoise: float | None = None,
    control_strength: float | None = None,
    control_net_name: str | None = None,
    architecture: str | None = None,
    purpose: str = "scene",
    preset: str | None = None,
    checkpoint: str | None = None,
    vae: str | None = None,
    lora_name: str | None = None,
    lora_strength: float | None = None,
    extra_params: dict[str, Any] | None = None,
    priority: int = 0,
) -> dict[str, Any]:
    config = load_config()
    model = resolve_image_model(
        config,
        architecture=architecture,
        purpose=purpose,
        input_image=bool(input_image),
        explicit=bool(architecture),
        preset=preset,
    )
    selected_workflow = workflow_id or model["workflow_id"]
    entry = image_workflow(config, selected_workflow, require_input_image=bool(input_image))
    generation = config["generation"]
    params: dict[str, Any] = {
        "positive_prompt": prompt,
        "negative_prompt": negative_prompt or generation.get("negative_prompt"),
        "seed": seed if seed is not None else -1,
        "scene_id": scene_id,
        "denoise": denoise,
        "control_strength": control_strength,
        "control_net_name": control_net_name,
        "attach": attach,
    }
    if width is not None:
        params["width"] = width
    if height is not None:
        params["height"] = height
    if steps is not None:
        params["steps"] = steps
    if cfg is not None:
        params["cfg"] = cfg
    if input_image:
        params["input_image"] = input_image
    if checkpoint:
        model["checkpoint"] = checkpoint
    if vae is not None:
        model["vae"] = vae
    if lora_name is not None:
        model["lora_name"] = lora_name
    if lora_strength is not None:
        model["lora_strength"] = lora_strength
    apply_model_to_params(params, model)
    params.setdefault("width", generation.get("width", 512))
    params.setdefault("height", generation.get("height", 512))
    params.setdefault("steps", generation.get("steps", 20))
    params.setdefault("cfg", generation.get("cfg", 7.0))
    params.setdefault("sampler", generation.get("sampler", "euler"))
    params.setdefault("scheduler", generation.get("scheduler", "normal"))
    params.setdefault("batch_size", 1)
    if extra_params:
        params.update(extra_params)
    if priority:
        params["priority"] = priority
    validate_dimensions(model, int(params["width"]), int(params["height"]))
    job = await runner.submit(
        project_id=project_id,
        workflow_id=entry["id"],
        workflow_name=entry["name"],
        params=params,
        priority=priority,
    )
    job["model"] = {
        "architecture": model["architecture"],
        "checkpoint": model["checkpoint"],
        "vae": model.get("vae") or None,
        "lora_name": model.get("lora_name") or None,
        "workflow_id": entry["id"],
        "fallback": model.get("fallback_reason"),
        "low_vram": model.get("low_vram"),
        "tiled_vae": model.get("tiled_vae"),
    }
    return job


async def submit_video(
    *,
    project_id: str,
    prompt: str,
    attach: dict[str, str],
    scene_id: str | None = None,
    negative_prompt: str | None = None,
    width: int | None = None,
    height: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    seed: int | None = None,
    length: int | None = None,
    fps: float | None = None,
    sampler: str | None = None,
    scheduler: str | None = None,
    input_image: str | None = None,
    workflow_id: str | None = None,
    priority: int = 0,
) -> dict[str, Any]:
    config = load_config()
    entry = video_workflow(config, workflow_id, require_input_image=bool(input_image))
    params: dict[str, Any] = {
        "positive_prompt": prompt,
        "negative_prompt": negative_prompt or VIDEO_NEGATIVE,
        "width": width or VIDEO_DEFAULTS["width"],
        "height": height or VIDEO_DEFAULTS["height"],
        "steps": steps or VIDEO_DEFAULTS["steps"],
        "cfg": cfg if cfg is not None else VIDEO_DEFAULTS["cfg"],
        "sampler": sampler or VIDEO_DEFAULTS["sampler"],
        "scheduler": scheduler or VIDEO_DEFAULTS["scheduler"],
        "length": length or VIDEO_DEFAULTS["length"],
        "fps": fps or VIDEO_DEFAULTS["fps"],
        "batch_size": 1,
        "seed": seed if seed is not None else -1,
        "input_image": input_image,
        "scene_id": scene_id,
        "attach": attach,
    }
    if priority:
        params["priority"] = priority
    return await runner.submit(
        project_id=project_id,
        workflow_id=entry["id"],
        workflow_name=entry["name"],
        params=params,
        priority=priority,
    )


async def upload_start_image(
    config: dict[str, Any],
    client: ComfyClient,
    asset_id: str,
    project_id: str,
) -> str:
    """Copy a project image into ComfyUI's input folder and return its LoadImage name."""
    resolved = asset_file(asset_id)
    if not resolved:
        raise ValueError("Start image asset was not found on disk.")
    path, asset = resolved
    if asset["project_id"] and asset["project_id"] != project_id:
        raise ValueError("Start image belongs to a different project.")
    if asset["kind"] != "image":
        raise ValueError("Start image must be an image asset.")

    suffix = Path(asset["filename"]).suffix.lower() or ".png"
    name = f"cartoon_studio_{asset_id}{suffix}"
    result = await client.upload_image(path.read_bytes(), name)
    uploaded = str(result.get("name") or name)
    subfolder = str(result.get("subfolder") or "")
    return f"{subfolder}/{uploaded}" if subfolder else uploaded
