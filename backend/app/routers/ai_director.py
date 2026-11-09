from __future__ import annotations

import json
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..ai import conversation_manager
from ..ai.openai_director import director
from ..ai.tool_registry import ToolContext, tool_registry
from ..config import load_config
from ..core.runtime import integration_status, openai_settings
from ..core.security import rate_limiter
from ..schemas_ai import AIConversationCreate, AIMessageCreate
from ..services.errors import ServiceError

router = APIRouter(prefix="/api/v1/ai", tags=["ai-director"])


def _raise(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/health")
async def ai_health() -> dict[str, Any]:
    return {"status": "ok", "openai": integration_status()["openai"], "model": openai_settings()["model"] or None}


@router.get("/tools")
async def tools() -> dict[str, Any]:
    return {
        "count": len(tool_registry.list_tools()),
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "scope": tool.scope,
                "confirmation_required": tool.confirmation_required,
            }
            for tool in tool_registry.list_tools()
        ],
    }


@router.get("/conversations")
async def list_conversations(project_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    return conversation_manager.list_conversations(project_id, min(limit, 100))


@router.post("/conversations", status_code=201)
async def create_conversation(payload: AIConversationCreate) -> dict[str, Any]:
    return conversation_manager.create_conversation(
        payload.project_id,
        payload.episode_id,
        payload.title,
        payload.model or openai_settings()["model"],
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str) -> dict[str, Any]:
    try:
        return conversation_manager.get_conversation(conversation_id)
    except ServiceError as exc:
        _raise(exc)


@router.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id: str, payload: AIMessageCreate) -> dict[str, Any]:
    limit = int((load_config().get("security") or {}).get("rate_limit_per_minute", 60))
    try:
        await rate_limiter.check(f"ai:{conversation_id}", limit)
        return await director.run_turn(
            conversation_id,
            payload.message,
            project_id=payload.project_id,
            episode_id=payload.episode_id,
            actor="ai_director",
        )
    except ServiceError as exc:
        _raise(exc)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/conversations/{conversation_id}/messages/stream")
async def stream_message(conversation_id: str, payload: AIMessageCreate) -> StreamingResponse:
    async def generate() -> AsyncGenerator[str, None]:
        async for event in director.stream_turn(
            conversation_id,
            payload.message,
            project_id=payload.project_id,
            episode_id=payload.episode_id,
            actor="ai_director",
        ):
            yield _sse(event["event"], event["data"])

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/tool-executions")
async def tool_executions(conversation_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    return conversation_manager.list_tool_executions(conversation_id, min(limit, 200))


@router.post("/tools/{tool_name}")
async def execute_tool(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Local/manual tool execution for UI debugging and integration tests."""
    context = ToolContext(
        actor=str(payload.pop("actor", "user")),
        conversation_id=payload.pop("conversation_id", None),
        project_id=payload.pop("project_id", None),
        episode_id=payload.pop("episode_id", None),
    )
    idempotency_key = payload.pop("idempotency_key", None)
    result = await tool_registry.execute(tool_name, payload, context, idempotency_key=idempotency_key)
    return result
