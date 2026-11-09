from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..db import execute, now
from . import dialogue_service, episode_service, scene_service
from .approval_service import record_scene_review
from .asset_service import asset_file
from .assets import get_asset
from .episodes import output_path, subtitle_path
from .errors import NotFoundError
from .media import list_media


def _check(name: str, ok: bool, detail: str, required: bool = True) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail, "required": required}


def review_scene(scene_id: str, actor: str = "quality_control") -> dict[str, Any]:
    scene = scene_service.get_scene_details(scene_id)
    media = list_media("scene", scene_id)
    keyframes = [item for item in media if item["role"] == "keyframe"]
    videos = [item for item in media if item["role"] == "video"]
    audio = dialogue_service.audio_status(scene_id)
    checks: list[dict[str, Any]] = []
    checks.append(_check("scene_exists", True, scene_id))
    checks.append(_check("has_background", bool(scene.get("background")), "Scene background is set."))
    checks.append(_check("has_cast", bool(scene.get("cast")), "Scene has cast members."))
    checks.append(_check("has_keyframe", bool(keyframes), "At least one keyframe is attached."))
    if keyframes:
        resolved = asset_file(keyframes[-1]["id"])
        checks.append(_check("keyframe_file", bool(resolved), "Latest keyframe file exists."))
        if resolved:
            asset = resolved[1]
            width = int((asset.get("meta") or {}).get("width") or 0)
            height = int((asset.get("meta") or {}).get("height") or 0)
            checks.append(
                _check(
                    "keyframe_resolution",
                    width >= 512 and height >= 288,
                    f"{width}x{height}",
                )
            )
    checks.append(
        _check(
            "dialogue_audio",
            not audio["missing_audio"],
            f"{audio['with_audio']}/{audio['total']} lines have audio.",
        )
    )
    checks.append(
        _check(
            "animation_optional",
            bool(videos),
            "Animation is optional for a motion-comic scene.",
            required=False,
        )
    )
    checks.append(
        _check(
            "approved",
            scene.get("approval_status") == "approved",
            f"Approval status: {scene.get('approval_status', 'draft')}",
            required=False,
        )
    )
    failed_required = [check for check in checks if check["required"] and not check["ok"]]
    status = "failed" if failed_required else ("passed" if all(check["ok"] for check in checks if check["required"]) else "needs_review")
    report = {
        "entity_type": "scene",
        "scene_id": scene_id,
        "status": status,
        "checks": checks,
        "score": None,
        "ai_estimate": False,
        "human_review_required": True,
        "summary": (
            "All required checks passed."
            if status == "passed"
            else "; ".join(check["detail"] for check in failed_required) or "Optional checks remain."
        ),
    }
    record_scene_review(scene_id, report, actor=actor)
    return report


def review_episode(episode_id: str, actor: str = "quality_control") -> dict[str, Any]:
    episode = episode_service.get_episode(episode_id)
    timeline = episode.get("timeline") or {}
    segments = timeline.get("segments") or []
    audio = timeline.get("audio") or []
    checks: list[dict[str, Any]] = []
    checks.append(_check("has_segments", bool(segments), f"{len(segments)} segment(s)."))
    missing_assets = []
    for segment in segments:
        if not asset_file(segment.get("asset_id")):
            missing_assets.append(segment.get("asset_id"))
    checks.append(_check("segment_assets", not missing_assets, f"Missing: {missing_assets}" if missing_assets else "All segment assets exist."))
    checks.append(_check("has_audio", bool(audio or timeline.get("settings", {}).get("background_music_asset_id")), f"{len(audio)} audio track(s).", required=False))
    output = output_path(episode)
    checks.append(_check("rendered_output", bool(output), str(output.name) if output else "No rendered MP4 yet.", required=False))
    if output:
        checks.append(_check("output_size", output.stat().st_size > 10000, f"{output.stat().st_size} bytes."))
        checks.append(_check("subtitles", bool(subtitle_path(episode)), "SRT sidecar exists.", required=False))
    checks.append(
        _check(
            "duration",
            int(episode.get("duration_ms") or 0) > 0,
            f"{episode.get('duration_ms')}ms",
        )
    )
    failed_required = [check for check in checks if check["required"] and not check["ok"]]
    status = "failed" if failed_required else "passed" if all(check["ok"] for check in checks if check["required"]) else "needs_review"
    report = {
        "entity_type": "episode",
        "episode_id": episode_id,
        "status": status,
        "checks": checks,
        "score": None,
        "ai_estimate": False,
        "human_review_required": True,
        "summary": "All required checks passed." if status == "passed" else "; ".join(check["detail"] for check in failed_required) or "Optional checks remain.",
    }
    production = episode.get("production") or {}
    production["quality"] = report
    execute(
        "UPDATE episodes SET production_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(production), now(), episode_id),
    )
    return report


def get_quality_report(entity_type: str, entity_id: str) -> dict[str, Any]:
    if entity_type == "scene":
        scene = scene_service.get_scene_details(entity_id)
        return {"entity_type": "scene", "scene_id": entity_id, "report": scene.get("quality") or {}}
    if entity_type == "episode":
        episode = episode_service.get_episode(entity_id)
        return {"entity_type": "episode", "episode_id": entity_id, "report": (episode.get("production") or {}).get("quality") or {}}
    raise NotFoundError("Quality reports support scene or episode.")


def regenerate_failed_scenes(episode_id: str) -> list[str]:
    episode = episode_service.get_episode(episode_id)
    scene_ids: list[str] = []
    for segment in (episode.get("timeline") or {}).get("segments", []):
        if segment.get("scene_id") and segment["scene_id"] not in scene_ids:
            scene_ids.append(segment["scene_id"])
    for row in episode.get("storyboard") or []:
        if row.get("scene_id") and row["scene_id"] not in scene_ids:
            scene_ids.append(row["scene_id"])
    failed: list[str] = []
    for scene_id in scene_ids:
        try:
            scene = scene_service.get_scene_details(scene_id)
        except NotFoundError:
            continue
        quality = scene.get("quality") or {}
        if scene.get("approval_status") == "rejected" or quality.get("status") == "failed":
            failed.append(scene_id)
    return failed
