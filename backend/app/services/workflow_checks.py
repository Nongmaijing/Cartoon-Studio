from __future__ import annotations

from typing import Any

from ..workflows.adapter import validate_workflow
from ..workflows.registry import load_workflow
from .engines import combo_options
from .model_config_service import configured_checkpoint


def model_status(mapping: dict[str, Any], api: dict[str, Any], object_info: dict[str, Any]) -> list[dict[str, Any]]:
    """Report whether each model named by the mapping is present in ComfyUI."""
    result: list[dict[str, Any]] = []
    for check in mapping.get("model_checks") or []:
        role = check.get("role")
        spec = (mapping.get("roles") or {}).get(role)
        if not spec:
            continue
        node = api.get(str(spec["node"]))
        if not node:
            continue
        value = node["inputs"].get(spec["input"])
        loader_info = object_info.get(check.get("loader", "")) or {}
        spec = (
            ((loader_info.get("input") or {}).get("required") or {})
            .get(check.get("input", ""), None)
        )
        options = combo_options(spec)
        result.append(
            {
                "role": role,
                "label": role.replace("_", " ").title(),
                "value": value,
                "available": value in options,
                "options": options,
            }
        )
    return result


def missing_node_classes(api: dict[str, Any], object_info: dict[str, Any]) -> list[str]:
    """Every node class used by the graph that the live ComfyUI does not provide."""
    return sorted(
        {
            node.get("class_type", "")
            for node in api.values()
            if node.get("class_type") and node.get("class_type") not in object_info
        }
    )


def workflow_readiness(
    config: dict[str, Any],
    entry: dict[str, Any],
    object_info: dict[str, Any],
) -> dict[str, Any]:
    """Validate a workflow's graph, mapped roles, node classes and model files."""
    loaded = load_workflow(config, entry["id"])
    api = loaded["api"]
    mapping = loaded["mapping"]
    engine = str(mapping.get("engine") or "")
    if engine in ("sdxl", "sd15"):
        checkpoint_key = "sdxl_inpaint" if entry["id"] == "sdxl_inpaint" else engine
        checkpoint = configured_checkpoint(config, checkpoint_key)
        checkpoint_role = (mapping.get("roles") or {}).get("checkpoint")
        if checkpoint and checkpoint_role:
            node = api.get(str(checkpoint_role.get("node")))
            if node and checkpoint_role.get("input") in (node.get("inputs") or {}):
                node["inputs"][checkpoint_role["input"]] = checkpoint
    checks = validate_workflow(api, mapping, object_info)
    models = model_status(mapping, api, object_info)
    missing_nodes = missing_node_classes(api, object_info)
    runnable = (
        all(check["ok"] for check in checks)
        and all(item["available"] for item in models)
        and not missing_nodes
    )
    return {
        "loaded": loaded,
        "checks": checks,
        "models": models,
        "missing_nodes": missing_nodes,
        "runnable": runnable,
    }
