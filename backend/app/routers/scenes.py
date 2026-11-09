from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from ..comfy.client import ComfyClient, ComfyError
from ..config import load_config
from ..db import execute, now, query, query_one
from ..schemas import (
    SceneCastAdd,
    SceneCreate,
    SceneGenerateRequest,
    SceneMediaAttach,
    SceneUpdate,
)
from ..services.creative import NEGATIVE_DEFAULT, scene_prompt
from ..services.conditioning import controlnet_model, resolve_image_mode
from ..services.generation import submit_image, submit_video, upload_start_image
from ..services.media import link_asset, list_media
from ..services.scenes import (
    decorate_scene,
    get_scene,
    raw_scene,
    scene_characters,
    scene_settings,
)

router = APIRouter(prefix="/api/scenes", tags=["scenes"])


def _get(scene_id: str) -> dict[str, Any]:
    scene = get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found.")
    return scene


def _require_project(project_id: str) -> None:
    if not query_one("SELECT id FROM projects WHERE id = ?", (project_id,)):
        raise HTTPException(status_code=404, detail="Project not found.")


def _validate_background(background_id: str, project_id: str) -> None:
    row = query_one(
        "SELECT id FROM backgrounds WHERE id = ? AND project_id = ?",
        (background_id, project_id),
    )
    if not row:
        raise HTTPException(status_code=400, detail="Background is not part of this project.")


def _validate_characters(character_ids: list[str], project_id: str) -> list[str]:
    unique = list(dict.fromkeys(character_ids))
    for character_id in unique:
        row = query_one(
            "SELECT id FROM characters WHERE id = ? AND project_id = ?",
            (character_id, project_id),
        )
        if not row:
            raise HTTPException(status_code=400, detail=f"Character {character_id} is not part of this project.")
    return unique


def _replace_cast(scene_id: str, character_ids: list[str], project_id: str) -> None:
    unique = _validate_characters(character_ids, project_id)
    execute("DELETE FROM scene_cast WHERE scene_id = ?", (scene_id,))
    for character_id in unique:
        execute(
            """INSERT INTO scene_cast (id, scene_id, character_id, role, created_at)
               VALUES (?, ?, ?, 'main', ?)""",
            (uuid.uuid4().hex[:12], scene_id, character_id, now()),
        )


def _image_size(
    payload: SceneGenerateRequest,
    settings: dict[str, Any],
    background: dict[str, Any] | None,
) -> tuple[int, int]:
    width = payload.width or settings.get("width") or (background or {}).get("width") or 768
    height = payload.height or settings.get("height") or (background or {}).get("height") or 432
    scale = min(1.0, 1024 / max(int(width), int(height)))
    width = max(64, int(round(int(width) * scale / 8)) * 8)
    height = max(64, int(round(int(height) * scale / 8)) * 8)
    return width, height


def _video_size(width: int, height: int) -> tuple[int, int]:
    width = max(32, int(round(int(width) / 32)) * 32)
    height = max(32, int(round(int(height) / 32)) * 32)
    return width, height


def _video_length(value: int) -> int:
    value = max(1, int(value))
    return ((value - 1) // 4) * 4 + 1


@router.get("")
async def list_scenes(project_id: str | None = None) -> list[dict[str, Any]]:
    if project_id:
        rows = query(
            "SELECT * FROM scenes WHERE project_id = ? ORDER BY updated_at DESC",
            (project_id,),
        )
    else:
        rows = query("SELECT * FROM scenes ORDER BY updated_at DESC")
    return [decorate_scene(row) for row in rows]


@router.post("", status_code=201)
async def create_scene(payload: SceneCreate) -> dict[str, Any]:
    _require_project(payload.project_id)
    settings = dict(payload.settings or {})
    if payload.background_id:
        _validate_background(payload.background_id, payload.project_id)
        settings["background_id"] = payload.background_id

    scene_id = uuid.uuid4().hex[:12]
    timestamp = now()
    execute(
        """INSERT INTO scenes
           (id, project_id, name, description, dialogue, action, camera, duration, settings_json, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            scene_id,
            payload.project_id,
            payload.name.strip(),
            payload.description.strip(),
            payload.dialogue.strip(),
            payload.action.strip(),
            payload.camera.strip(),
            payload.duration,
            json.dumps(settings),
            timestamp,
            timestamp,
        ),
    )
    _replace_cast(scene_id, payload.character_ids, payload.project_id)
    return _get(scene_id)


@router.get("/{scene_id}")
async def get_scene_detail(scene_id: str) -> dict[str, Any]:
    return _get(scene_id)


@router.patch("/{scene_id}")
async def update_scene(scene_id: str, payload: SceneUpdate) -> dict[str, Any]:
    scene = raw_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found.")
    project_id = scene["project_id"]
    fields = payload.model_fields_set

    updates: list[str] = []
    params: list[Any] = []
    for field in ("name", "description", "dialogue", "action", "camera", "duration"):
        if field not in fields:
            continue
        value = getattr(payload, field)
        if field == "name":
            value = (value or "").strip()
            if not value:
                raise HTTPException(status_code=400, detail="Scene name cannot be empty.")
        elif isinstance(value, str):
            value = value.strip()
        updates.append(f"{field} = ?")
        params.append(value)

    settings = scene_settings(scene)
    settings_changed = False
    if "background_id" in fields:
        if payload.background_id:
            _validate_background(payload.background_id, project_id)
            settings["background_id"] = payload.background_id
        else:
            settings.pop("background_id", None)
        settings_changed = True
    if "settings" in fields and payload.settings:
        settings.update(payload.settings)
        settings_changed = True
    if settings_changed:
        updates.append("settings_json = ?")
        params.append(json.dumps(settings))

    if "character_ids" in fields:
        _replace_cast(scene_id, payload.character_ids or [], project_id)

    if updates or "character_ids" in fields:
        updates.append("updated_at = ?")
        params.append(now())
        params.append(scene_id)
        execute(f"UPDATE scenes SET {', '.join(updates)} WHERE id = ?", params)
    return _get(scene_id)


@router.get("/{scene_id}/media")
async def scene_media(scene_id: str, role: str | None = None) -> list[dict[str, Any]]:
    _get(scene_id)
    return list_media("scene", scene_id, role=role)


@router.get("/{scene_id}/references")
async def scene_references(scene_id: str) -> list[dict[str, Any]]:
    """Collect every usable visual reference for this scene's cast and its keyframes."""
    scene = _get(scene_id)
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    cast = query(
        """SELECT c.id AS character_id, c.name, c.canonical_asset_id
           FROM scene_cast sc JOIN characters c ON c.id = sc.character_id
           WHERE sc.scene_id = ?
           ORDER BY sc.created_at ASC""",
        (scene_id,),
    )
    for member in cast:
        canonical = member.get("canonical_asset_id")
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(
                {
                    "character_id": member["character_id"],
                    "character_name": member["name"],
                    "asset_id": canonical,
                    "url": f"/api/assets/{canonical}/file",
                    "role": "canonical",
                    "label": "Identity",
                    "source": "canonical",
                }
            )
        for item in list_media("character", member["character_id"]):
            if item["role"] not in ("reference", "pose") or item["id"] in seen:
                continue
            seen.add(item["id"])
            result.append(
                {
                    "character_id": member["character_id"],
                    "character_name": member["name"],
                    "asset_id": item["id"],
                    "url": item["url"],
                    "role": item["role"],
                    "label": item.get("label") or item["role"],
                    "source": "media",
                }
            )
    for item in list_media("scene", scene_id, role="keyframe"):
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        result.append(
            {
                "character_id": None,
                "character_name": scene["name"],
                "asset_id": item["id"],
                "url": item["url"],
                "role": "keyframe",
                "label": item.get("label") or "Keyframe",
                "source": "scene",
            }
        )
    return result


@router.post("/{scene_id}/media", status_code=201)
async def attach_scene_media(scene_id: str, payload: SceneMediaAttach) -> dict[str, Any]:
    scene = _get(scene_id)
    asset = query_one("SELECT id, project_id FROM assets WHERE id = ?", (payload.asset_id,))
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")
    if asset["project_id"] and scene["project_id"] and asset["project_id"] != scene["project_id"]:
        raise HTTPException(status_code=400, detail="Asset belongs to a different project.")
    try:
        link = link_asset(
            "scene",
            scene_id,
            payload.asset_id,
            role=payload.role,
            label=payload.label.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**link, "scene_id": scene_id}


@router.post("/{scene_id}/cast", status_code=201)
async def add_scene_cast(scene_id: str, payload: SceneCastAdd) -> dict[str, Any]:
    scene = _get(scene_id)
    _validate_characters([payload.character_id], scene["project_id"])
    existing = query_one(
        "SELECT id FROM scene_cast WHERE scene_id = ? AND character_id = ?",
        (scene_id, payload.character_id),
    )
    if existing:
        execute("UPDATE scene_cast SET role = ? WHERE id = ?", (payload.role, existing["id"]))
    else:
        execute(
            """INSERT INTO scene_cast (id, scene_id, character_id, role, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (uuid.uuid4().hex[:12], scene_id, payload.character_id, payload.role, now()),
        )
    execute("UPDATE scenes SET updated_at = ? WHERE id = ?", (now(), scene_id))
    return _get(scene_id)


@router.delete("/{scene_id}/cast/{character_id}")
async def remove_scene_cast(scene_id: str, character_id: str) -> dict[str, Any]:
    _get(scene_id)
    execute(
        "DELETE FROM scene_cast WHERE scene_id = ? AND character_id = ?",
        (scene_id, character_id),
    )
    execute("UPDATE scenes SET updated_at = ? WHERE id = ?", (now(), scene_id))
    return _get(scene_id)


@router.post("/{scene_id}/generate", status_code=202)
async def generate_scene(scene_id: str, payload: SceneGenerateRequest) -> dict[str, Any]:
    scene = _get(scene_id)
    project_id = scene["project_id"]
    if not project_id:
        raise HTTPException(status_code=400, detail="Scene is not attached to a project.")
    settings = scene["settings"]
    background = scene["background"]
    characters = scene_characters(scene_id)
    prompt = scene_prompt(scene, background, characters, payload.kind, payload.prompt)

    try:
        if payload.kind == "keyframe":
            width, height = _image_size(payload, settings, background)
            reference_asset_id = payload.reference_asset_id or settings.get("reference_asset_id")
            reference_mode = (
                payload.reference_mode
                if "reference_mode" in payload.model_fields_set
                else settings.get("reference_mode", "identity")
            )
            denoise = (
                payload.denoise
                if "denoise" in payload.model_fields_set
                else settings.get("denoise", payload.denoise)
            )
            control_strength = (
                payload.control_strength
                if "control_strength" in payload.model_fields_set
                else settings.get("control_strength", payload.control_strength)
            )
            workflow_id = payload.workflow_id or settings.get("workflow_id")
            input_image = None
            control_net_name = None
            mode = "text-to-image"
            if reference_asset_id:
                config = load_config()
                client = ComfyClient(
                    config["comfyui"]["server_url"],
                    timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
                )
                object_info = await client.object_info()
                mode = resolve_image_mode(object_info, reference_mode, True)
                if mode == "controlnet-pose":
                    workflow_id = workflow_id or "sd15_controlnet_pose"
                    control_net_name = controlnet_model(object_info)
                input_image = await upload_start_image(
                    config, client, reference_asset_id, project_id
                )
            job = await submit_image(
                project_id=project_id,
                prompt=prompt,
                negative_prompt=payload.negative_prompt or NEGATIVE_DEFAULT,
                width=width,
                height=height,
                steps=payload.steps or settings.get("steps") or 24,
                cfg=payload.cfg if payload.cfg is not None else settings.get("cfg", 7.0),
                seed=payload.seed if payload.seed is not None else settings.get("seed", -1),
                workflow_id=workflow_id,
                input_image=input_image,
                denoise=denoise if reference_asset_id else None,
                control_strength=control_strength if mode == "controlnet-pose" else None,
                control_net_name=control_net_name,
                scene_id=scene_id,
                attach={
                    "owner_type": "scene",
                    "owner_id": scene_id,
                    "role": "keyframe",
                    "label": "keyframe",
                },
            )
            return {
                "job": job,
                "prompt": prompt,
                "kind": "keyframe",
                "width": width,
                "height": height,
                "mode": mode,
                "input_image": input_image,
                "reference_asset_id": reference_asset_id,
                "fallback": bool(reference_asset_id)
                and reference_mode == "pose"
                and mode != "controlnet-pose",
            }

        width, height = _video_size(
            payload.width or settings.get("video_width") or 832,
            payload.height or settings.get("video_height") or 480,
        )
        length = _video_length(payload.length or settings.get("length") or 121)
        if payload.start_image is not None:
            start_asset = payload.start_image or None
        else:
            start_asset = settings.get("start_image")
        input_image = None
        if start_asset:
            config = load_config()
            client = ComfyClient(
                config["comfyui"]["server_url"],
                timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
            )
            input_image = await upload_start_image(config, client, start_asset, project_id)

        job = await submit_video(
            project_id=project_id,
            prompt=prompt,
            negative_prompt=payload.negative_prompt,
            width=width,
            height=height,
            steps=payload.steps or settings.get("video_steps") or 20,
            cfg=payload.cfg if payload.cfg is not None else settings.get("video_cfg", 5.0),
            seed=payload.seed if payload.seed is not None else settings.get("video_seed", -1),
            length=length,
            fps=payload.fps or settings.get("fps") or 24,
            sampler=settings.get("sampler") or "uni_pc",
            scheduler=settings.get("scheduler") or "simple",
            input_image=input_image,
            workflow_id=payload.workflow_id or settings.get("video_workflow_id"),
            scene_id=scene_id,
            attach={
                "owner_type": "scene",
                "owner_id": scene_id,
                "role": "video",
                "label": "shot",
            },
        )
        return {
            "job": job,
            "prompt": prompt,
            "kind": "video",
            "width": width,
            "height": height,
            "length": length,
            "input_image": input_image,
        }
    except (ValueError, ComfyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{scene_id}/jobs")
async def scene_jobs(scene_id: str, limit: int = 20) -> list[dict[str, Any]]:
    _get(scene_id)
    from ..services.jobs import list_jobs

    matches = [job for job in list_jobs(limit=200) if job.get("scene_id") == scene_id]
    return matches[: min(limit, 100)]
