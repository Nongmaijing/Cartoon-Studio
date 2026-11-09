from __future__ import annotations

import shutil
from typing import Any

from ..config import load_config
from ..schemas import EpisodeTimeline
from ..services import episode_export, episodes
from .base import EditingProvider, ProviderInfo


class FFmpegEditingProvider(EditingProvider):
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or load_config()
        ffmpeg = str((config.get("ffmpeg") or {}).get("path") or "").strip()
        available = bool(ffmpeg) or bool(shutil.which("ffmpeg"))
        self.info = ProviderInfo(
            name="ffmpeg",
            type="editing",
            capabilities=["assemble_video", "synchronize_audio", "add_transitions", "render_episode", "generate_preview"],
            available=available,
            input_constraints={"timeline": "episode timeline JSON"},
            output_constraints={"format": "mp4", "resolution": "configurable"},
            resource_estimate={"cpu": "serialized", "gpu": "not required"},
            config={"ffmpeg_path": ffmpeg or shutil.which("ffmpeg") or ""},
            notes="Existing FFmpeg episode exporter with audio mixing and soft subtitles.",
        )

    async def assemble_video(self, **kwargs: Any) -> dict[str, Any]:
        episode_id = kwargs["episode_id"]
        timeline = kwargs.get("timeline")
        if timeline is not None:
            episodes.save_timeline(episode_id, EpisodeTimeline.model_validate(timeline))
        episode_export.start_export(episode_id)
        return {"provider": "ffmpeg", "episode_id": episode_id, "status": "queued"}

    async def render_episode(self, **kwargs: Any) -> dict[str, Any]:
        return await self.assemble_video(**kwargs)

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        return episodes.get_episode(job_id) or {"id": job_id, "status": "not_found"}

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        return {"episode_id": job_id, "status": episode_export.cancel_export(job_id)}
