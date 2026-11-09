from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from ..config import load_config
from ..services import audio_synth, tts
from .base import AudioProvider, ProviderInfo


class KokoroAudioProvider(AudioProvider):
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or load_config()
        tts_config = config.get("tts") or {}
        model = Path(str(tts_config.get("kokoro_model") or ""))
        voices = Path(str(tts_config.get("kokoro_voices") or ""))
        self.info = ProviderInfo(
            name="kokoro",
            type="audio",
            capabilities=["generate_speech", "generate_voice", "generate_sound_effect", "generate_music"],
            available=model.exists() and voices.exists(),
            input_constraints={"text": "utf-8", "engine": "kokoro/sapi/piper"},
            output_constraints={"format": "wav", "sample_rate": 24000},
            resource_estimate={"cpu": "single-threaded/serialized", "gpu": "not required"},
            config={"default_engine": tts_config.get("default_engine", "kokoro")},
            notes="Kokoro neural TTS, with Windows SAPI fallback. Music/SFX are original local synthesis.",
        )

    async def generate_speech(self, **kwargs: Any) -> dict[str, Any]:
        out_path = Path(kwargs["out_path"])
        settings = await tts.synthesize(
            text=kwargs["text"],
            out_path=out_path,
            engine=kwargs.get("engine"),
            voice=kwargs.get("voice"),
            rate=int(kwargs.get("rate", 0)),
            pitch=int(kwargs.get("pitch", 0)),
            volume=int(kwargs.get("volume", 100)),
            emotion=str(kwargs.get("emotion", "neutral")),
            config=kwargs.get("config"),
        )
        return {"provider": "kokoro", "status": "completed", "path": str(out_path), **settings}

    async def generate_sound_effect(self, **kwargs: Any) -> dict[str, Any]:
        out_path = Path(kwargs["out_path"])
        result = await asyncio.to_thread(
            audio_synth.synthesize_sound_effect,
            out_path,
            str(kwargs.get("kind", "sparkle")),
        )
        return {"provider": "kokoro", "status": "completed", "path": str(out_path), **result}

    async def generate_music(self, **kwargs: Any) -> dict[str, Any]:
        out_path = Path(kwargs["out_path"])
        result = await asyncio.to_thread(
            audio_synth.synthesize_music,
            out_path,
            float(kwargs.get("duration", 30.0)),
        )
        return {"provider": "kokoro", "status": "completed", "path": str(out_path), **result}

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        return {"id": job_id, "status": "completed", "provider": "kokoro"}
