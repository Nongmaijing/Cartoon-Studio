from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..ai.tool_registry import ToolContext, tool_registry
from ..core.runtime import integration_status, mcp_settings
from ..core.security import create_mcp_token
from ..db import execute, now, query
from ..schemas_ai import MCPTokenCreate, MCPToolExecuteRequest, TunnelStartRequest
from ..services import mcp_tunnel_service
from ..services.errors import ServiceError

router = APIRouter(prefix="/api/v1/mcp", tags=["mcp-support"])


def _raise(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/status")
async def status() -> dict[str, Any]:
    settings = mcp_settings()
    return {
        "enabled": settings["enabled"],
        "transport": settings["transport"],
        "host": settings["host"],
        "port": settings["port"],
        "public_url": settings["public_url"] or None,
        "auth_mode": settings["auth_mode"],
        "bearer_token_configured": bool(settings["bearer_token"]),
        "integration": integration_status()["mcp"],
        "tools": len(tool_registry.list_tools()),
    }


@router.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "tools": len(tool_registry.list_tools())}


@router.get("/tools")
async def tools() -> dict[str, Any]:
    return {"tools": tool_registry.mcp_tools()}


@router.post("/tokens", status_code=201)
async def create_token(payload: MCPTokenCreate) -> dict[str, Any]:
    """Create an MCP bearer token. The raw token is returned only once."""
    result = create_mcp_token(payload.name, payload.scopes)
    return {
        "id": result["id"],
        "name": result["name"],
        "token": result["token"],
        "scopes": result["scopes"],
        "warning": "Store this token securely. It will not be shown again.",
    }


@router.get("/tokens")
async def list_tokens() -> list[dict[str, Any]]:
    return query(
        "SELECT id, name, scopes, created_at, last_used_at, revoked FROM mcp_tokens ORDER BY created_at DESC"
    )


@router.post("/tokens/{token_id}/revoke")
async def revoke_token(token_id: str) -> dict[str, Any]:
    execute("UPDATE mcp_tokens SET revoked = 1 WHERE id = ?", (token_id,))
    return {"id": token_id, "revoked": True}


@router.post("/tools/{tool_name}")
async def execute_tool(tool_name: str, payload: MCPToolExecuteRequest) -> dict[str, Any]:
    context = ToolContext(
        actor=payload.actor or "mcp",
        conversation_id=None,
        project_id=payload.project_id,
        episode_id=payload.episode_id,
        scopes="production",
    )
    try:
        return await tool_registry.execute(
            tool_name,
            payload.arguments,
            context,
            idempotency_key=payload.idempotency_key,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/tunnel/status")
async def tunnel_status() -> dict[str, Any]:
    return await mcp_tunnel_service.get_status()


@router.post("/tunnel/start")
async def tunnel_start(payload: TunnelStartRequest) -> dict[str, Any]:
    try:
        return await mcp_tunnel_service.start_tunnel(
            confirm=payload.confirm,
            ttl_minutes=payload.ttl_minutes,
            actor="user",
        )
    except ServiceError as exc:
        _raise(exc)


@router.post("/tunnel/stop")
async def tunnel_stop() -> dict[str, Any]:
    try:
        return await mcp_tunnel_service.stop_tunnel(actor="user", reason="user")
    except ServiceError as exc:
        _raise(exc)
