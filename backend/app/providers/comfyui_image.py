from __future__ import annotations

from typing import Any

from ..config import load_config
from ..services.generation import submit_image
from ..services.jobs import get_job, runner
from .base import ImageProvider, ProviderInfo


class ComfyUIImageProvider(ImageProvider):
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or load_config()
        self.info = ProviderInfo(
            name="comfyui",
            type="image",
            capabilities=[
                "generate_image",
                "generate_character_sheet",
                "generate_expression_sheet",
                "generate_pose_sheet",
                "generate_background",
                "upscale",
            ],
            available=bool(config.get("comfyui", {}).get("server_url")),
            input_constraints={"workflow": "api-format", "input_image": "uploaded project image"},
            output_constraints={"format": "png", "location": "project outputs"},
            resource_estimate={"gpu": "local ComfyUI", "vram_gb": 6},
            config={"workflow_default": config.get("generation", {}).get("default_workflow")},
            notes="Existing ComfyUI workflow queue. Live GPU/connection status is reported separately.",
        )

    async def generate_image(self, **kwargs: Any) -> dict[str, Any]:
        job = await submit_image(
            project_id=kwargs["project_id"],
            prompt=kwargs.get("prompt") or "cartoon image",
            attach=kwargs.get("attach") or {},
            negative_prompt=kwargs.get("negative_prompt"),
            width=kwargs.get("width"),
            height=kwargs.get("height"),
            steps=kwargs.get("steps"),
            cfg=kwargs.get("cfg"),
            seed=kwargs.get("seed"),
            workflow_id=kwargs.get("workflow_id"),
            scene_id=kwargs.get("scene_id"),
            input_image=kwargs.get("input_image"),
            denoise=kwargs.get("denoise"),
            control_strength=kwargs.get("control_strength"),
            control_net_name=kwargs.get("control_net_name"),
            architecture=kwargs.get("architecture"),
            purpose=kwargs.get("purpose") or "scene",
            preset=kwargs.get("preset"),
            checkpoint=kwargs.get("checkpoint"),
            vae=kwargs.get("vae"),
            lora_name=kwargs.get("lora_name"),
            lora_strength=kwargs.get("lora_strength"),
        )
        return {"provider": "comfyui", "job": job, "job_id": job.get("id")}

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        return get_job(job_id) or {"id": job_id, "status": "not_found"}

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        status = await runner.cancel(job_id)
        return {"job_id": job_id, "status": status}
