from __future__ import annotations

from typing import Any


def _first(api: dict[str, Any], class_type: str) -> tuple[str, dict] | None:
    for node_id, node in api.items():
        if node.get("class_type") == class_type:
            return node_id, node
    return None


def _role(node_id: str, node: dict, input_name: str) -> dict[str, str]:
    return {"node": node_id, "class": node.get("class_type", ""), "input": input_name}


def infer_mapping(api: dict[str, Any], name: str = "Imported workflow") -> dict[str, Any]:
    """Infer UI roles from an API-format graph by inspecting node classes and links.

    This lets a user import a ComfyUI API workflow without hand-writing a mapping.
    The inference is conservative: a role is only added when the node and input exist.
    """
    roles: dict[str, dict[str, str]] = {}

    checkpoint = _first(api, "CheckpointLoaderSimple")
    if checkpoint:
        node_id, node = checkpoint
        if "ckpt_name" in node.get("inputs", {}):
            roles["checkpoint"] = _role(node_id, node, "ckpt_name")

    unet = _first(api, "UNETLoader")
    if unet:
        node_id, node = unet
        if "unet_name" in node.get("inputs", {}):
            roles["model"] = _role(node_id, node, "unet_name")

    clip_loader = _first(api, "CLIPLoader")
    if clip_loader:
        node_id, node = clip_loader
        if "clip_name" in node.get("inputs", {}):
            roles["clip"] = _role(node_id, node, "clip_name")

    vae_loader = _first(api, "VAELoader")
    if vae_loader:
        node_id, node = vae_loader
        if "vae_name" in node.get("inputs", {}):
            roles["vae"] = _role(node_id, node, "vae_name")

    shift = _first(api, "ModelSamplingSD3")
    if shift:
        node_id, node = shift
        if "shift" in node.get("inputs", {}):
            roles["shift"] = _role(node_id, node, "shift")

    sampler = _first(api, "KSampler")
    if sampler:
        node_id, node = sampler
        for input_name, role in (
            ("seed", "seed"),
            ("steps", "steps"),
            ("cfg", "cfg"),
            ("sampler_name", "sampler"),
            ("scheduler", "scheduler"),
            ("denoise", "denoise"),
        ):
            if input_name in node.get("inputs", {}):
                roles[role] = _role(node_id, node, input_name)
        for slot, role in (("positive", "positive_prompt"), ("negative", "negative_prompt")):
            link = node.get("inputs", {}).get(slot)
            if isinstance(link, list) and link:
                source = api.get(str(link[0]))
                if source and "text" in source.get("inputs", {}):
                    roles[role] = _role(str(link[0]), source, "text")

    latent = _first(api, "EmptyLatentImage") or _first(api, "Wan22ImageToVideoLatent")
    if latent:
        node_id, node = latent
        for input_name in ("width", "height", "batch_size", "length"):
            if input_name in node.get("inputs", {}):
                roles[input_name] = _role(node_id, node, input_name)

    load_image = _first(api, "LoadImage")
    if load_image:
        node_id, node = load_image
        if "image" in node.get("inputs", {}):
            roles["input_image"] = _role(node_id, node, "image")

    create_video = _first(api, "CreateVideo")
    if create_video:
        node_id, node = create_video
        if "fps" in node.get("inputs", {}):
            roles["fps"] = _role(node_id, node, "fps")

    output_nodes: list[str] = []
    for class_type in ("SaveImage", "SaveVideo"):
        found = _first(api, class_type)
        if not found:
            continue
        node_id, node = found
        output_nodes.append(node_id)
        if "filename_prefix" in node.get("inputs", {}):
            roles["filename_prefix"] = _role(node_id, node, "filename_prefix")
        if "format" in node.get("inputs", {}):
            roles["output_format"] = _role(node_id, node, "format")

    is_video = create_video is not None or _first(api, "SaveVideo") is not None
    is_sd15 = checkpoint is not None
    engine = "sd15" if is_sd15 else ("wan22" if unet else "custom")

    model_checks: list[dict[str, str]] = []
    if "checkpoint" in roles:
        model_checks.append({"role": "checkpoint", "loader": "CheckpointLoaderSimple", "input": "ckpt_name"})
    if "model" in roles:
        model_checks.append({"role": "model", "loader": "UNETLoader", "input": "unet_name"})
    if "clip" in roles:
        model_checks.append({"role": "clip", "loader": "CLIPLoader", "input": "clip_name"})
    if "vae" in roles:
        model_checks.append({"role": "vae", "loader": "VAELoader", "input": "vae_name"})

    return {
        "schema": 1,
        "name": name,
        "description": "Mapping inferred from node classes and links at import time.",
        "engine": engine,
        "kind": "video" if is_video else "image",
        "roles": roles,
        "model_checks": model_checks,
        "output_nodes": output_nodes,
    }
