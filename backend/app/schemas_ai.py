from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AIConversationCreate(BaseModel):
    project_id: str | None = None
    episode_id: str | None = None
    title: str = Field(default="", max_length=200)
    model: str = ""


class AIMessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    project_id: str | None = None
    episode_id: str | None = None
    provider: str | None = None
    model: str | None = None


class ProductionStartRequest(BaseModel):
    project_id: str
    episode_id: str
    plan: dict[str, Any] | None = None
    confirm: bool = False
    idempotency_key: str | None = None


class ProductionRegenerateRequest(BaseModel):
    confirm: bool = False


class MCPTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: str = "production"


class MCPToolExecuteRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
    project_id: str | None = None
    episode_id: str | None = None
    actor: str = "mcp"
    idempotency_key: str | None = None


class ProviderConfigUpdate(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool | None = None


class ModelConfigUpdate(BaseModel):
    models: dict[str, Any] = Field(default_factory=dict)


class FastModeUpdate(BaseModel):
    enabled: bool | None = None
    steps: int | None = Field(default=None, ge=4, le=8)
    strength: float | None = Field(default=None, ge=0.1, le=2.0)


class ArtStyleUpdate(BaseModel):
    art_style: str = Field(min_length=1, max_length=64)
    custom_style: str | None = Field(default=None, max_length=300)


class CutoutRequest(BaseModel):
    project_id: str
    asset_id: str
    engine: str = Field(default="auto", max_length=16)
    tolerance: int = Field(default=26, ge=0, le=120)
    feather: int = Field(default=10, ge=0, le=60)
    padding: int = Field(default=8, ge=0, le=200)


class CameraClipRequest(BaseModel):
    project_id: str
    asset_id: str
    duration: float = Field(default=8.0, ge=1, le=60)
    fps: int = Field(default=24, ge=12, le=30)
    width: int = Field(default=1280, ge=64, le=2048)
    height: int = Field(default=720, ge=64, le=2048)
    camera: str = Field(default="push_in", max_length=32)
    motion_strength: float = Field(default=1.0, ge=0, le=3)


class ParallaxRequest(BaseModel):
    project_id: str
    background_asset_id: str
    foreground_asset_id: str
    duration: float = Field(default=6.0, ge=1, le=30)
    fps: int = Field(default=24, ge=12, le=30)
    width: int = Field(default=1280, ge=64, le=2048)
    height: int = Field(default=720, ge=64, le=2048)
    camera: str = Field(default="push_in", max_length=32)
    subject_height: float = Field(default=0.62, ge=0.1, le=1.2)
    subject_x: float = Field(default=0.5, ge=-0.2, le=1.2)
    subject_y: float = Field(default=0.94, ge=0.2, le=1.2)
    motion_strength: float = Field(default=1.0, ge=0, le=3)
    bob_period: float = Field(default=2.6, ge=0.5, le=10)
    shadow: bool = True
    scene_id: str | None = None


class TunnelStartRequest(BaseModel):
    confirm: bool = False
    ttl_minutes: int = Field(default=30, description="Minutes until auto-secure; 0 means never auto-stop")


class ApprovalRequest(BaseModel):
    notes: str = ""
