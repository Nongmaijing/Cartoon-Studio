from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from typing import Any

import httpx

from ..core.runtime import allow_cloud_generation, openai_settings
from ..services.assets import store_asset_from_path
from .base import ImageProvider, ProviderError, ProviderInfo


class OpenAIImageProvider(ImageProvider):
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        settings = openai_settings()
        self.model = str((config or {}).get("model") or "gpt-image-1")
        available = bool(settings.get("api_key")) and allow_cloud_generation()
        self.info = ProviderInfo(
            name="openai",
            type="image",
            capabilities=["generate_image", "generate_character_sheet", "generate_background"],
            available=available,
            input_constraints={"prompt": "text", "size": "provider-supported size"},
            output_constraints={"format": "png"},
            resource_estimate={"cloud": True, "cost": "provider billed"},
            config={"model": self.model, "allow_cloud": allow_cloud_generation()},
            notes=(
                "Optional OpenAI image provider. Disabled unless OPENAI_API_KEY is set and "
                "ALLOW_CLOUD_GENERATION=true. Private assets are not uploaded automatically."
            ),
        )

    async def generate_image(self, **kwargs: Any) -> dict[str, Any]:
        if not self.info.available:
            raise ProviderError(
                "OpenAI image generation is not enabled. Set OPENAI_API_KEY and ALLOW_CLOUD_GENERATION=true."
            )
        from openai import AsyncOpenAI

        settings = openai_settings()
        client = AsyncOpenAI(api_key=settings["api_key"], base_url=settings["base_url"])
        size = str(kwargs.get("size") or "")
        if not size:
            width = int(kwargs.get("width") or 1024)
            height = int(kwargs.get("height") or 1024)
            size = "1536x1024" if width > height else "1024x1536" if height > width else "1024x1024"
        response = await client.images.generate(
            model=self.model,
            prompt=str(kwargs["prompt"]),
            size=size,
            n=1,
        )
        item = response.data[0]
        if getattr(item, "b64_json", None):
            content = base64.b64decode(item.b64_json)
        elif getattr(item, "url", None):
            async with httpx.AsyncClient(timeout=120) as http:
                result = await http.get(item.url)
                result.raise_for_status()
                content = result.content
        else:
            raise ProviderError("OpenAI returned no image data.")
        with tempfile.TemporaryDirectory(prefix="cartoon_studio_openai_") as tmp:
            source = Path(tmp) / "openai.png"
            source.write_bytes(content)
            asset = store_asset_from_path(
                project_id=kwargs["project_id"],
                subdir="cloud",
                filename="openai_image.png",
                source_path=source,
                kind="image",
                mime="image/png",
                meta={"provider": "openai", "model": self.model, "prompt": kwargs["prompt"], "size": size},
            )
        return {"provider": "openai", "status": "completed", "asset": asset, "asset_id": asset["id"]}

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        return {"id": job_id, "status": "completed", "provider": "openai"}
