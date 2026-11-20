from __future__ import annotations

import copy
import random
from typing import Any

ROLE_LABELS = {
    "checkpoint": "Checkpoint",
    "model": "Diffusion model",
    "clip": "Text encoder",
    "vae": "VAE",
    "shift": "Sampling shift",
    "positive_prompt": "Positive prompt",
    "negative_prompt": "Negative prompt",
    "width": "Width",
    "height": "Height",
    "batch_size": "Batch size",
    "length": "Frame count",
    "seed": "Seed",
    "steps": "Steps",
    "cfg": "CFG",
    "sampler": "Sampler",
    "scheduler": "Scheduler",
    "denoise": "Denoise",
    "fps": "FPS",
    "input_image": "Input image",
    "pose_image": "Pose skeleton",
    "mask_image": "Mask image",
    "ipadapter_weight": "IP-Adapter weight",
    "control_net_name": "ControlNet model",
    "control_strength": "ControlNet strength",
    "animatediff_model": "AnimateDiff motion model",
    "filename_prefix": "Filename prefix",
    "output_format": "Output format",
}

# UI field -> mapping role
PARAM_TO_ROLE = {
    "positive_prompt": "positive_prompt",
    "negative_prompt": "negative_prompt",
    "checkpoint": "checkpoint",
    "model": "model",
    "clip": "clip",
    "vae": "vae",
    "width": "width",
    "height": "height",
    "steps": "steps",
    "cfg": "cfg",
    "seed": "seed",
    "sampler": "sampler",
    "scheduler": "scheduler",
    "denoise": "denoise",
    "batch_size": "batch_size",
    "length": "length",
    "fps": "fps",
    "input_image": "input_image",
    "pose_image": "pose_image",
    "mask_image": "mask_image",
    "ipadapter_weight": "ipadapter_weight",
    "control_net_name": "control_net_name",
    "control_strength": "control_strength",
    "output_format": "output_format",
}


def _input_spec(object_info: dict[str, Any], class_type: str, input_name: str) -> dict[str, Any] | None:
    node = object_info.get(class_type) or {}
    inputs = node.get("input") or {}
    for section in ("required", "optional"):
        spec = (inputs.get(section) or {}).get(input_name)
        if spec is not None:
            return spec if isinstance(spec, dict) else {"type": spec}
    return None


def validate_workflow(
    api: dict[str, Any],
    mapping: dict[str, Any],
    object_info: dict[str, Any],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    roles = mapping.get("roles") or {}
    for role, spec in roles.items():
        node_id = str(spec.get("node", ""))
        input_name = spec.get("input", "")
        expected_class = spec.get("class")
        node = api.get(node_id)
        check: dict[str, Any] = {
            "role": role,
            "label": ROLE_LABELS.get(role, role),
            "node": node_id,
            "input": input_name,
            "ok": True,
            "message": "",
        }
        if node is None:
            check.update(ok=False, message=f"Node {node_id} does not exist in this workflow.")
        elif expected_class and node.get("class_type") != expected_class:
            check.update(
                ok=False,
                message=f"Node {node_id} is {node.get('class_type')}, expected {expected_class}.",
            )
        elif input_name not in (node.get("inputs") or {}):
            check.update(ok=False, message=f"Input '{input_name}' is missing on node {node_id}.")
        else:
            class_type = node["class_type"]
            if class_type not in object_info:
                check.update(ok=False, message=f"Node type '{class_type}' is not installed in ComfyUI.")
            else:
                spec_info = _input_spec(object_info, class_type, input_name)
                if spec_info is None:
                    check.update(
                        ok=False,
                        message=f"ComfyUI node '{class_type}' has no input '{input_name}'.",
                    )
        checks.append(check)
    return checks


def build_prompt(
    api: dict[str, Any],
    mapping: dict[str, Any],
    params: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    prompt = copy.deepcopy(api)
    applied: list[str] = []
    roles = mapping.get("roles") or {}

    for param, role in PARAM_TO_ROLE.items():
        if param not in params:
            continue
        value = params[param]
        if value is None or value == "":
            continue
        spec = roles.get(role)
        if not spec:
            continue
        node_id = str(spec.get("node", ""))
        input_name = spec.get("input", "")
        node = prompt.get(node_id)
        if not node or input_name not in (node.get("inputs") or {}):
            continue
        node["inputs"][input_name] = value
        applied.append(role)

    if roles.get("seed") and ("seed" not in params or params.get("seed") in (None, -1)):
        node_id = str(roles["seed"].get("node"))
        input_name = roles["seed"].get("input", "seed")
        if prompt.get(node_id):
            prompt[node_id]["inputs"][input_name] = random.randint(0, 2**32 - 1)
            applied.append("seed")

    return prompt, applied


def _find_checkpoint(api: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    for node_id, node in api.items():
        if node.get("class_type") == "CheckpointLoaderSimple":
            return str(node_id), node
    return None, None


def _rewire(
    api: dict[str, Any],
    source_id: str,
    source_output: int,
    target_id: str,
    target_output: int,
    skip_ids: set[str] | None = None,
) -> None:
    skip = skip_ids or set()
    for node_id, node in api.items():
        if node_id in skip:
            continue
        inputs = node.get("inputs") or {}
        for key, value in list(inputs.items()):
            if (
                isinstance(value, list)
                and len(value) == 2
                and str(value[0]) == str(source_id)
                and int(value[1]) == int(source_output)
            ):
                inputs[key] = [target_id, int(target_output)]


def _unique_node_id(api: dict[str, Any], base: str) -> str:
    node_id = base
    counter = 2
    while node_id in api:
        node_id = f"{base}_{counter}"
        counter += 1
    return node_id


def apply_vae(api: dict[str, Any], params: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Optionally inject a VAELoader and rewire the graph to use it."""
    vae_name = params.get("vae")
    if not vae_name:
        return api, False
    checkpoint_id, checkpoint = _find_checkpoint(api)
    if not checkpoint:
        raise ValueError("A VAE selection requires a CheckpointLoaderSimple workflow.")
    existing = next(
        (
            (node_id, node)
            for node_id, node in api.items()
            if node.get("class_type") == "VAELoader" and "vae_name" in (node.get("inputs") or {})
        ),
        None,
    )
    if existing:
        node_id, node = existing
        node["inputs"]["vae_name"] = vae_name
    else:
        node_id = _unique_node_id(api, "model_vae")
        api[node_id] = {"class_type": "VAELoader", "inputs": {"vae_name": vae_name}}
    _rewire(api, checkpoint_id, 2, node_id, 0, skip_ids={node_id})
    return api, True


def apply_lora(api: dict[str, Any], params: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Optionally inject a LoraLoader and rewire model/clip links."""
    lora_name = params.get("lora_name")
    if not lora_name:
        return api, False
    checkpoint_id, checkpoint = _find_checkpoint(api)
    if not checkpoint:
        raise ValueError("A LoRA selection requires a CheckpointLoaderSimple workflow.")
    try:
        strength = float(params.get("lora_strength") or 0.8)
    except (TypeError, ValueError):
        strength = 0.8
    node_id = _unique_node_id(api, "model_lora")
    api[node_id] = {
        "class_type": "LoraLoader",
        "inputs": {
            "model": [checkpoint_id, 0],
            "clip": [checkpoint_id, 1],
            "lora_name": lora_name,
            "strength_model": strength,
            "strength_clip": strength,
        },
    }
    _rewire(api, checkpoint_id, 0, node_id, 0, skip_ids={node_id})
    _rewire(api, checkpoint_id, 1, node_id, 1, skip_ids={node_id})
    return api, True


def apply_model_adapters(api: dict[str, Any], params: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    applied: list[str] = []
    api, vae_applied = apply_vae(api, params)
    if vae_applied:
        applied.append("vae")
    api, lora_applied = apply_lora(api, params)
    if lora_applied:
        applied.append("lora")
    return api, applied
