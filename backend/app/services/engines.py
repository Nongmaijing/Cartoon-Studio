from __future__ import annotations

from typing import Any

WAN_REQUIRED_NODES = [
    "UNETLoader",
    "CLIPLoader",
    "VAELoader",
    "ModelSamplingSD3",
    "Wan22ImageToVideoLatent",
    "KSampler",
    "VAEDecodeTiled",
    "CreateVideo",
    "SaveVideo",
]

WAN_EXPECTED = {
    "model": "wan2.2_ti2v_5B_fp16.safetensors",
    "clip": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
    "vae": "wan2.2_vae.safetensors",
}


def _loader_options(object_info: dict[str, Any], class_type: str, input_name: str) -> list[str]:
    node = object_info.get(class_type) or {}
    spec = (((node.get("input") or {}).get("required") or {}).get(input_name))
    return combo_options(spec)


def combo_options(spec: Any) -> list[str]:
    """Read combo options from both old and new ComfyUI object_info formats."""
    if not isinstance(spec, (list, tuple)) or not spec:
        return []
    first = spec[0]
    if isinstance(first, list):
        return [str(value) for value in first]
    if first == "COMBO" and len(spec) > 1 and isinstance(spec[1], dict):
        options = spec[1].get("options")
        if isinstance(options, list):
            return [str(value) for value in options]
    return []


def _matching_nodes(object_info: dict[str, Any], patterns: tuple[str, ...]) -> list[str]:
    return sorted(
        name
        for name in object_info
        if any(pattern.lower() in name.lower() for pattern in patterns)
    )


def _collect_models(
    object_info: dict[str, Any],
    nodes: list[str],
    input_names: tuple[str, ...] | None = None,
) -> dict[str, list[str]]:
    """Collect model-file combo options from the matching loader nodes."""
    models: dict[str, list[str]] = {}
    for node_name in nodes:
        node = object_info.get(node_name) or {}
        required = (node.get("input") or {}).get("required") or {}
        for input_name, spec in required.items():
            if input_names is not None and input_name not in input_names:
                continue
            options = combo_options(spec)
            if options:
                models[f"{node_name}.{input_name}"] = options
    return models


def _all_model_values(models: dict[str, list[str]]) -> list[str]:
    values: list[str] = []
    for options in models.values():
        values.extend(options)
    return values


def _engine_result(
    *,
    available: bool,
    required_nodes: list[str],
    object_info: dict[str, Any],
    models: dict[str, list[str]],
    expected: dict[str, str] | None = None,
    notes: str = "",
) -> dict[str, Any]:
    missing = [name for name in required_nodes if name not in object_info]
    return {
        "available": available,
        "nodes": {name: name in object_info for name in required_nodes},
        "missing_nodes": missing,
        "models": models,
        "expected": expected or {},
        "notes": notes,
    }


def detect_engines(object_info: dict[str, Any]) -> dict[str, Any]:
    """Report what the installed ComfyUI can actually run. Never assumes a node or model exists."""
    wan_models = {
        "model": _loader_options(object_info, "UNETLoader", "unet_name"),
        "clip": _loader_options(object_info, "CLIPLoader", "clip_name"),
        "vae": _loader_options(object_info, "VAELoader", "vae_name"),
    }
    wan_missing_models = [
        role for role, expected in WAN_EXPECTED.items() if expected not in wan_models.get(role, [])
    ]
    wan_available = (
        not [name for name in WAN_REQUIRED_NODES if name not in object_info]
        and not wan_missing_models
    )
    wan = _engine_result(
        available=wan_available,
        required_nodes=WAN_REQUIRED_NODES,
        object_info=object_info,
        models=wan_models,
        expected=WAN_EXPECTED,
        notes=(
            "Wan 2.2 TI2V-5B can run text-to-video and image-to-video. "
            "On 6 GB VRAM expect 20+ minutes for a 121-frame 720p clip."
        ),
    )
    wan["missing_models"] = wan_missing_models

    animatediff_nodes = sorted(
        name
        for name in object_info
        if name.startswith("ADE_") or "animatediff" in name.lower()
    )
    animatediff_models = _collect_models(object_info, animatediff_nodes, ("model_name",))
    animatediff = _engine_result(
        available=bool(animatediff_nodes) and bool(_all_model_values(animatediff_models)),
        required_nodes=animatediff_nodes,
        object_info=object_info,
        models=animatediff_models,
        notes="AnimateDiff is optional and only used when its custom nodes and motion models are installed.",
    )

    ipadapter_nodes = _matching_nodes(object_info, ("IPAdapter",))
    ipadapter_models = _collect_models(
        object_info,
        ipadapter_nodes,
        ("ipadapter_file", "ipadapter", "clip_name", "unet_name"),
    )
    ipadapter_has_models = bool(_all_model_values(ipadapter_models))
    ipadapter = _engine_result(
        available=bool(ipadapter_nodes) and ipadapter_has_models,
        required_nodes=ipadapter_nodes,
        object_info=object_info,
        models=ipadapter_models,
        notes=(
            "IPAdapter is optional and used for character consistency when installed."
            if ipadapter_has_models or not ipadapter_nodes
            else "IPAdapter nodes are present, but no IPAdapter model files were found."
        ),
    )

    controlnet_nodes = _matching_nodes(object_info, ("ControlNet",))
    controlnet_models = _collect_models(
        object_info,
        controlnet_nodes,
        ("control_net_name", "controlnet_name", "control_net"),
    )
    controlnet_has_models = bool(_all_model_values(controlnet_models))
    controlnet = _engine_result(
        available=bool(controlnet_nodes) and controlnet_has_models,
        required_nodes=controlnet_nodes,
        object_info=object_info,
        models=controlnet_models,
        notes=(
            "ControlNet is optional and used for pose or layout control when installed."
            if controlnet_has_models or not controlnet_nodes
            else "ControlNet core nodes are present, but no ControlNet model files were found."
        ),
    )

    return {
        "wan22": wan,
        "animatediff": animatediff,
        "ipadapter": ipadapter,
        "controlnet": controlnet,
    }
