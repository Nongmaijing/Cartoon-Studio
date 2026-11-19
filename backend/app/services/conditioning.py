from __future__ import annotations

from typing import Any

from .engines import detect_engines


def controlnet_ready(object_info: dict[str, Any]) -> bool:
    """True only when ControlNet nodes *and* model files are available."""
    return bool(detect_engines(object_info)["controlnet"]["available"])


def ipadapter_ready(object_info: dict[str, Any]) -> bool:
    """True only when the IP-Adapter node, adapter weights and CLIP vision are present."""
    return bool(detect_engines(object_info)["ipadapter"]["available"])


def ipadapter_workflow_id(
    config: dict[str, Any],
    architecture: str,
    variant: str = "identity",
) -> str | None:
    """Pick a runnable IP-Adapter workflow for the active architecture.

    ``variant="scene"`` prefers the lower-weight scene graph and falls back to the
    identity graph when that file is not installed.
    """
    from ..workflows.registry import find_workflow

    models = config.get("models") or {}
    configured = str((models.get("workflows") or {}).get(f"ipadapter_{variant}_{architecture}") or "")
    candidates = [
        configured,
        f"{architecture}_ipadapter_{variant}",
    ]
    if variant != "identity":
        candidates.append(f"{architecture}_ipadapter_identity")
    for candidate in candidates:
        if not candidate:
            continue
        entry = find_workflow(config, candidate)
        if not entry:
            continue
        roles = set(entry.get("roles") or [])
        if (
            entry.get("format") == "api"
            and entry.get("valid")
            and entry.get("kind") == "image"
            and "input_image" in roles
        ):
            return candidate
    return None


def prefer_ipadapter(requested_workflow: str | None) -> bool:
    """Identity conditioning may replace a plain img2img pick, but never a deliberate graph."""
    if not requested_workflow:
        return True
    return requested_workflow.lower().endswith("_img2img")


def _controlnet_names(object_info: dict[str, Any]) -> list[str]:
    models = detect_engines(object_info)["controlnet"].get("models") or {}
    preferred = [
        str(value)
        for key, options in models.items()
        if key.endswith(".control_net_name")
        for value in options
    ]
    if preferred:
        return preferred
    return [str(value) for options in models.values() for value in options]


def _matches_architecture(name: str, architecture: str) -> bool:
    lowered = name.lower()
    if architecture == "sdxl":
        return "sdxl" in lowered
    if architecture == "sd15":
        return any(hint in lowered for hint in ("sd15", "sd1.5", "sd1-5", "v11"))
    return True


def controlnet_model(object_info: dict[str, Any], architecture: str | None = None) -> str | None:
    """Return a ControlNet model file ComfyUI can load for the given architecture.

    An SDXL graph cannot load an SD1.5 ControlNet file (and vice versa), so when an
    architecture is supplied only matching filenames are eligible. Returns ``None``
    when no compatible file exists; callers should fall back to image-to-image.
    """
    names = _controlnet_names(object_info)
    if architecture:
        for name in names:
            if _matches_architecture(name, architecture):
                return name
        return None
    return names[0] if names else None


def controlnet_workflow_id(config: dict[str, Any], architecture: str) -> str | None:
    """Pick the runnable ControlNet workflow that matches the active architecture."""
    from ..workflows.registry import find_workflow

    models = config.get("models") or {}
    configured = str((models.get("workflows") or {}).get(f"controlnet_pose_{architecture}") or "")
    for candidate in (configured, f"{architecture}_controlnet_pose"):
        if not candidate:
            continue
        entry = find_workflow(config, candidate)
        if not entry:
            continue
        roles = set(entry.get("roles") or [])
        if (
            entry.get("format") == "api"
            and entry.get("valid")
            and entry.get("kind") == "image"
            and {"input_image", "control_net_name"} <= roles
        ):
            return candidate
    return None


def resolve_image_mode(
    object_info: dict[str, Any],
    reference_mode: str,
    has_reference: bool,
) -> str:
    """Choose text-to-image, image-to-image, IP-Adapter identity, or ControlNet pose."""
    if not has_reference:
        return "text-to-image"
    if reference_mode == "pose" and controlnet_ready(object_info):
        return "controlnet-pose"
    if reference_mode == "identity" and ipadapter_ready(object_info):
        return "ipadapter-identity"
    return "image-to-image"
