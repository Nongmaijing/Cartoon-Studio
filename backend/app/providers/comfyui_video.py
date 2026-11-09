from __future__ import annotations

from typing import Any

from ..config import load_config
from ..services.generation import submit_video
from ..services.jobs import get_job, runner
from .base import ProviderInfo, VideoProvider


class ComfyUIVideoProvider(VideoProvider):
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or load_config()
        self.info = ProviderInfo(
            name="comfyui",
            type="video",
            capabilities=["generate_video", "animate_image"],
            available=bool(config.get("comfyui", {}).get("server_url")),
            input_constraints={"start_image": "project image", "workflow": "api-format"},
            output_constraints={"format": "mp4", "location": "project outputs"},
            resource_estimate={"gpu": "local ComfyUI", "vram_gb": 6, "notes": "Wan video is slow on 6 GB VRAM."},
            config={"workflows": ["wan22_t2v", "wan22_i2v"]},
            notes="Existing Wan 2.2 queue; AnimateDiff is reported separately when installed.",
        )

    async def generate_video(self, **kwargs: Any) -> dict[str, Any]:
        job = await submit_video(
            project_id=kwargs["project_id"],
            prompt=kwargs.get("prompt") or "cartoon animation",
            attach=kwargs.get("attach") or {},
            scene_id=kwargs.get("scene_id"),
            negative_prompt=kwargs.get("negative_prompt"),
            width=kwargs.get("width"),
            height=kwargs.get("height"),
            steps=kwargs.get("steps"),
            cfg=kwargs.get("cfg"),
            seed=kwargs.get("seed"),
            length=kwargs.get("length"),
            fps=kwargs.get("fps"),
            sampler=kwargs.get("sampler"),
            scheduler=kwargs.get("scheduler"),
            input_image=kwargs.get("input_image"),
            workflow_id=kwargs.get("workflow_id"),
        )
        return {"provider": "comfyui", "job": job, "job_id": job.get("id")}

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        return get_job(job_id) or {"id": job_id, "status": "not_found"}

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        status = await runner.cancel(job_id)
        return {"job_id": job_id, "status": status}
