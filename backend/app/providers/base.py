from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderInfo:
    name: str
    type: str
    capabilities: list[str]
    available: bool
    input_constraints: dict[str, Any] = field(default_factory=dict)
    output_constraints: dict[str, Any] = field(default_factory=dict)
    resource_estimate: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaseProvider:
    info: ProviderInfo

    async def status(self) -> dict[str, Any]:
        return self.info.as_dict()


class ImageProvider(BaseProvider):
    async def generate_image(self, **kwargs: Any) -> dict[str, Any]:
        raise ProviderError(f"{self.info.name} does not implement image generation.")

    async def generate_character_sheet(self, **kwargs: Any) -> dict[str, Any]:
        return await self.generate_image(**kwargs)

    async def generate_expression_sheet(self, **kwargs: Any) -> dict[str, Any]:
        return await self.generate_image(**kwargs)

    async def generate_pose_sheet(self, **kwargs: Any) -> dict[str, Any]:
        return await self.generate_image(**kwargs)

    async def generate_background(self, **kwargs: Any) -> dict[str, Any]:
        return await self.generate_image(**kwargs)

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        raise ProviderError(f"{self.info.name} does not expose job status.")

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        raise ProviderError(f"{self.info.name} does not support cancellation.")


class VideoProvider(BaseProvider):
    async def generate_video(self, **kwargs: Any) -> dict[str, Any]:
        raise ProviderError(f"{self.info.name} does not implement video generation.")

    async def animate_image(self, **kwargs: Any) -> dict[str, Any]:
        return await self.generate_video(**kwargs)

    async def extend_video(self, **kwargs: Any) -> dict[str, Any]:
        raise ProviderError(f"{self.info.name} does not implement video extension.")

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        raise ProviderError(f"{self.info.name} does not expose job status.")

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        raise ProviderError(f"{self.info.name} does not support cancellation.")


class AudioProvider(BaseProvider):
    async def generate_speech(self, **kwargs: Any) -> dict[str, Any]:
        raise ProviderError(f"{self.info.name} does not implement speech generation.")

    async def generate_voice(self, **kwargs: Any) -> dict[str, Any]:
        return await self.generate_speech(**kwargs)

    async def generate_sound_effect(self, **kwargs: Any) -> dict[str, Any]:
        raise ProviderError(f"{self.info.name} does not implement sound effects.")

    async def generate_music(self, **kwargs: Any) -> dict[str, Any]:
        raise ProviderError(f"{self.info.name} does not implement music generation.")

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        raise ProviderError(f"{self.info.name} does not expose job status.")


class EditingProvider(BaseProvider):
    async def assemble_video(self, **kwargs: Any) -> dict[str, Any]:
        raise ProviderError(f"{self.info.name} does not implement video assembly.")

    async def synchronize_audio(self, **kwargs: Any) -> dict[str, Any]:
        raise ProviderError(f"{self.info.name} does not implement audio synchronization.")

    async def add_transitions(self, **kwargs: Any) -> dict[str, Any]:
        raise ProviderError(f"{self.info.name} does not implement transitions.")

    async def render_episode(self, **kwargs: Any) -> dict[str, Any]:
        return await self.assemble_video(**kwargs)

    async def generate_preview(self, **kwargs: Any) -> dict[str, Any]:
        return await self.render_episode(**kwargs)

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        raise ProviderError(f"{self.info.name} does not expose job status.")

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        raise ProviderError(f"{self.info.name} does not support cancellation.")
