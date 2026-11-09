from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from ..config import load_config
from ..db import execute, now
from . import dialogue_service, episode_service, model_config_service, resource_manager, scene_service
from .audit_service import log
from .errors import NotFoundError, ServiceError
from .media import list_media

DEFAULT_SHOT_SECONDS = 6.0


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _shot_count(duration_seconds: float) -> int:
    return max(1, min(20, int(round(max(1.0, duration_seconds) / DEFAULT_SHOT_SECONDS))))


def _shot_windows(total_seconds: float, count: int) -> list[tuple[float, float]]:
    step = total_seconds / count
    return [(round(index * step, 3), round((index + 1) * step, 3)) for index in range(count)]


def _dialogue_for_window(lines: list[dict[str, Any]], start: float, end: float) -> list[dict[str, Any]]:
    result = []
    for line in lines:
        line_start = _as_float(line.get("start_ms")) / 1000.0
        line_duration = _as_float(line.get("duration_ms")) / 1000.0
        line_end = line_start + line_duration
        if line_start < end and line_end > start:
            result.append(
                {
                    "line_id": line.get("id"),
                    "character_id": line.get("character_id"),
                    "character_name": line.get("character_name"),
                    "text": line.get("text"),
                    "emotion": line.get("emotion"),
                    "start_ms": line.get("start_ms"),
                    "duration_ms": line.get("duration_ms"),
                    "audio_asset_id": line.get("audio_asset_id"),
                }
            )
    return result


def _scene_shots(episode: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    shots: list[dict[str, Any]] = []
    storyboard = episode.get("storyboard") or []
    if storyboard:
        scene_rows = storyboard
    else:
        scene_rows = [
            {"scene_id": scene["id"], "number": index + 1}
            for index, scene in enumerate(scene_service.list_scenes(episode["project_id"]))
        ]
    active_model = model_config_service.resolve_image_model(
        config,
        purpose="scene",
        input_image=False,
    )
    for scene_index, row in enumerate(scene_rows):
        scene_id = row.get("scene_id")
        if not scene_id:
            continue
        try:
            scene = scene_service.get_scene_details(scene_id)
        except NotFoundError:
            continue
        duration = _as_float(scene.get("duration"), DEFAULT_SHOT_SECONDS)
        count = _shot_count(duration)
        windows = _shot_windows(duration, count)
        lines = dialogue_service.list_lines(scene_id)
        media = list_media("scene", scene_id)
        videos = [item for item in media if item.get("role") == "video"]
        keyframes = [item for item in media if item.get("role") == "keyframe"]
        for shot_index, (start, end) in enumerate(windows, start=1):
            shot_uuid = uuid.uuid4().hex[:12]
            dialogue = _dialogue_for_window(lines, start, end)
            needs_keyframe = not keyframes
            needs_animation = bool(not videos)
            image_estimate = resource_manager.estimate_job(
                config,
                active_model["workflow_id"],
                dict(active_model.get("preset") or {}),
            )
            video_estimate = resource_manager.estimate_job(
                config,
                "wan22_i2v",
                {"width": 640, "height": 360, "steps": 8, "length": int(max(1, end - start) * 24)},
            )
            shots.append(
                {
                    "id": shot_uuid,
                    "scene_id": scene_id,
                    "scene_number": row.get("number") or scene_index + 1,
                    "shot_number": shot_index,
                    "label": f"Scene {row.get('number') or scene_index + 1} · Shot {shot_index}",
                    "start_seconds": round(start, 3),
                    "end_seconds": round(end, 3),
                    "duration_seconds": round(max(0.5, end - start), 3),
                    "characters": [
                        {
                            "character_id": member.get("character_id") or member.get("id"),
                            "name": member.get("name"),
                        }
                        for member in (scene.get("cast") or [])
                    ],
                    "background": {
                        "background_id": (scene.get("background") or {}).get("id"),
                        "name": (scene.get("background") or {}).get("name"),
                    },
                    "camera": scene.get("camera") or "",
                    "action": scene.get("action") or "",
                    "dialogue": dialogue,
                    "audio_requirements": {
                        "dialogue_count": len(dialogue),
                        "missing_audio": [item["line_id"] for item in dialogue if not item.get("audio_asset_id")],
                        "music": True,
                        "sound_effects": [],
                    },
                    "reference_asset_id": (keyframes[-1]["id"] if keyframes else None),
                    "generation_instructions": {
                        "image_prompt": " ".join(
                            part
                            for part in [
                                scene.get("name"),
                                scene.get("description"),
                                scene.get("action"),
                                "single animation keyframe, cinematic composition",
                            ]
                            if part
                        ),
                        "needs_keyframe": needs_keyframe,
                        "needs_animation": needs_animation,
                        "suggested_video_workflow": "wan22_i2v",
                        "animation_note": "Use a short low-resolution Wan clip on 6 GB; animate only shots that need motion.",
                    },
                    "estimate": {
                        "image_seconds": image_estimate["estimated_seconds"],
                        "animation_seconds": video_estimate["estimated_seconds"] if needs_animation else 0,
                        "image_vram_gb": image_estimate["estimated_vram_gb"],
                        "animation_vram_gb": video_estimate["estimated_vram_gb"] if needs_animation else 0,
                    },
                    "status": "planned",
                    "approval_status": "draft",
                    "notes": "",
                }
            )
    return shots


def build_shot_plan(episode_id: str, actor: str = "user") -> dict[str, Any]:
    episode = episode_service.get_episode(episode_id)
    config = load_config()
    shots = _scene_shots(episode, config)
    if not shots:
        raise ServiceError("No scenes are available to plan. Create a storyboard or scenes first.")
    total_image_seconds = sum(shot["estimate"]["image_seconds"] for shot in shots)
    total_animation_seconds = sum(shot["estimate"]["animation_seconds"] for shot in shots)
    total_dialogue = sum(shot["audio_requirements"]["dialogue_count"] for shot in shots)
    missing_keyframes = sum(1 for shot in shots if shot["generation_instructions"]["needs_keyframe"])
    missing_animations = sum(1 for shot in shots if shot["generation_instructions"]["needs_animation"])
    plan = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "episode_id": episode_id,
        "project_id": episode["project_id"],
        "episode_name": episode.get("name"),
        "shot_count": len(shots),
        "shots": shots,
        "estimate": {
            "image_seconds": round(total_image_seconds, 1),
            "animation_seconds": round(total_animation_seconds, 1),
            "total_gpu_seconds": round(total_image_seconds + total_animation_seconds, 1),
            "total_gpu_minutes": round((total_image_seconds + total_animation_seconds) / 60.0, 1),
            "dialogue_lines": total_dialogue,
            "missing_keyframes": missing_keyframes,
            "missing_animations": missing_animations,
            "note": "Rough 6 GB profile estimate. Actual time depends on model, offloading and shot length.",
        },
    }
    production = episode.get("production") or {}
    production["shot_plan"] = plan
    execute(
        "UPDATE episodes SET production_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(production), now(), episode_id),
    )
    log(actor, "build_shot_plan", "episode", episode_id, {"shots": len(shots)})
    return plan


def get_shot_plan(episode_id: str) -> dict[str, Any]:
    episode = episode_service.get_episode(episode_id)
    plan = (episode.get("production") or {}).get("shot_plan")
    if not plan:
        raise NotFoundError("No shot plan has been built for this episode.")
    return plan


def estimate_episode(episode_id: str) -> dict[str, Any]:
    try:
        plan = get_shot_plan(episode_id)
        return plan.get("estimate") or {}
    except NotFoundError:
        episode = episode_service.get_episode(episode_id)
        shots = _scene_shots(episode, load_config())
        total = sum(shot["estimate"]["image_seconds"] + shot["estimate"]["animation_seconds"] for shot in shots)
        return {
            "shot_count": len(shots),
            "image_seconds": round(sum(shot["estimate"]["image_seconds"] for shot in shots), 1),
            "animation_seconds": round(sum(shot["estimate"]["animation_seconds"] for shot in shots), 1),
            "total_gpu_seconds": round(total, 1),
            "total_gpu_minutes": round(total / 60.0, 1),
            "note": "Preview estimate. Build the shot plan to persist it.",
        }


def update_shot_status(episode_id: str, shot_id: str, status: str, notes: str = "", actor: str = "user") -> dict[str, Any]:
    episode = episode_service.get_episode(episode_id)
    production = episode.get("production") or {}
    plan = production.get("shot_plan")
    if not plan:
        raise NotFoundError("No shot plan has been built for this episode.")
    updated = False
    for shot in plan.get("shots", []):
        if shot.get("id") == shot_id:
            shot["status"] = status
            shot["notes"] = notes
            updated = True
            break
    if not updated:
        raise NotFoundError("Shot not found in this episode's shot plan.")
    execute(
        "UPDATE episodes SET production_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(production), now(), episode_id),
    )
    log(actor, "update_shot_status", "episode", episode_id, {"shot_id": shot_id, "status": status})
    return plan


def production_report(project_id: str | None = None) -> dict[str, Any]:
    from ..db import query, query_one

    def count(table: str, where: str = "", params: tuple[Any, ...] = ()) -> int:
        row = query_one(f"SELECT COUNT(*) AS n FROM {table} {where}", params)
        return int(row["n"] if row else 0)

    project_clause = "WHERE project_id = ?" if project_id else ""
    project_params = (project_id,) if project_id else ()
    job_clause = "WHERE project_id = ?" if project_id else ""
    statuses = {
        row["status"]: int(row["n"])
        for row in query(
            f"SELECT status, COUNT(*) AS n FROM jobs {job_clause} GROUP BY status",
            project_params,
        )
    }
    resource_rows = query(
        f"SELECT resource_class, COUNT(*) AS n, AVG(execution_seconds) AS avg_seconds, MAX(peak_vram_mb) AS peak_vram FROM jobs {job_clause} GROUP BY resource_class",
        project_params,
    )
    recent = query(
        f"SELECT id, project_id, workflow_id, workflow_name, status, resource_class, model_name, execution_seconds, peak_vram_mb, created_at FROM jobs {job_clause} ORDER BY created_at DESC LIMIT 20",
        project_params,
    )
    return {
        "project_id": project_id,
        "counts": {
            "projects": count("projects"),
            "characters": count("characters", project_clause, project_params),
            "backgrounds": count("backgrounds", project_clause, project_params),
            "scenes": count("scenes", project_clause, project_params),
            "episodes": count("episodes", project_clause, project_params),
            "assets": count("assets", project_clause, project_params),
            "jobs": count("jobs", job_clause, project_params),
            "production_runs": count("production_runs", project_clause, project_params),
        },
        "job_statuses": statuses,
        "resource_usage": [
            {
                "resource_class": row["resource_class"],
                "jobs": int(row["n"]),
                "avg_execution_seconds": round(float(row["avg_seconds"] or 0), 2),
                "peak_vram_mb": row["peak_vram"],
            }
            for row in resource_rows
        ],
        "recent_jobs": recent,
        "approvals": {
            "approved_characters": count("characters", "WHERE approval_status = 'approved'" + (" AND project_id = ?" if project_id else ""), project_params),
            "approved_scenes": count("scenes", "WHERE approval_status = 'approved'" + (" AND project_id = ?" if project_id else ""), project_params),
        },
    }
