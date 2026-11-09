from __future__ import annotations

from typing import Any

from .engines import detect_engines


def controlnet_ready(object_info: dict[str, Any]) -> bool:
    """True only when ControlNet nodes *and* model files are available."""
    return bool(detect_engines(object_info)["controlnet"]["available"])


def controlnet_model(object_info: dict[str, Any]) -> str | None:
    """Return the first ControlNet model file ComfyUI can actually load."""
    models = detect_engines(object_info)["controlnet"].get("models") or {}
    preferred = [
        options
        for key, options in models.items()
        if key.endswith(".control_net_name") and options
    ]
    for options in preferred:
        return str(options[0])
    for options in models.values():
        if options:
            return str(options[0])
    return None


def resolve_image_mode(
    object_info: dict[str, Any],
    reference_mode: str,
    has_reference: bool,
) -> str:
    """Choose text-to-image, image-to-image, or ControlNet pose conditioning."""
    if not has_reference:
        return "text-to-image"
    if reference_mode == "pose" and controlnet_ready(object_info):
        return "controlnet-pose"
    return "image-to-image"
