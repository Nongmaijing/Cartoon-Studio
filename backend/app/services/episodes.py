from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from ..config import load_config
from ..db import execute, now, query, query_one
from ..schemas import EpisodeTimeline


def _default_timeline() -> dict[str, Any]:
    return {
        "segments": [],
        "audio": [],
        "settings": {
            "width": 1280,
            "height": 720,
            "fps": 24.0,
            "subtitles": "soft",
            "background_music_asset_id": None,
            "background_music_volume": 0.35,
            "fade_duration_ms": 350,
        },
    }


def parse_timeline(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "{}")
        except json.JSONDecodeError:
            raw = {}
    if isinstance(raw, list):
        return {**_default_timeline(), "segments": raw}
    if not isinstance(raw, dict):
        return _default_timeline()
    result = _default_timeline()
    result.update({key: value for key, value in raw.items() if key in ("segments", "audio", "settings")})
    settings = _default_timeline()["settings"]
    settings.update(result.get("settings") or {})
    result["settings"] = settings
    result["segments"] = result.get("segments") or []
    result["audio"] = result.get("audio") or []
    for segment in result["segments"]:
        segment.setdefault("motion", "none")
    return result


def total_duration_ms(timeline: dict[str, Any]) -> int:
    return sum(max(0, int(segment.get("duration_ms") or 0)) for segment in timeline.get("segments") or [])


def _actual_kind(asset: dict[str, Any]) -> str:
    kind = str(asset.get("kind") or "").lower()
    mime = str(asset.get("mime") or "").lower()
    filename = str(asset.get("filename") or "").lower()
    if kind in ("video", "audio", "image"):
        return kind
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("image/"):
        return "image"
    for suffix in (".mp4", ".webm", ".mov", ".mkv", ".gif"):
        if filename.endswith(suffix):
            return "video"
    return "image"


def _asset(asset_id: str, project_id: str) -> dict[str, Any]:
    asset = query_one("SELECT * FROM assets WHERE id = ?", (asset_id,))
    if not asset:
        raise ValueError(f"Asset {asset_id} was not found.")
    if asset.get("project_id") and asset["project_id"] != project_id:
        raise ValueError(f"Asset {asset_id} belongs to a different project.")
    return asset


def validate_timeline(timeline: EpisodeTimeline, project_id: str) -> dict[str, Any]:
    data = timeline.model_dump()
    segments = data.get("segments") or []
    if not segments:
        raise ValueError("Add at least one scene segment before exporting.")
    for segment in segments:
        if not segment.get("id"):
            segment["id"] = uuid.uuid4().hex[:12]
        scene = query_one(
            "SELECT id FROM scenes WHERE id = ? AND project_id = ?",
            (segment["scene_id"], project_id),
        )
        if not scene:
            raise ValueError(f"Scene {segment['scene_id']} is not part of this project.")
        asset = _asset(str(segment["asset_id"]), project_id)
        actual = _actual_kind(asset)
        if actual not in ("image", "video"):
            raise ValueError(f"Asset {segment['asset_id']} is not an image or video.")
        if segment["kind"] != actual:
            segment["kind"] = actual
        segment["duration_ms"] = max(100, int(segment.get("duration_ms") or 3000))

    for audio in data.get("audio") or []:
        if not audio.get("id"):
            audio["id"] = uuid.uuid4().hex[:12]
        asset = _asset(str(audio["asset_id"]), project_id)
        if _actual_kind(asset) != "audio":
            raise ValueError(f"Asset {audio['asset_id']} is not audio.")
        audio["start_ms"] = max(0, int(audio.get("start_ms") or 0))
        audio["volume"] = max(0.0, min(2.0, float(audio.get("volume", 1.0))))

    settings = data.get("settings") or {}
    music_id = settings.get("background_music_asset_id")
    if music_id:
        asset = _asset(str(music_id), project_id)
        if _actual_kind(asset) != "audio":
            raise ValueError("Background music must be an audio asset.")
    width = int(settings.get("width") or 1280)
    height = int(settings.get("height") or 720)
    settings["width"] = max(64, width - (width % 2))
    settings["height"] = max(64, height - (height % 2))
    settings["fps"] = max(1.0, min(60.0, float(settings.get("fps") or 24.0)))
    settings["fade_duration_ms"] = max(0, min(2000, int(settings.get("fade_duration_ms") or 0)))
    data["settings"] = settings
    data["duration_ms"] = total_duration_ms(data)
    return data


def decorate_episode(row: dict[str, Any]) -> dict[str, Any]:
    timeline = parse_timeline(row.get("timeline_json"))
    row["timeline"] = timeline
    row["settings"] = timeline.get("settings") or {}
    row["segment_count"] = len(timeline.get("segments") or [])
    row["audio_count"] = len(timeline.get("audio") or [])
    computed = total_duration_ms(timeline)
    row["duration_ms"] = int(row.get("duration_ms") or computed)
    row["output_url"] = (
        f"/api/assets/{row['output_asset_id']}/file" if row.get("output_asset_id") else None
    )
    row["subtitle_url"] = f"/api/episodes/{row['id']}/subtitles" if row.get("subtitle_path") else None
    for key in ("production_json", "script_json"):
        try:
            row[key.replace("_json", "")] = json.loads(row.get(key) or "{}")
        except json.JSONDecodeError:
            row[key.replace("_json", "")] = {}
    try:
        parsed_storyboard = json.loads(row.get("storyboard_json") or "[]")
        row["storyboard"] = parsed_storyboard if isinstance(parsed_storyboard, list) else []
    except json.JSONDecodeError:
        row["storyboard"] = []
    row["production_state"] = row.get("production_state") or "DRAFT"
    return row


def list_episodes(project_id: str | None = None) -> list[dict[str, Any]]:
    if project_id:
        rows = query(
            "SELECT * FROM episodes WHERE project_id = ? ORDER BY updated_at DESC",
            (project_id,),
        )
    else:
        rows = query("SELECT * FROM episodes ORDER BY updated_at DESC")
    return [decorate_episode(row) for row in rows]


def get_episode(episode_id: str) -> dict[str, Any] | None:
    row = query_one("SELECT * FROM episodes WHERE id = ?", (episode_id,))
    return decorate_episode(row) if row else None


def create_episode(project_id: str, name: str, description: str = "") -> dict[str, Any]:
    episode_id = uuid.uuid4().hex[:12]
    timestamp = now()
    execute(
        """INSERT INTO episodes
           (id, project_id, name, description, status, progress, timeline_json, settings_json,
            duration_ms, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'draft', 0, ?, ?, 0, ?, ?)""",
        (
            episode_id,
            project_id,
            name.strip(),
            description.strip(),
            json.dumps(_default_timeline()),
            json.dumps(_default_timeline()["settings"]),
            timestamp,
            timestamp,
        ),
    )
    return get_episode(episode_id) or {}


def update_episode(episode_id: str, *, name: str | None = None, description: str | None = None) -> dict[str, Any]:
    updates: list[str] = []
    params: list[Any] = []
    if name is not None:
        updates.append("name = ?")
        params.append(name.strip())
    if description is not None:
        updates.append("description = ?")
        params.append(description.strip())
    if updates:
        updates.append("updated_at = ?")
        params.extend([now(), episode_id])
        execute(f"UPDATE episodes SET {', '.join(updates)} WHERE id = ?", params)
    return get_episode(episode_id) or {}


def save_timeline(episode_id: str, timeline: EpisodeTimeline) -> dict[str, Any]:
    episode = query_one("SELECT * FROM episodes WHERE id = ?", (episode_id,))
    if not episode:
        raise ValueError("Episode not found.")
    data = validate_timeline(timeline, episode["project_id"])
    execute(
        """UPDATE episodes
           SET timeline_json = ?, settings_json = ?, duration_ms = ?, updated_at = ?
           WHERE id = ?""",
        (
            json.dumps(data),
            json.dumps(data["settings"]),
            data["duration_ms"],
            now(),
            episode_id,
        ),
    )
    return get_episode(episode_id) or {}


def delete_episode(episode_id: str) -> None:
    execute("DELETE FROM episodes WHERE id = ?", (episode_id,))


def output_path(episode: dict[str, Any]) -> Path | None:
    rel = episode.get("output_path")
    if not rel:
        return None
    config = load_config()
    root = Path(config["paths"]["output_dir"]).resolve()
    path = (root / rel).resolve()
    if root not in path.parents and path != root:
        return None
    return path if path.exists() else None


def subtitle_path(episode: dict[str, Any]) -> Path | None:
    rel = episode.get("subtitle_path")
    if not rel:
        return None
    config = load_config()
    root = Path(config["paths"]["output_dir"]).resolve()
    path = (root / rel).resolve()
    if root not in path.parents and path != root:
        return None
    return path if path.exists() else None


def mark_interrupted_exports() -> None:
    execute(
        "UPDATE episodes SET status='interrupted', error=?, finished_at=? WHERE status IN ('queued','exporting')",
        ("Application restarted while this episode was exporting.", now()),
    )
