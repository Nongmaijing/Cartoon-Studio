from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..comfy.client import ComfyClient, ComfyError
from ..config import load_config
from ..schemas import WorkflowImport
from ..services.workflow_checks import workflow_readiness
from ..workflows.adapter import ROLE_LABELS
from ..workflows.inference import infer_mapping
from ..workflows.registry import (
    find_workflow,
    list_workflows,
    load_workflow,
    save_workflow,
)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


async def _object_info() -> dict:
    config = load_config()
    client = ComfyClient(
        config["comfyui"]["server_url"],
        timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
    )
    return await client.object_info()


@router.get("")
async def workflows() -> list[dict]:
    config = load_config()
    entries = list_workflows(config)
    try:
        object_info = await _object_info()
    except ComfyError as exc:
        for entry in entries:
            entry["runnable"] = False
            entry["comfy_error"] = str(exc)
        return entries

    for entry in entries:
        entry["runnable"] = False
        entry["model_status"] = []
        entry["missing_nodes"] = []
        if entry["format"] != "api" or not entry["valid"]:
            continue
        try:
            readiness = workflow_readiness(config, entry, object_info)
        except Exception as exc:  # noqa: BLE001
            entry["errors"].append(str(exc))
            continue
        loaded = readiness["loaded"]
        entry["model_status"] = readiness["models"]
        entry["missing_nodes"] = readiness["missing_nodes"]
        entry["runnable"] = readiness["runnable"]
        entry["roles_detail"] = [
            {
                "role": role,
                "label": ROLE_LABELS.get(role, role),
                "node": spec.get("node"),
                "input": spec.get("input"),
                "class": spec.get("class"),
            }
            for role, spec in (loaded["mapping"].get("roles") or {}).items()
        ]
    return entries


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str) -> dict:
    config = load_config()
    try:
        loaded = load_workflow(config, workflow_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "entry": loaded["entry"],
        "api": loaded["api"],
        "mapping": loaded["mapping"],
    }


@router.get("/{workflow_id}/export")
async def export_workflow(workflow_id: str) -> JSONResponse:
    config = load_config()
    try:
        loaded = load_workflow(config, workflow_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    payload = {"name": loaded["entry"]["name"], "api": loaded["api"], "mapping": loaded["mapping"]}
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{workflow_id}.json"'},
    )


@router.post("/import", status_code=201)
async def import_workflow(payload: WorkflowImport) -> dict:
    config = load_config()
    mapping = payload.mapping
    if not mapping:
        mapping = infer_mapping(payload.api, payload.name)
    try:
        entry = save_workflow(config, payload.name, payload.api, mapping)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return entry


@router.post("/{workflow_id}/validate")
async def validate(workflow_id: str) -> dict:
    config = load_config()
    try:
        loaded = load_workflow(config, workflow_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if loaded["entry"]["format"] != "api":
        return {"valid": False, "checks": [], "errors": loaded["entry"]["errors"]}
    try:
        object_info = await _object_info()
    except ComfyError as exc:
        raise HTTPException(status_code=503, detail=f"ComfyUI unavailable: {exc}") from exc
    readiness = workflow_readiness(config, loaded["entry"], object_info)
    return {
        "valid": all(check["ok"] for check in readiness["checks"]),
        "runnable": readiness["runnable"],
        "checks": readiness["checks"],
        "models": readiness["models"],
        "missing_nodes": readiness["missing_nodes"],
        "errors": [
            check["message"] for check in readiness["checks"] if not check["ok"]
        ],
    }
