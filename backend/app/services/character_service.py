from __future__ import annotations

import json
import uuid
from typing import Any

from ..comfy.client import ComfyClient
from ..config import load_config
from ..db import execute, now, query, query_one
from ..providers.registry import registry
from .approval_service import approve_character as approve_character_record
from .approval_service import snapshot_character
from .audit_service import log
from .canonical_service import validate_canonical_asset
from .conditioning import (
    controlnet_model,
    controlnet_ready,
    controlnet_workflow_id,
    ipadapter_workflow_id,
    resolve_image_mode,
)
from .creative import character_negative_prompt, character_prompt
from .errors import NotFoundError, ServiceError
from .generation import upload_start_image
from .media import cover_asset_id, list_media, media_counts
from .model_config_service import resolve_image_model

CHARACTER_FIELDS = (
    "name",
    "description",
    "style",
    "clothing",
    "appearance",
    "voice_engine",
    "voice_name",
    "voice_rate",
    "voice_pitch",
    "voice_volume",
)


def _decorate(row: dict[str, Any]) -> dict[str, Any]:
    counts = media_counts("character", row["id"])
    cover = cover_asset_id("character", row["id"])
    row["reference_count"] = counts.get("reference", 0)
    row["expression_count"] = counts.get("expression", 0)
    row["pose_count"] = counts.get("pose", 0)
    row["cover_asset_id"] = cover
    row["cover_url"] = f"/api/assets/{cover}/file" if cover else None
    canonical = row.get("canonical_asset_id")
    row["canonical_url"] = f"/api/assets/{canonical}/file" if canonical else None
    row["canonical_created_at"] = None
    row["canonical_stale"] = False
    if canonical:
        asset = query_one("SELECT created_at FROM assets WHERE id = ?", (canonical,))
        if asset:
            row["canonical_created_at"] = asset.get("created_at")
            row["canonical_stale"] = bool(
                asset.get("created_at") and row.get("updated_at")
                and asset["created_at"] < row["updated_at"]
            )
    try:
        row["memory"] = json.loads(row.get("memory_json") or "{}")
    except json.JSONDecodeError:
        row["memory"] = {}
    row["model"] = row["memory"].get("model") if isinstance(row["memory"], dict) else {}
    return row


def list_characters(project_id: str | None = None) -> list[dict[str, Any]]:
    if project_id:
        rows = query(
            "SELECT * FROM characters WHERE project_id = ? ORDER BY updated_at DESC",
            (project_id,),
        )
    else:
        rows = query("SELECT * FROM characters ORDER BY updated_at DESC")
    return [_decorate(row) for row in rows]


def get_character(character_id: str) -> dict[str, Any]:
    row = query_one("SELECT * FROM characters WHERE id = ?", (character_id,))
    if not row:
        raise NotFoundError("Character not found.")
    return _decorate(row)


def create_character(
    project_id: str,
    *,
    name: str,
    description: str = "",
    style: str = "",
    clothing: str = "",
    appearance: str = "",
    voice_engine: str = "",
    voice_name: str = "",
    voice_rate: int = 0,
    voice_pitch: int = 0,
    voice_volume: int = 100,
    actor: str = "user",
) -> dict[str, Any]:
    if not query_one("SELECT id FROM projects WHERE id = ?", (project_id,)):
        raise NotFoundError("Project not found.")
    character_id = uuid.uuid4().hex[:12]
    timestamp = now()
    execute(
        """INSERT INTO characters
           (id, project_id, name, description, style, clothing, appearance,
            voice_engine, voice_name, voice_rate, voice_pitch, voice_volume,
            memory_json, approval_status, version, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', 'draft', 1, ?, ?)""",
        (
            character_id,
            project_id,
            name.strip(),
            description.strip(),
            style.strip(),
            clothing.strip(),
            appearance.strip(),
            voice_engine.strip(),
            voice_name.strip(),
            voice_rate,
            voice_pitch,
            voice_volume,
            timestamp,
            timestamp,
        ),
    )
    log(actor, "create_character", "character", character_id, {"name": name})
    return get_character(character_id)


def update_character(character_id: str, updates: dict[str, Any], actor: str = "user") -> dict[str, Any]:
    current = get_character(character_id)
    allowed = set(CHARACTER_FIELDS) | {"memory_json"}
    fields = [field for field in updates if field in allowed]
    if not fields:
        return current
    identity_fields = {"name", "description", "style", "clothing", "appearance"}
    identity_changed = bool(identity_fields & set(fields))
    sql_parts: list[str] = []
    params: list[Any] = []
    for field in fields:
        value = updates[field]
        if isinstance(value, str):
            value = value.strip()
        sql_parts.append(f"{field} = ?")
        params.append(value)
    if identity_changed and current.get("approval_status") == "approved":
        # Approval describes a specific design. Editing identity fields invalidates it.
        sql_parts.extend(["approval_status = 'draft'", "approved_at = NULL"])
    sql_parts.append("updated_at = ?")
    params.extend([now(), character_id])
    execute(f"UPDATE characters SET {', '.join(sql_parts)} WHERE id = ?", params)
    snapshot_character(character_id, approved=False)
    log(actor, "update_character", "character", character_id, {"fields": fields})
    return get_character(character_id)


def set_memory(character_id: str, memory: dict[str, Any], actor: str = "user") -> dict[str, Any]:
    return update_character(character_id, {"memory_json": json.dumps(memory)}, actor=actor)


def update_voice(character_id: str, *, engine: str, voice: str, rate: int = 0, pitch: int = 0, volume: int = 100, actor: str = "user") -> dict[str, Any]:
    return update_character(
        character_id,
        {
            "voice_engine": engine,
            "voice_name": voice,
            "voice_rate": rate,
            "voice_pitch": pitch,
            "voice_volume": volume,
        },
        actor=actor,
    )


def set_canonical(character_id: str, asset_id: str, actor: str = "user") -> dict[str, Any]:
    character = get_character(character_id)
    if character.get("approval_status") == "approved" and character.get("canonical_asset_id") != asset_id:
        raise ServiceError(
            "Cannot change the canonical reference while the character is approved.",
            status_code=409,
            code="canonical_locked",
        )
    validate_canonical_asset(character, asset_id)
    execute(
        "UPDATE characters SET canonical_asset_id = ?, updated_at = ? WHERE id = ?",
        (asset_id, now(), character_id),
    )
    snapshot_character(character_id, approved=False)
    log(actor, "set_canonical", "character", character_id, {"asset_id": asset_id})
    return get_character(character_id)


def clear_canonical(character_id: str, actor: str = "user") -> dict[str, Any]:
    character = get_character(character_id)
    if character.get("approval_status") == "approved":
        raise ServiceError(
            "Cannot clear the canonical reference while the character is approved.",
            status_code=409,
            code="canonical_locked",
        )
    execute(
        "UPDATE characters SET canonical_asset_id = NULL, updated_at = ? WHERE id = ?",
        (now(), character_id),
    )
    log(actor, "clear_canonical", "character", character_id)
    return get_character(character_id)


def get_references(character_id: str) -> dict[str, Any]:
    character = get_character(character_id)
    media = list_media("character", character_id)
    return {
        "character_id": character_id,
        "canonical_asset_id": character.get("canonical_asset_id"),
        "references": [item for item in media if item["role"] == "reference"],
        "expressions": [item for item in media if item["role"] == "expression"],
        "poses": [item for item in media if item["role"] == "pose"],
        "approval_status": character.get("approval_status", "draft"),
    }


def _character_model_overrides(character: dict[str, Any]) -> dict[str, Any]:
    memory = character.get("memory") or {}
    model = memory.get("model") if isinstance(memory, dict) else {}
    if not isinstance(model, dict):
        model = {}
    overrides: dict[str, Any] = {}
    for key in (
        "architecture",
        "checkpoint",
        "vae",
        "lora_name",
        "lora_strength",
        "preset",
        "reference_strength",
        "denoise",
    ):
        value = model.get(key)
        if value not in (None, ""):
            overrides[key] = value
    return overrides


async def generate_sheet(
    character_id: str,
    *,
    kind: str = "reference",
    label: str = "front",
    width: int | None = None,
    height: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    seed: int | None = None,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    reference_asset_id: str | None = None,
    use_reference: bool = True,
    reference_mode: str = "identity",
    denoise: float = 0.5,
    control_strength: float = 0.8,
    actor: str = "user",
) -> dict[str, Any]:
    character = get_character(character_id)
    project_id = character.get("project_id")
    if not project_id:
        raise ServiceError("Character is not attached to a project.")
    config = load_config()
    client = ComfyClient(
        config["comfyui"]["server_url"],
        timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
    )
    reference_asset_id = (
        reference_asset_id or character.get("canonical_asset_id")
    ) if use_reference else None
    input_image = None
    workflow_id = None
    mode = "text-to-image"
    control_net_name = None
    if reference_asset_id:
        object_info = await client.object_info()
        mode = resolve_image_mode(object_info, reference_mode, True)
        if mode == "controlnet-pose":
            control_net_name = controlnet_model(object_info)
        input_image = await upload_start_image(config, client, reference_asset_id, project_id)
    final_label = label.strip() or ("front" if kind == "reference" else kind)
    composed = character_prompt(character, kind, final_label, prompt)
    overrides = _character_model_overrides(character)
    model = resolve_image_model(
        config,
        architecture=overrides.get("architecture"),
        purpose="character",
        input_image=bool(reference_asset_id),
        explicit=bool(overrides.get("architecture")),
    )
    if mode == "controlnet-pose":
        workflow_id = controlnet_workflow_id(config, model["architecture"])
        control_net_name = controlnet_model(object_info, model["architecture"])
        if not workflow_id or not control_net_name:
            mode = "image-to-image"
            workflow_id = None
            control_net_name = None
    elif mode == "ipadapter-identity":
        workflow_id = ipadapter_workflow_id(config, model["architecture"])
        if not workflow_id:
            mode = "image-to-image"
            workflow_id = None
    if "preset" not in overrides:
        overrides["preset"] = (
            "sdxl_portrait"
            if model["architecture"] == "sdxl" and kind == "pose"
            else f"{model['architecture']}_character"
        )
    effective_denoise = float(
        overrides.pop("reference_strength", overrides.pop("denoise", denoise))
    )
    if mode == "ipadapter-identity":
        # IP-Adapter conditions an empty latent; a partial denoise would only add noise.
        effective_denoise = 1.0
    provider = registry.get("image")
    result = await provider.generate_image(
        project_id=project_id,
        prompt=composed,
        negative_prompt=negative_prompt
        or character_negative_prompt(kind, final_label, character.get("clothing")),
        width=width,
        height=height,
        steps=steps,
        cfg=cfg,
        seed=seed,
        workflow_id=workflow_id,
        input_image=input_image,
        denoise=effective_denoise if reference_asset_id else None,
        control_strength=control_strength if mode == "controlnet-pose" else None,
        control_net_name=control_net_name,
        purpose="character",
        **overrides,
        attach={
            "owner_type": "character",
            "owner_id": character_id,
            "role": kind,
            "label": final_label,
        },
    )
    log(
        actor,
        "generate_character_sheet",
        "character",
        character_id,
        {"kind": kind, "mode": mode, "job_id": result.get("job_id")},
    )
    reference_approved = (
        character.get("approval_status") == "approved" if reference_asset_id else None
    )
    return {
        **result,
        "character_id": character_id,
        "mode": mode,
        "reference_asset_id": reference_asset_id,
        "input_image": input_image,
        "reference_approved": reference_approved,
        "reference_warning": (
            "The reference is used because it is the character's canonical image, but the character is not approved."
            if reference_asset_id and not reference_approved
            else None
        ),
        "model": result.get("model"),
        "prompt": composed,
        "fallback": bool(reference_asset_id) and reference_mode == "pose" and mode != "controlnet-pose",
    }


async def generate_character_sheet(character_id: str, **kwargs: Any) -> dict[str, Any]:
    return await generate_sheet(character_id, **kwargs)


def approve_character(character_id: str, actor: str = "user") -> dict[str, Any]:
    return approve_character_record(character_id, actor=actor)
