from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..db import query_one
from ..schemas import DialogueImportRequest, DialogueLineCreate, DialogueLineUpdate
from ..services import dialogue, tts

router = APIRouter(prefix="/api", tags=["dialogue"])


def _require_scene(scene_id: str) -> dict[str, Any]:
    row = query_one("SELECT * FROM scenes WHERE id = ?", (scene_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Scene not found.")
    return row


def _require_line(line_id: str) -> dict[str, Any]:
    line = dialogue.get_line(line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Dialogue line not found.")
    return line


@router.get("/scenes/{scene_id}/dialogue")
async def scene_dialogue(scene_id: str) -> list[dict[str, Any]]:
    _require_scene(scene_id)
    return dialogue.list_lines(scene_id)


@router.post("/scenes/{scene_id}/dialogue", status_code=201)
async def create_dialogue_line(scene_id: str, payload: DialogueLineCreate) -> dict[str, Any]:
    _require_scene(scene_id)
    try:
        return await dialogue.create_line(
            scene_id,
            character_id=payload.character_id,
            text=payload.text,
            emotion=payload.emotion,
            voice_engine=payload.voice_engine,
            voice_name=payload.voice_name,
            rate=payload.rate,
            pitch=payload.pitch,
            volume=payload.volume,
            start_ms=payload.start_ms,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except tts.TTSError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scenes/{scene_id}/dialogue/import", status_code=201)
async def import_dialogue(scene_id: str, payload: DialogueImportRequest) -> list[dict[str, Any]]:
    _require_scene(scene_id)
    try:
        return await dialogue.import_scene_dialogue(scene_id, replace=payload.replace)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except tts.TTSError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scenes/{scene_id}/dialogue/generate")
async def generate_scene_dialogue(scene_id: str) -> dict[str, Any]:
    _require_scene(scene_id)
    return await dialogue.generate_scene(scene_id)


@router.patch("/dialogue/{line_id}")
async def update_dialogue_line(line_id: str, payload: DialogueLineUpdate) -> dict[str, Any]:
    _require_line(line_id)
    try:
        return dialogue.update_line(line_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/dialogue/{line_id}")
async def delete_dialogue_line(line_id: str) -> dict[str, Any]:
    _require_line(line_id)
    try:
        dialogue.delete_line(line_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"deleted": True, "line_id": line_id}


@router.post("/dialogue/{line_id}/generate")
async def generate_dialogue_line(line_id: str) -> dict[str, Any]:
    _require_line(line_id)
    try:
        return await dialogue.generate_line(line_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except tts.TTSError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
