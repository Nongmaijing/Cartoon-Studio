from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..config import load_config
from ..schemas import VoicePreviewRequest
from ..services import tts

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.get("/engines")
async def engines(refresh: bool = False) -> dict:
    return await tts.detect_engines(load_config(), refresh=refresh)


@router.post("/preview")
async def preview(payload: VoicePreviewRequest) -> Response:
    with tempfile.TemporaryDirectory(prefix="cartoon_studio_preview_") as tmp:
        out_path = Path(tmp) / "preview.wav"
        try:
            await tts.synthesize(
                text=payload.text,
                out_path=out_path,
                engine=payload.engine or None,
                voice=payload.voice or None,
                rate=payload.rate,
                pitch=payload.pitch,
                volume=payload.volume,
                emotion=payload.emotion,
                config=load_config(),
            )
        except tts.TTSError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        content = out_path.read_bytes()
    return Response(
        content=content,
        media_type="audio/wav",
        headers={
            "Content-Disposition": 'inline; filename="voice-preview.wav"',
            "Cache-Control": "no-store",
        },
    )
