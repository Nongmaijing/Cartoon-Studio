from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from ..comfy.client import ComfyClient, ComfyError
from ..config import load_config
from .assets import asset_file
from .generation import submit_image, upload_start_image

EDIT_NEGATIVE = (
    "photo, photorealistic, 3d render, blurry, low quality, deformed, extra limbs, "
    "watermark, text, signature, logo, cropped, jpeg artifacts, visible seam"
)


def comfy_client(config: dict[str, Any]) -> ComfyClient:
    return ComfyClient(
        config["comfyui"]["server_url"],
        timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
    )


def _target_size(path: Path, max_pixels: int) -> tuple[int, int]:
    with Image.open(path) as image:
        width, height = image.size
    scale = min(1.0, (max_pixels / max(1, width * height)) ** 0.5)
    width = max(64, int(width * scale) // 8 * 8)
    height = max(64, int(height * scale) // 8 * 8)
    return width, height


async def inpaint_checkpoint(config: dict[str, Any], client: ComfyClient | None = None) -> str:
    """Return a ComfyUI-visible SDXL inpainting checkpoint, or an empty string."""
    configured = str((config.get("models", {}).get("checkpoints") or {}).get("sdxl_inpaint") or "")
    if configured:
        return configured
    client = client or comfy_client(config)
    try:
        info = await client.object_info()
    except ComfyError:
        return ""
    options = (
        ((info.get("CheckpointLoaderSimple") or {}).get("input") or {})
        .get("required", {})
        .get("ckpt_name", [])
        or []
    )
    choices = options[0] if options and isinstance(options[0], list) else []
    for name in choices:
        lowered = str(name).lower()
        if "inpaint" in lowered and ("xl" in lowered or "sdxl" in lowered):
            return str(name)
    return ""


async def edit_image(
    *,
    source_asset_id: str,
    prompt: str,
    mask_asset_id: str | None = None,
    negative_prompt: str | None = None,
    seed: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    denoise: float = 0.55,
    width: int | None = None,
    height: int | None = None,
    attach: dict[str, str] | None = None,
) -> dict[str, Any]:
    config = load_config()
    resolved = asset_file(source_asset_id)
    if not resolved:
        raise ValueError("Source image asset was not found on disk.")
    path, asset = resolved
    if asset.get("kind") != "image" and not str(asset.get("mime") or "").startswith("image/"):
        raise ValueError("Only image assets can be edited.")
    project_id = asset.get("project_id")
    if not project_id:
        raise ValueError("Source image is not attached to a project.")

    client = comfy_client(config)
    input_name = await upload_start_image(config, client, source_asset_id, project_id)
    mask_name = None
    checkpoint: str | None = None
    workflow_id = "sdxl_img2img"
    if mask_asset_id:
        mask_resolved = asset_file(mask_asset_id)
        if not mask_resolved:
            raise ValueError("Mask asset was not found on disk.")
        mask_path, mask_asset = mask_resolved
        if mask_asset.get("kind") != "image":
            raise ValueError("Mask must be an image asset.")
        if mask_asset.get("project_id") != project_id:
            raise ValueError("Mask belongs to a different project.")
        mask_name = await upload_start_image(config, client, mask_asset_id, project_id)
        checkpoint = await inpaint_checkpoint(config, client)
        if not checkpoint:
            raise ValueError(
                "Masked editing needs an SDXL inpainting checkpoint. Install one and select it "
                "as the SDXL inpainting checkpoint, or run a whole-image edit without a mask."
            )
        workflow_id = "sdxl_inpaint"
        denoise = 1.0

    if width is None or height is None:
        max_pixels = int((config.get("models") or {}).get("max_pixels") or 1250000)
        width, height = _target_size(path, max_pixels)

    return await submit_image(
        project_id=project_id,
        prompt=prompt,
        attach=attach
        or {
            "owner_type": "project",
            "owner_id": project_id,
            "role": "edit",
            "label": "edited",
        },
        negative_prompt=negative_prompt or EDIT_NEGATIVE,
        width=width,
        height=height,
        steps=steps,
        cfg=cfg,
        seed=seed,
        workflow_id=workflow_id,
        input_image=input_name,
        mask_image=mask_name,
        denoise=denoise,
        architecture="sdxl",
        purpose="edit",
        checkpoint=checkpoint,
        extra_params={
            "edit": {
                "source_asset_id": source_asset_id,
                "mask_asset_id": mask_asset_id,
                "mode": "masked" if mask_name else "whole-image",
            }
        },
    )

