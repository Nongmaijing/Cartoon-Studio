from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from ..comfy.client import ComfyClient, ComfyError
from ..config import load_config
from ..db import execute, now, query, query_one
from ..schemas import (
    CanonicalAsset,
    CharacterCreate,
    CharacterGenerateRequest,
    CharacterModelSettings,
    CharacterSheetRequest,
    CharacterUpdate,
    ConsistencyCheckRequest,
    MediaAttach,
    VoiceAssignment,
)
from ..services import character_sheet_service, consistency_service
from ..services.conditioning import controlnet_model, resolve_image_mode
from ..services.creative import NEGATIVE_DEFAULT, character_prompt
from ..services.generation import submit_image, upload_start_image
from ..services.media import cover_asset_id, link_asset, list_media, media_counts

router = APIRouter(prefix="/api/characters", tags=["characters"])


def _client(config: dict[str, Any]) -> ComfyClient:
    return ComfyClient(
        config["comfyui"]["server_url"],
        timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
    )


def _decorate(row: dict[str, Any]) -> dict[str, Any]:
    counts = media_counts("character", row["id"])
    row["reference_count"] = counts.get("reference", 0)
    row["expression_count"] = counts.get("expression", 0)
    row["pose_count"] = counts.get("pose", 0)
    cover = cover_asset_id("character", row["id"])
    row["cover_asset_id"] = cover
    row["cover_url"] = f"/api/assets/{cover}/file" if cover else None
    canonical = row.get("canonical_asset_id")
    row["canonical_url"] = f"/api/assets/{canonical}/file" if canonical else None
    try:
        row["memory"] = json.loads(row.get("memory_json") or "{}")
    except json.JSONDecodeError:
        row["memory"] = {}
    row["model"] = row["memory"].get("model") if isinstance(row["memory"], dict) else {}
    row["master_reference"] = {
        "asset_id": canonical,
        "url": f"/api/assets/{canonical}/file" if canonical else None,
        "approved": row.get("approval_status") == "approved",
    }
    return row


def _get(character_id: str) -> dict[str, Any]:
    row = query_one("SELECT * FROM characters WHERE id = ?", (character_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Character not found.")
    return _decorate(row)


def _require_project(project_id: str) -> None:
    if not query_one("SELECT id FROM projects WHERE id = ?", (project_id,)):
        raise HTTPException(status_code=404, detail="Project not found.")


@router.get("")
async def list_characters(project_id: str | None = None) -> list[dict[str, Any]]:
    if project_id:
        rows = query(
            "SELECT * FROM characters WHERE project_id = ? ORDER BY updated_at DESC",
            (project_id,),
        )
    else:
        rows = query("SELECT * FROM characters ORDER BY updated_at DESC")
    return [_decorate(row) for row in rows]


@router.post("", status_code=201)
async def create_character(payload: CharacterCreate) -> dict[str, Any]:
    _require_project(payload.project_id)
    character_id = uuid.uuid4().hex[:12]
    timestamp = now()
    execute(
        """INSERT INTO characters
           (id, project_id, name, description, style, clothing, appearance,
            voice_engine, voice_name, voice_rate, voice_pitch, voice_volume,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            character_id,
            payload.project_id,
            payload.name.strip(),
            payload.description.strip(),
            payload.style.strip(),
            payload.clothing.strip(),
            payload.appearance.strip(),
            payload.voice_engine.strip(),
            payload.voice_name.strip(),
            payload.voice_rate,
            payload.voice_pitch,
            payload.voice_volume,
            timestamp,
            timestamp,
        ),
    )
    return _get(character_id)


@router.get("/{character_id}")
async def get_character(character_id: str) -> dict[str, Any]:
    return _get(character_id)


@router.patch("/{character_id}")
async def update_character(character_id: str, payload: CharacterUpdate) -> dict[str, Any]:
    _get(character_id)
    updates: list[str] = []
    params: list[Any] = []
    for field in (
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
    ):
        value = getattr(payload, field)
        if value is not None:
            updates.append(f"{field} = ?")
            params.append(value.strip() if isinstance(value, str) else value)
    if updates:
        updates.append("updated_at = ?")
        params.extend([now(), character_id])
        execute(f"UPDATE characters SET {', '.join(updates)} WHERE id = ?", params)
    return _get(character_id)


@router.patch("/{character_id}/voice")
async def update_character_voice(character_id: str, payload: VoiceAssignment) -> dict[str, Any]:
    _get(character_id)
    execute(
        """UPDATE characters
           SET voice_engine = ?, voice_name = ?, voice_rate = ?, voice_pitch = ?, voice_volume = ?, updated_at = ?
           WHERE id = ?""",
        (
            payload.engine.strip(),
            payload.voice.strip(),
            payload.rate,
            payload.pitch,
            payload.volume,
            now(),
            character_id,
        ),
    )
    return _get(character_id)


@router.get("/{character_id}/media")
async def character_media(character_id: str, role: str | None = None) -> list[dict[str, Any]]:
    _get(character_id)
    return list_media("character", character_id, role=role)


@router.post("/{character_id}/media", status_code=201)
async def attach_character_media(character_id: str, payload: MediaAttach) -> dict[str, Any]:
    character = _get(character_id)
    asset = query_one("SELECT id, project_id FROM assets WHERE id = ?", (payload.asset_id,))
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")
    if asset["project_id"] and character["project_id"] and asset["project_id"] != character["project_id"]:
        raise HTTPException(status_code=400, detail="Asset belongs to a different project.")
    try:
        link = link_asset(
            "character",
            character_id,
            payload.asset_id,
            role=payload.role,
            label=payload.label.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**link, "character_id": character_id}


@router.post("/{character_id}/approve")
async def approve_character(character_id: str) -> dict[str, Any]:
    from ..services import character_service
    from ..services.errors import ServiceError

    try:
        return character_service.approve_character(character_id, actor="user")
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/{character_id}/model")
async def get_character_model(character_id: str) -> dict[str, Any]:
    character = _get(character_id)
    return {"character_id": character_id, "model": character.get("model") or {}}


@router.patch("/{character_id}/model")
async def update_character_model(character_id: str, payload: CharacterModelSettings) -> dict[str, Any]:
    character = _get(character_id)
    memory = character.get("memory") or {}
    if not isinstance(memory, dict):
        memory = {}
    model = memory.get("model") if isinstance(memory.get("model"), dict) else {}
    for key, value in payload.model_dump(exclude_none=True).items():
        model[key] = value
    memory["model"] = model
    execute(
        "UPDATE characters SET memory_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(memory), now(), character_id),
    )
    return _get(character_id)


@router.post("/{character_id}/canonical")
async def set_canonical_asset(character_id: str, payload: CanonicalAsset) -> dict[str, Any]:
    character = _get(character_id)
    asset = query_one("SELECT id, project_id, kind FROM assets WHERE id = ?", (payload.asset_id,))
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")
    if asset["project_id"] and character["project_id"] and asset["project_id"] != character["project_id"]:
        raise HTTPException(status_code=400, detail="Asset belongs to a different project.")
    if asset["kind"] != "image":
        raise HTTPException(status_code=400, detail="The canonical asset must be an image.")
    execute(
        "UPDATE characters SET canonical_asset_id = ?, updated_at = ? WHERE id = ?",
        (payload.asset_id, now(), character_id),
    )
    return _get(character_id)


@router.delete("/{character_id}/canonical")
async def clear_canonical_asset(character_id: str) -> dict[str, Any]:
    _get(character_id)
    execute(
        "UPDATE characters SET canonical_asset_id = NULL, updated_at = ? WHERE id = ?",
        (now(), character_id),
    )
    return _get(character_id)


@router.post("/{character_id}/generate", status_code=202)
async def generate_character_media(character_id: str, payload: CharacterGenerateRequest) -> dict[str, Any]:
    from ..services import character_service
    from ..services.errors import ServiceError

    try:
        return await character_service.generate_sheet(
            character_id,
            kind=payload.kind,
            label=payload.label,
            width=payload.width,
            height=payload.height,
            steps=payload.steps,
            cfg=payload.cfg,
            seed=payload.seed,
            prompt=payload.prompt,
            negative_prompt=payload.negative_prompt,
            reference_asset_id=payload.reference_asset_id,
            reference_mode=payload.reference_mode,
            denoise=payload.denoise,
            control_strength=payload.control_strength,
            actor="user",
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except (ValueError, ComfyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{character_id}/sheet/{kind}", status_code=202)
async def generate_character_sheet(
    character_id: str,
    kind: str,
    payload: CharacterSheetRequest,
) -> dict[str, Any]:
    from ..services.errors import ServiceError

    try:
        return await character_sheet_service.generate_sheet(
            character_id,
            kind,
            reference_asset_id=payload.reference_asset_id,
            allow_unapproved_reference=payload.allow_unapproved_reference,
            seed=payload.seed,
            steps=payload.steps,
            cfg=payload.cfg,
            denoise=payload.denoise,
            width=payload.width,
            height=payload.height,
            architecture=payload.architecture,
            checkpoint=payload.checkpoint,
            vae=payload.vae,
            lora_name=payload.lora_name,
            lora_strength=payload.lora_strength,
            actor="user",
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{character_id}/sheets/{sheet_id}")
async def get_character_sheet(character_id: str, sheet_id: str) -> dict[str, Any]:
    _get(character_id)
    return character_sheet_service.get_sheet(character_id, sheet_id)


@router.get("/{character_id}/sheets")
async def list_character_sheets(character_id: str, limit: int = 20) -> list[dict[str, Any]]:
    _get(character_id)
    return character_sheet_service.list_sheets(character_id, limit)


@router.get("/{character_id}/jobs")
async def character_jobs(character_id: str, limit: int = 20) -> list[dict[str, Any]]:
    _get(character_id)
    from ..services.jobs import list_jobs

    matches = [
        job
        for job in list_jobs(limit=200, project_id=None)
        if ((job.get("params") or {}).get("attach") or {}).get("owner_id") == character_id
    ]
    return matches[: min(limit, 100)]


@router.post("/{character_id}/consistency-check")
async def consistency_check(character_id: str, payload: ConsistencyCheckRequest) -> dict[str, Any]:
    _get(character_id)
    try:
        return await consistency_service.check_identity(
            character_id,
            payload.candidate_asset_id,
            model=payload.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
