from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    archived: bool | None = None


class GenerateRequest(BaseModel):
    project_id: str
    workflow_id: str
    prompt: str = Field(min_length=1)
    negative_prompt: str | None = None
    width: int | None = Field(default=None, ge=64, le=2048)
    height: int | None = Field(default=None, ge=64, le=2048)
    steps: int | None = Field(default=None, ge=1, le=100)
    cfg: float | None = Field(default=None, ge=0.0, le=30.0)
    seed: int | None = None
    sampler: str | None = None
    scheduler: str | None = None
    batch_size: int | None = Field(default=None, ge=1, le=4)
    length: int | None = Field(default=None, ge=1, le=501)
    fps: float | None = Field(default=None, ge=1, le=60)
    input_image: str | None = None
    output_format: str | None = None
    scene_id: str | None = None


class WorkflowImport(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    api: dict[str, Any]
    mapping: dict[str, Any] | None = None


class CharacterCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    style: str = ""
    clothing: str = ""
    appearance: str = ""
    voice_engine: str = ""
    voice_name: str = ""
    voice_rate: int = Field(default=0, ge=-10, le=10)
    voice_pitch: int = Field(default=0, ge=-50, le=50)
    voice_volume: int = Field(default=100, ge=0, le=100)


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    style: str | None = None
    clothing: str | None = None
    appearance: str | None = None
    voice_engine: str | None = None
    voice_name: str | None = None
    voice_rate: int | None = Field(default=None, ge=-10, le=10)
    voice_pitch: int | None = Field(default=None, ge=-50, le=50)
    voice_volume: int | None = Field(default=None, ge=0, le=100)


class VoiceAssignment(BaseModel):
    engine: str = ""
    voice: str = ""
    rate: int = Field(default=0, ge=-10, le=10)
    pitch: int = Field(default=0, ge=-50, le=50)
    volume: int = Field(default=100, ge=0, le=100)


class VoicePreviewRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    engine: str = ""
    voice: str = ""
    rate: int = Field(default=0, ge=-10, le=10)
    pitch: int = Field(default=0, ge=-50, le=50)
    volume: int = Field(default=100, ge=0, le=100)
    emotion: str = Field(default="neutral", max_length=32)


class DialogueLineCreate(BaseModel):
    character_id: str | None = None
    text: str = Field(min_length=1, max_length=2000)
    emotion: str = Field(default="neutral", max_length=32)
    voice_engine: str | None = None
    voice_name: str | None = None
    rate: int | None = Field(default=None, ge=-10, le=10)
    pitch: int | None = Field(default=None, ge=-50, le=50)
    volume: int | None = Field(default=None, ge=0, le=100)
    start_ms: int = Field(default=0, ge=0)


class DialogueLineUpdate(BaseModel):
    character_id: str | None = None
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    emotion: str | None = Field(default=None, max_length=32)
    voice_engine: str | None = None
    voice_name: str | None = None
    rate: int | None = Field(default=None, ge=-10, le=10)
    pitch: int | None = Field(default=None, ge=-50, le=50)
    volume: int | None = Field(default=None, ge=0, le=100)
    start_ms: int | None = Field(default=None, ge=0)
    order_index: int | None = Field(default=None, ge=0)


class DialogueImportRequest(BaseModel):
    replace: bool = False


class CharacterGenerateRequest(BaseModel):
    kind: Literal["reference", "expression", "pose"] = "reference"
    label: str = Field(default="", max_length=80)
    prompt: str | None = None
    negative_prompt: str | None = None
    width: int | None = Field(default=512, ge=64, le=2048)
    height: int | None = Field(default=768, ge=64, le=2048)
    steps: int | None = Field(default=24, ge=1, le=100)
    cfg: float | None = Field(default=7.0, ge=0.0, le=30.0)
    seed: int | None = None
    workflow_id: str | None = None
    reference_asset_id: str | None = None
    reference_mode: Literal["identity", "pose"] = "identity"
    denoise: float = Field(default=0.55, ge=0.0, le=1.0)
    control_strength: float = Field(default=0.8, ge=0.0, le=2.0)


class CanonicalAsset(BaseModel):
    asset_id: str


class BackgroundCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    aspect_ratio: str = "16:9"
    width: int = Field(default=1024, ge=64, le=2048)
    height: int = Field(default=576, ge=64, le=2048)


class BackgroundUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    aspect_ratio: str | None = None
    width: int | None = Field(default=None, ge=64, le=2048)
    height: int | None = Field(default=None, ge=64, le=2048)


class BackgroundGenerateRequest(BaseModel):
    prompt: str | None = None
    negative_prompt: str | None = None
    width: int | None = Field(default=None, ge=64, le=2048)
    height: int | None = Field(default=None, ge=64, le=2048)
    steps: int | None = Field(default=24, ge=1, le=100)
    cfg: float | None = Field(default=7.0, ge=0.0, le=30.0)
    seed: int | None = None
    workflow_id: str | None = None


class MediaAttach(BaseModel):
    asset_id: str
    role: Literal["reference", "expression", "pose", "background", "other"] = "other"
    label: str = Field(default="", max_length=80)


class AssetUpscaleRequest(BaseModel):
    workflow_id: str = "upscale_4x"
    owner_type: Literal["character", "scene", "background"] | None = None
    owner_id: str | None = None
    role: str | None = Field(default=None, max_length=40)
    label: str = Field(default="upscaled", max_length=80)


class SceneCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    dialogue: str = ""
    action: str = ""
    camera: str = ""
    duration: float = Field(default=5.0, ge=0.5, le=120.0)
    background_id: str | None = None
    character_ids: list[str] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)


class SceneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    dialogue: str | None = None
    action: str | None = None
    camera: str | None = None
    duration: float | None = Field(default=None, ge=0.5, le=120.0)
    background_id: str | None = None
    character_ids: list[str] | None = None
    settings: dict[str, Any] | None = None


class SceneCastAdd(BaseModel):
    character_id: str
    role: str = Field(default="main", max_length=40)


class SceneMediaAttach(BaseModel):
    asset_id: str
    role: Literal["keyframe", "video", "other"] = "other"
    label: str = Field(default="", max_length=80)


class SceneGenerateRequest(BaseModel):
    kind: Literal["keyframe", "video"] = "keyframe"
    workflow_id: str | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    width: int | None = Field(default=None, ge=32, le=2048)
    height: int | None = Field(default=None, ge=32, le=2048)
    steps: int | None = Field(default=None, ge=1, le=100)
    cfg: float | None = Field(default=None, ge=0.0, le=30.0)
    seed: int | None = None
    length: int | None = Field(default=None, ge=1, le=501)
    fps: float | None = Field(default=None, ge=1, le=60)
    start_image: str | None = None
    reference_asset_id: str | None = None
    reference_mode: Literal["identity", "pose"] = "identity"
    denoise: float = Field(default=0.55, ge=0.0, le=1.0)
    control_strength: float = Field(default=0.8, ge=0.0, le=2.0)


class AnimationGenerateRequest(BaseModel):
    project_id: str
    workflow_id: str | None = None
    prompt: str = Field(min_length=1)
    negative_prompt: str | None = None
    width: int = Field(default=832, ge=32, le=2048)
    height: int = Field(default=480, ge=32, le=2048)
    steps: int = Field(default=20, ge=1, le=100)
    cfg: float = Field(default=5.0, ge=0.0, le=30.0)
    seed: int = -1
    length: int = Field(default=121, ge=1, le=501)
    fps: float = Field(default=24.0, ge=1, le=60)
    sampler: str = "uni_pc"
    scheduler: str = "simple"
    start_image: str | None = None
    scene_id: str | None = None


class EpisodeCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=120)
    description: str = ""


class EpisodeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None


class EpisodeSegment(BaseModel):
    id: str | None = None
    scene_id: str
    asset_id: str
    kind: Literal["video", "image"] = "video"
    duration_ms: int = Field(default=3000, ge=100, le=600000)
    trim_start_ms: int = Field(default=0, ge=0, le=600000)
    transition: Literal["cut", "fade"] = "cut"
    motion: Literal["none", "zoom_in", "zoom_out", "pan_left", "pan_right"] = "none"
    label: str = ""
    muted: bool = False


class EpisodeAudio(BaseModel):
    id: str | None = None
    asset_id: str
    start_ms: int = Field(default=0, ge=0, le=3600000)
    volume: float = Field(default=1.0, ge=0.0, le=2.0)
    loop: bool = False
    label: str = ""
    kind: Literal["dialogue", "music", "sfx", "other"] = "other"


class EpisodeSettings(BaseModel):
    width: int = Field(default=1280, ge=64, le=1920)
    height: int = Field(default=720, ge=64, le=1080)
    fps: float = Field(default=24.0, ge=1, le=60)
    subtitles: Literal["soft", "none"] = "soft"
    background_music_asset_id: str | None = None
    background_music_volume: float = Field(default=0.35, ge=0.0, le=2.0)
    fade_duration_ms: int = Field(default=350, ge=0, le=2000)


class EpisodeTimeline(BaseModel):
    segments: list[EpisodeSegment] = Field(default_factory=list)
    audio: list[EpisodeAudio] = Field(default_factory=list)
    settings: EpisodeSettings = Field(default_factory=EpisodeSettings)


class EpisodeExportRequest(BaseModel):
    timeline: EpisodeTimeline | None = None


class SettingsUpdate(BaseModel):
    comfyui: dict[str, Any] | None = None
    paths: dict[str, Any] | None = None
    generation: dict[str, Any] | None = None
    ffmpeg: dict[str, Any] | None = None
    tts: dict[str, Any] | None = None
    server: dict[str, Any] | None = None
    ui: dict[str, Any] | None = None


class CancelResponse(BaseModel):
    job_id: str
    status: Literal["cancelled", "cancelling", "not_running"]
