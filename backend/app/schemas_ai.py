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


class ApprovalRequest(BaseModel):
    notes: str = ""
