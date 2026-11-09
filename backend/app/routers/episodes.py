from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from ..db import query_one
from ..schemas import EpisodeCreate, EpisodeExportRequest, EpisodeTimeline, EpisodeUpdate
from ..services import episode_export, episodes

router = APIRouter(prefix="/api/episodes", tags=["episodes"])


def _require_episode(episode_id: str) -> dict:
    episode = episodes.get_episode(episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found.")
    return episode


def _require_project(project_id: str) -> None:
    if not query_one("SELECT id FROM projects WHERE id = ?", (project_id,)):
        raise HTTPException(status_code=404, detail="Project not found.")


@router.get("")
async def list_episodes(project_id: str | None = None) -> list[dict]:
    return episodes.list_episodes(project_id)


@router.post("", status_code=201)
async def create_episode(payload: EpisodeCreate) -> dict:
    _require_project(payload.project_id)
    return episodes.create_episode(payload.project_id, payload.name, payload.description)


@router.get("/{episode_id}")
async def get_episode(episode_id: str) -> dict:
    return _require_episode(episode_id)


@router.patch("/{episode_id}")
async def update_episode(episode_id: str, payload: EpisodeUpdate) -> dict:
    _require_episode(episode_id)
    return episodes.update_episode(
        episode_id,
        name=payload.name,
        description=payload.description,
    )


@router.delete("/{episode_id}")
async def delete_episode(episode_id: str) -> dict:
    _require_episode(episode_id)
    episodes.delete_episode(episode_id)
    return {"deleted": True, "episode_id": episode_id}


@router.put("/{episode_id}/timeline")
async def save_timeline(episode_id: str, payload: EpisodeTimeline) -> dict:
    _require_episode(episode_id)
    try:
        return episodes.save_timeline(episode_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{episode_id}/export")
async def export_episode(episode_id: str, payload: EpisodeExportRequest | None = None) -> dict:
    _require_episode(episode_id)
    try:
        if payload and payload.timeline is not None:
            episodes.save_timeline(episode_id, payload.timeline)
        episode_export.start_export(episode_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _require_episode(episode_id)


@router.get("/{episode_id}/export")
async def export_status(episode_id: str) -> dict:
    return _require_episode(episode_id)


@router.post("/{episode_id}/cancel")
async def cancel_export(episode_id: str) -> dict:
    _require_episode(episode_id)
    status = episode_export.cancel_export(episode_id)
    if status == "not_found":
        raise HTTPException(status_code=404, detail="Episode not found.")
    return {"episode_id": episode_id, "status": status}


@router.get("/{episode_id}/file")
async def episode_file(episode_id: str) -> FileResponse:
    episode = _require_episode(episode_id)
    path = episodes.output_path(episode)
    if not path:
        raise HTTPException(status_code=404, detail="No exported file is available yet.")
    return FileResponse(path, media_type="video/mp4", filename=path.name)


@router.get("/{episode_id}/subtitles")
async def episode_subtitles(episode_id: str) -> PlainTextResponse:
    episode = _require_episode(episode_id)
    path = episodes.subtitle_path(episode)
    if not path:
        raise HTTPException(status_code=404, detail="No subtitle file is available yet.")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="application/x-subrip")
