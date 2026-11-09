from __future__ import annotations

import json
import uuid
from typing import Any

from ..comfy.client import ComfyClient
from ..config import load_config
from ..db import execute, now, query, query_one
from ..providers.registry import registry
from .approval_service import approve_scene as approve_scene_record
from .approval_service import reject_scene as reject_scene_record
from .audit_service import log
from .conditioning import controlnet_model, resolve_image_mode
from .creative import NEGATIVE_DEFAULT, VIDEO_NEGATIVE, scene_prompt
from .errors import NotFoundError, ServiceError
from .generation import upload_start_image
from .media import list_media
from .scenes import decorate_scene, get_scene, raw_scene, scene_characters, scene_settings


def list_scenes(project_id: str | None = None) -> list[dict[str, Any]]:
    if project_id:
        rows = query("SELECT * FROM scenes WHERE project_id = ? ORDER BY updated_at DESC", (project_id,))
    else:
        rows = query("SELECT * FROM scenes ORDER BY updated_at DESC")
    return [decorate_scene(row) for row in rows]


def get_scene_details(scene_id: str) -> dict[str, Any]:
    scene = get_scene(scene_id)
    if not scene:
        raise NotFoundError("Scene not found.")
    return scene


def create_scene(
    project_id: str,
    *,
    name: str,
    description: str = "",
    dialogue_text: str = "",
    action: str = "",
    camera: str = "",
    duration: float = 5.0,
    background_id: str | None = None,
    character_ids: list[str] | None = None,
    settings: dict[str, Any] | None = None,
    actor: str = "user",
) -> dict[str, Any]:
    if not query_one("SELECT id FROM projects WHERE id = ?", (project_id,)):
        raise NotFoundError("Project not found.")
    settings = dict(settings or {})
    if background_id:
        if not query_one(
            "SELECT id FROM backgrounds WHERE id = ? AND project_id = ?",
            (background_id, project_id),
        ):
            raise ServiceError("Background is not part of this project.")
        settings["background_id"] = background_id
    scene_id = uuid.uuid4().hex[:12]
    timestamp = now()
    execute(
        """INSERT INTO scenes
           (id, project_id, name, description, dialogue, action, camera, duration, settings_json, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            scene_id,
            project_id,
            name.strip(),
            description.strip(),
            dialogue_text.strip(),
            action.strip(),
            camera.strip(),
            duration,
            json.dumps(settings),
            timestamp,
            timestamp,
        ),
    )
    _replace_cast(scene_id, list(character_ids or []), project_id)
    log(actor, "create_scene", "scene", scene_id, {"name": name})
    return get_scene_details(scene_id)


def _replace_cast(scene_id: str, character_ids: list[str], project_id: str) -> None:
    unique = list(dict.fromkeys(character_ids))
    for character_id in unique:
        if not query_one(
            "SELECT id FROM characters WHERE id = ? AND project_id = ?",
            (character_id, project_id),
        ):
            raise ServiceError(f"Character {character_id} is not part of this project.")
    execute("DELETE FROM scene_cast WHERE scene_id = ?", (scene_id,))
    for character_id in unique:
        execute(
            """INSERT INTO scene_cast (id, scene_id, character_id, role, created_at)
               VALUES (?, ?, ?, 'main', ?)""",
            (uuid.uuid4().hex[:12], scene_id, character_id, now()),
        )


def update_scene(scene_id: str, updates: dict[str, Any], actor: str = "user") -> dict[str, Any]:
    scene = raw_scene(scene_id)
    if not scene:
        raise NotFoundError("Scene not found.")
    project_id = scene["project_id"]
    fields = set(updates)
    sql_parts: list[str] = []
    params: list[Any] = []
    for field in ("name", "description", "dialogue", "action", "camera", "duration"):
        if field not in fields:
            continue
        value = updates[field]
        if field == "name":
            value = str(value or "").strip()
            if not value:
                raise ServiceError("Scene name cannot be empty.")
        sql_parts.append(f"{field} = ?")
        params.append(value)
    settings = scene_settings(scene)
    if "background_id" in fields:
        background_id = updates.get("background_id")
        if background_id:
            if not query_one(
                "SELECT id FROM backgrounds WHERE id = ? AND project_id = ?",
                (background_id, project_id),
            ):
                raise ServiceError("Background is not part of this project.")
            settings["background_id"] = background_id
        else:
            settings.pop("background_id", None)
        sql_parts.append("settings_json = ?")
        params.append(json.dumps(settings))
    if "settings" in fields and isinstance(updates["settings"], dict):
        settings.update(updates["settings"])
        sql_parts.append("settings_json = ?")
        params.append(json.dumps(settings))
    if "character_ids" in fields:
        _replace_cast(scene_id, list(updates.get("character_ids") or []), project_id)
    if sql_parts:
        sql_parts.append("updated_at = ?")
        params.extend([now(), scene_id])
        execute(f"UPDATE scenes SET {', '.join(sql_parts)} WHERE id = ?", params)
    log(actor, "update_scene", "scene", scene_id, {"fields": sorted(fields)})
    return get_scene_details(scene_id)


def _image_size(scene: dict[str, Any], width: int | None, height: int | None, settings: dict[str, Any]) -> tuple[int, int]:
    background = scene.get("background") or {}
    w = width or settings.get("width") or background.get("width") or 768
    h = height or settings.get("height") or background.get("height") or 432
    scale = min(1.0, 1024 / max(int(w), int(h)))
    return max(64, int(round(int(w) * scale / 8)) * 8), max(64, int(round(int(h) * scale / 8)) * 8)


async def generate_scene_image(
    scene_id: str,
    *,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    width: int | None = None,
    height: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    seed: int | None = None,
    workflow_id: str | None = None,
    reference_asset_id: str | None = None,
    reference_mode: str = "identity",
    denoise: float = 0.55,
    control_strength: float = 0.8,
    actor: str = "user",
) -> dict[str, Any]:
    scene = get_scene_details(scene_id)
    project_id = scene["project_id"]
    if not project_id:
        raise ServiceError("Scene is not attached to a project.")
    settings = scene_settings(raw_scene(scene_id) or {})
    characters = scene_characters(scene_id)
    composed = scene_prompt(scene, scene.get("background"), characters, "keyframe", prompt)
    target_w, target_h = _image_size(scene, width, height, settings)
    reference_asset_id = reference_asset_id or settings.get("reference_asset_id")
    input_image = None
    mode = "text-to-image"
    control_net_name = None
    config = load_config()
    client = ComfyClient(
        config["comfyui"]["server_url"],
        timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
    )
    if reference_asset_id:
        object_info = await client.object_info()
        mode = resolve_image_mode(object_info, reference_mode, True)
        if mode == "controlnet-pose":
            workflow_id = workflow_id or "sd15_controlnet_pose"
            control_net_name = controlnet_model(object_info)
        input_image = await upload_start_image(config, client, reference_asset_id, project_id)
    provider = registry.get("image")
    result = await provider.generate_image(
        project_id=project_id,
        prompt=composed,
        negative_prompt=negative_prompt or NEGATIVE_DEFAULT,
        width=target_w,
        height=target_h,
        steps=steps or settings.get("steps") or 28,
        cfg=cfg if cfg is not None else settings.get("cfg", 6.5),
        seed=seed if seed is not None else settings.get("seed", -1),
        workflow_id=workflow_id or settings.get("workflow_id"),
        scene_id=scene_id,
        input_image=input_image,
        denoise=denoise if reference_asset_id else None,
        control_strength=control_strength if mode == "controlnet-pose" else None,
        control_net_name=control_net_name,
        attach={
            "owner_type": "scene",
            "owner_id": scene_id,
            "role": "keyframe",
            "label": "keyframe",
        },
    )
    log(actor, "generate_scene_image", "scene", scene_id, {"mode": mode, "job_id": result.get("job_id")})
    return {
        **result,
        "scene_id": scene_id,
        "prompt": composed,
        "mode": mode,
        "width": target_w,
        "height": target_h,
        "reference_asset_id": reference_asset_id,
        "fallback": bool(reference_asset_id) and reference_mode == "pose" and mode != "controlnet-pose",
    }


async def regenerate_scene(scene_id: str, **kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("seed", -1)
    return await generate_scene_image(scene_id, **kwargs)


async def animate_scene(
    scene_id: str,
    *,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    width: int | None = None,
    height: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    seed: int | None = None,
    length: int | None = None,
    fps: float | None = None,
    start_image: str | None = None,
    workflow_id: str | None = None,
    actor: str = "user",
) -> dict[str, Any]:
    scene = get_scene_details(scene_id)
    project_id = scene["project_id"]
    if not project_id:
        raise ServiceError("Scene is not attached to a project.")
    settings = scene_settings(raw_scene(scene_id) or {})
    characters = scene_characters(scene_id)
    composed = scene_prompt(scene, scene.get("background"), characters, "video", prompt)
    media = list_media("scene", scene_id)
    keyframes = [item for item in media if item["role"] == "keyframe"]
    if start_image is None and keyframes:
        start_image = keyframes[-1]["id"]
    input_image = None
    if start_image:
        config = load_config()
        client = ComfyClient(
            config["comfyui"]["server_url"],
            timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
        )
        input_image = await upload_start_image(config, client, start_image, project_id)
    provider = registry.get("video")
    result = await provider.generate_video(
        project_id=project_id,
        prompt=composed,
        negative_prompt=negative_prompt or VIDEO_NEGATIVE,
        width=width or settings.get("video_width") or 832,
        height=height or settings.get("video_height") or 480,
        steps=steps or settings.get("video_steps") or 20,
        cfg=cfg if cfg is not None else settings.get("video_cfg", 5.0),
        seed=seed if seed is not None else settings.get("video_seed", -1),
        length=length or settings.get("length") or 121,
        fps=fps or settings.get("fps") or 24,
        sampler=settings.get("sampler") or "uni_pc",
        scheduler=settings.get("scheduler") or "simple",
        input_image=input_image,
        workflow_id=workflow_id or settings.get("video_workflow_id"),
        scene_id=scene_id,
        attach={"owner_type": "scene", "owner_id": scene_id, "role": "video", "label": "shot"},
    )
    log(actor, "animate_scene", "scene", scene_id, {"job_id": result.get("job_id")})
    return {**result, "scene_id": scene_id, "prompt": composed, "input_image": input_image}


async def regenerate_animation(scene_id: str, **kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("seed", -1)
    return await animate_scene(scene_id, **kwargs)


def get_animation_preview(scene_id: str) -> dict[str, Any]:
    get_scene_details(scene_id)
    videos = [item for item in list_media("scene", scene_id) if item["role"] == "video"]
    return {"scene_id": scene_id, "videos": videos, "latest": videos[-1] if videos else None}


def approve_scene(scene_id: str, actor: str = "user", notes: str = "") -> dict[str, Any]:
    return approve_scene_record(scene_id, actor=actor, notes=notes)


def reject_scene(scene_id: str, actor: str = "user", notes: str = "") -> dict[str, Any]:
    return reject_scene_record(scene_id, actor=actor, notes=notes)


def approve_animation(scene_id: str, actor: str = "user") -> dict[str, Any]:
    preview = get_animation_preview(scene_id)
    if not preview["latest"]:
        raise ServiceError("No animation is available to approve.")
    result = approve_scene_record(scene_id, actor=actor, notes="Animation approved.")
    return {**result, "asset_id": preview["latest"]["id"]}
