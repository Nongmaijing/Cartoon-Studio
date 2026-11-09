from __future__ import annotations

import json
from typing import Any

from ..db import execute, now, query_one
from ..schemas import EpisodeTimeline
from . import episode_export, episodes
from .asset_service import assets_for_episode
from .audit_service import log
from .errors import ConfirmationRequired, NotFoundError, ServiceError


def list_episodes(project_id: str | None = None) -> list[dict[str, Any]]:
    return episodes.list_episodes(project_id)


def get_episode(episode_id: str) -> dict[str, Any]:
    episode = episodes.get_episode(episode_id)
    if not episode:
        raise NotFoundError("Episode not found.")
    return episode


def create_episode(project_id: str, name: str, description: str = "", actor: str = "user") -> dict[str, Any]:
    if not query_one("SELECT id FROM projects WHERE id = ?", (project_id,)):
        raise NotFoundError("Project not found.")
    episode = episodes.create_episode(project_id, name, description)
    log(actor, "create_episode", "episode", episode["id"], {"name": name})
    return episode


def update_episode(
    episode_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    actor: str = "user",
) -> dict[str, Any]:
    get_episode(episode_id)
    episode = episodes.update_episode(episode_id, name=name, description=description)
    log(actor, "update_episode", "episode", episode_id, {"fields": [key for key, value in {"name": name, "description": description}.items() if value is not None]})
    return episode


def delete_episode(episode_id: str, actor: str = "user", confirm: bool = False) -> dict[str, Any]:
    get_episode(episode_id)
    if not confirm:
        raise ConfirmationRequired("Deleting an episode requires explicit confirmation (confirm=true).")
    episodes.delete_episode(episode_id)
    log(actor, "delete_episode", "episode", episode_id)
    return {"deleted": True, "episode_id": episode_id}


def save_timeline(episode_id: str, timeline: EpisodeTimeline, actor: str = "user") -> dict[str, Any]:
    get_episode(episode_id)
    episode = episodes.save_timeline(episode_id, timeline)
    log(actor, "save_timeline", "episode", episode_id)
    return episode


def render_episode(
    episode_id: str,
    timeline: EpisodeTimeline | dict[str, Any] | None = None,
    actor: str = "user",
    confirm: bool = False,
) -> dict[str, Any]:
    get_episode(episode_id)
    if not confirm:
        raise ConfirmationRequired("Rendering an episode requires explicit confirmation (confirm=true).")
    if timeline is not None:
        episodes.save_timeline(episode_id, EpisodeTimeline.model_validate(timeline))
    episode_export.start_export(episode_id)
    log(actor, "render_episode", "episode", episode_id)
    return get_episode(episode_id)


def cancel_render(episode_id: str, actor: str = "user") -> dict[str, Any]:
    get_episode(episode_id)
    status = episode_export.cancel_export(episode_id)
    log(actor, "cancel_render", "episode", episode_id, {"status": status})
    return {"episode_id": episode_id, "status": status}


def get_status(episode_id: str) -> dict[str, Any]:
    episode = get_episode(episode_id)
    return {
        "episode_id": episode_id,
        "status": episode.get("status"),
        "progress": episode.get("progress"),
        "duration_ms": episode.get("duration_ms"),
        "output_url": episode.get("output_url"),
        "subtitle_url": episode.get("subtitle_url"),
        "error": episode.get("error"),
        "production_state": episode.get("production_state"),
        "production": episode.get("production"),
        "log": episode.get("log"),
    }


def get_preview(episode_id: str) -> dict[str, Any]:
    episode = get_episode(episode_id)
    return {
        "episode_id": episode_id,
        "status": episode.get("status"),
        "output_url": episode.get("output_url"),
        "subtitle_url": episode.get("subtitle_url"),
        "duration_ms": episode.get("duration_ms"),
    }


def get_assets(episode_id: str) -> dict[str, Any]:
    get_episode(episode_id)
    return assets_for_episode(episode_id)


def set_production_state(episode_id: str, state: str, production: dict[str, Any] | None = None) -> None:
    get_episode(episode_id)
    if production is None:
        execute(
            "UPDATE episodes SET production_state = ?, updated_at = ? WHERE id = ?",
            (state, now(), episode_id),
        )
    else:
        execute(
            "UPDATE episodes SET production_state = ?, production_json = ?, updated_at = ? WHERE id = ?",
            (state, json.dumps(production), now(), episode_id),
        )
