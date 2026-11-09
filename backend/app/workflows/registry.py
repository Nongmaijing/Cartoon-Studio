from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import load_config


def workflow_dir(config: dict[str, Any] | None = None) -> Path:
    config = config or load_config()
    return Path(config["paths"]["workflow_dir"])


def is_api_workflow(data: Any) -> bool:
    return (
        isinstance(data, dict)
        and bool(data)
        and all(isinstance(value, dict) and "class_type" in value for value in data.values())
    )


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip()).strip("_").lower()
    return slug or "workflow"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _mapping_path(path: Path) -> Path:
    return path.with_suffix(".mapping.json")


def _validate_structure(api: dict[str, Any], mapping: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    roles = mapping.get("roles") or {}
    if not roles:
        errors.append("Mapping has no roles.")
    for role, spec in roles.items():
        node_id = str(spec.get("node", ""))
        node = api.get(node_id)
        if node is None:
            errors.append(f"Role '{role}' points to missing node {node_id}.")
            continue
        expected = spec.get("class")
        if expected and node.get("class_type") != expected:
            errors.append(
                f"Role '{role}' expects {expected} at node {node_id}, found {node.get('class_type')}."
            )
        input_name = spec.get("input")
        if input_name and input_name not in (node.get("inputs") or {}):
            errors.append(f"Role '{role}' input '{input_name}' not present on node {node_id}.")
    return (not errors, errors)


def _entry_from_file(path: Path, source: str) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": path.stem,
        "name": path.stem,
        "path": str(path),
        "source": source,
        "format": "unknown",
        "engine": "unknown",
        "kind": "unknown",
        "description": "",
        "roles": [],
        "valid": False,
        "errors": [],
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
    }
    try:
        api = _read_json(path)
    except Exception as exc:  # noqa: BLE001
        entry["errors"].append(f"Could not read JSON: {exc}")
        return entry

    if not is_api_workflow(api):
        entry["format"] = "ui"
        entry["errors"].append(
            "This is a ComfyUI UI-format workflow. Export it from ComfyUI as an API workflow to run it here."
        )
        return entry

    entry["format"] = "api"
    mapping_file = _mapping_path(path)
    if not mapping_file.exists():
        entry["errors"].append("Missing mapping sidecar. Import a mapping to run this workflow.")
        return entry

    try:
        mapping = _read_json(mapping_file)
    except Exception as exc:  # noqa: BLE001
        entry["errors"].append(f"Could not read mapping: {exc}")
        return entry

    entry["name"] = mapping.get("name") or path.stem
    entry["engine"] = mapping.get("engine", "unknown")
    entry["kind"] = mapping.get("kind", "unknown")
    entry["description"] = mapping.get("description", "")
    entry["roles"] = sorted((mapping.get("roles") or {}).keys())
    valid, errors = _validate_structure(api, mapping)
    entry["valid"] = valid
    entry["errors"] = errors
    return entry


def list_workflows(config: dict[str, Any] | None = None, include_comfyui: bool = True) -> list[dict[str, Any]]:
    config = config or load_config()
    entries: list[dict[str, Any]] = []
    directory = workflow_dir(config)
    if directory.exists():
        for path in sorted(directory.glob("*.json")):
            if path.name.endswith(".mapping.json"):
                continue
            entries.append(_entry_from_file(path, "studio"))

    if include_comfyui:
        install = config["comfyui"].get("install_path") or ""
        user_dir = Path(install) / "user" / "default" / "workflows" if install else None
        if user_dir and user_dir.exists():
            for path in sorted(user_dir.glob("*.json")):
                entry = _entry_from_file(path, "comfyui")
                entry["id"] = f"comfyui__{path.stem}"
                entry["name"] = f"{path.stem} (ComfyUI UI)"
                entries.append(entry)
    return entries


def find_workflow(config: dict[str, Any], workflow_id: str) -> dict[str, Any] | None:
    for entry in list_workflows(config):
        if entry["id"] == workflow_id:
            return entry
    return None


def load_workflow(config: dict[str, Any], workflow_id: str) -> dict[str, Any]:
    entry = find_workflow(config, workflow_id)
    if not entry:
        raise FileNotFoundError(f"Workflow '{workflow_id}' not found.")
    path = Path(entry["path"])
    api = _read_json(path)
    mapping: dict[str, Any] = {}
    mapping_file = _mapping_path(path)
    if mapping_file.exists():
        mapping = _read_json(mapping_file)
    return {"entry": entry, "api": api, "mapping": mapping}


def save_workflow(config: dict[str, Any], name: str, api: dict[str, Any], mapping: dict[str, Any] | None) -> dict[str, Any]:
    if not is_api_workflow(api):
        raise ValueError("Workflow must be a ComfyUI API-format graph (node id -> {class_type, inputs}).")
    mapping = mapping or {}
    mapping.setdefault("schema", 1)
    mapping.setdefault("name", name)
    mapping.setdefault("engine", "custom")
    mapping.setdefault("kind", "image")
    mapping.setdefault("roles", {})

    directory = workflow_dir(config)
    directory.mkdir(parents=True, exist_ok=True)
    base = _slug(name)
    candidate = base
    counter = 2
    while (directory / f"{candidate}.json").exists():
        candidate = f"{base}_{counter}"
        counter += 1

    api_path = directory / f"{candidate}.json"
    mapping_path = directory / f"{candidate}.mapping.json"
    api_path.write_text(json.dumps(api, indent=2), encoding="utf-8")
    mapping_path.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    return _entry_from_file(api_path, "studio")
