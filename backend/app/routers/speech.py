from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..schemas import TranscribeRequest
from ..services import speech_service

router = APIRouter(prefix="/api/v1/speech", tags=["speech"])


@router.get("/status")
async def status() -> dict[str, Any]:
    return speech_service.availability()


@router.post("/transcribe")
async def transcribe(payload: TranscribeRequest) -> dict[str, Any]:
    try:
        return await speech_service.transcribe_asset(
            payload.asset_id,
            language=payload.language,
            vad=payload.vad,
            include_srt=payload.include_srt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
