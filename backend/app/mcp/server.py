from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..ai.tool_registry import ToolContext, tool_registry
from ..ai import opencode_client
from ..core.runtime import base_url, mcp_settings
from ..core.security import verify_mcp_token
from ..services import project_service
from ..services import episode_service, production_service

logger = logging.getLogger(__name__)

TYPE_MAP = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "list",
    "object": "dict",
}


class CartoonTokenVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        info = verify_mcp_token(token)
        if not info:
            return None
        return AccessToken(
            token=token,
            client_id=str(info.get("id") or "mcp"),
            scopes=[scope.strip() for scope in str(info.get("scopes") or "production").split(",") if scope.strip()],
        )


def _python_default(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    return repr(value)


def _make_tool_function(tool: Any) -> Any:
    properties = (tool.input_schema or {}).get("properties") or {}
    required = set((tool.input_schema or {}).get("required") or [])
    required_params: list[str] = []
    optional_params: list[str] = []
    for name, spec in properties.items():
        type_name = TYPE_MAP.get(str(spec.get("type")), "Any")
        if name in required:
            required_params.append(f"{name}: {type_name}")
        else:
            optional_params.append(f"{name}: {type_name} = {_python_default(spec.get('default'))}")
    params = required_params + optional_params + ["idempotency_key: str = None"]
    source = (
        f"async def {tool.name}({', '.join(params)}) -> dict:\n"
        f"    payload = {{k: v for k, v in locals().items() if v is not None and k != 'idempotency_key'}}\n"
        f"    return await _execute_tool({tool.name!r}, payload, idempotency_key)\n"
    )
    namespace: dict[str, Any] = {"_execute_tool": _execute_tool, "Any": Any}
    exec(source, namespace)  # noqa: S102 - generated from the trusted local tool schema
    function = namespace[tool.name]
    function.__doc__ = tool.description
    function.__name__ = tool.name
    return function


async def _execute_tool(name: str, payload: dict[str, Any], idempotency_key: str | None = None) -> dict[str, Any]:
    context = ToolContext(
        actor="mcp",
        project_id=payload.get("project_id"),
        episode_id=payload.get("episode_id"),
        scopes="production",
    )
    return await tool_registry.execute(name, payload, context, idempotency_key=idempotency_key)


async def opencode_ask(
    message: str,
    session_id: str = "",
    title: str = "",
    model: str = "",
    wait_seconds: int = 45,
    delivery: str = "",
) -> dict[str, Any]:
    """Start an OpenCode coding-agent task in D:\\bro.

    The message is sent to the OpenCode HTTP API. If the task is still running after
    wait_seconds, call opencode_task with the returned session_id. Use model in the
    form provider/model, for example opencode-go/beam-free or ollama/qwen3:8b. Leave
    model empty to use the configured default. When OPENCODE_BRIDGE_SESSION_ID is set,
    omitting session_id continues that session with queue delivery instead of
    interrupting it. delivery accepts steer or queue.
    """
    try:
        return await asyncio.to_thread(
            opencode_client.ask,
            message,
            session_id=session_id or None,
            title=title,
            model=model or None,
            wait_seconds=max(0, min(int(wait_seconds), 120)),
            delivery=delivery or None,
        )
    except opencode_client.OpenCodeError as exc:
        return {"status": "failed", "error": str(exc)}


async def opencode_task(session_id: str, message_id: str = "") -> dict[str, Any]:
    """Poll an OpenCode task started by opencode_ask.

    Returns status queued, running, completed, failed or waiting_for_permission,
    plus the assistant text, tools used and any pending permission requests.
    Pass the message_id returned by opencode_ask when continuing an existing session.
    """
    try:
        return await asyncio.to_thread(
            opencode_client.task_status,
            session_id,
            message_id or None,
        )
    except opencode_client.OpenCodeError as exc:
        return {"session_id": session_id, "status": "failed", "error": str(exc)}


async def opencode_sessions(limit: int = 10) -> dict[str, Any]:
    """List recent OpenCode sessions visible to the local service."""
    try:
        items = await asyncio.to_thread(opencode_client.list_sessions, max(1, min(int(limit), 50)))
    except opencode_client.OpenCodeError as exc:
        return {"status": "failed", "error": str(exc), "sessions": []}
    return {
        "sessions": [
            {
                "session_id": item.get("id"),
                "title": item.get("title") or "",
                "updated": (item.get("time") or {}).get("updated"),
                "directory": (item.get("location") or {}).get("directory"),
                "model": item.get("model"),
            }
            for item in items
        ]
    }


async def opencode_permission(session_id: str, request_id: str, decision: str = "once") -> dict[str, Any]:
    """Answer a pending OpenCode permission request.

    decision must be once, always or reject. Only approve actions you understand;
    'always' saves a durable project-scoped rule.
    """
    try:
        return await asyncio.to_thread(
            opencode_client.reply_permission,
            session_id,
            request_id,
            decision,
        )
    except opencode_client.OpenCodeError as exc:
        return {"status": "failed", "error": str(exc)}


def _transport_security(public_url: str, allowed_hosts: list[str], allowed_origins: list[str]) -> TransportSecuritySettings:
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    parsed = urlparse(public_url) if public_url else None
    if parsed and parsed.netloc:
        hosts.append(parsed.netloc)
    if parsed and parsed.scheme and parsed.netloc:
        origins.append(f"{parsed.scheme}://{parsed.netloc}")
    # ChatGPT/OpenAI web origins, in case an Origin header is present.
    origins.extend(
        [
            "https://chatgpt.com",
            "https://chat.openai.com",
            "https://platform.openai.com",
        ]
    )
    for host in allowed_hosts:
        if host not in hosts:
            hosts.append(host)
    for origin in allowed_origins:
        if origin not in origins:
            origins.append(origin)
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


def create_mcp_server() -> FastMCP:
    settings = mcp_settings()
    public_url = settings.get("public_url") or base_url().replace("8010", str(settings["port"]))
    auth_mode = str(settings.get("auth_mode") or "bearer").lower()
    if auth_mode not in ("bearer", "none"):
        raise RuntimeError("MCP_AUTH_MODE must be 'bearer' or 'none'.")
    if auth_mode == "none" and not settings.get("allow_unauthenticated"):
        raise RuntimeError(
            "MCP_AUTH_MODE=none requires MCP_ALLOW_UNAUTHENTICATED=true. "
            "Only use this behind a private tunnel/allowlist for local ChatGPT testing."
        )

    auth_kwargs: dict[str, Any] = {}
    if auth_mode == "bearer":
        auth = AuthSettings(
            issuer_url=public_url,
            resource_server_url=public_url,
            required_scopes=["production"],
            validate_token_resource=False,
        )
        auth_kwargs = {"token_verifier": CartoonTokenVerifier(), "auth": auth}
    else:
        logger.warning(
            "MCP authentication is DISABLED (MCP_AUTH_MODE=none). "
            "Any client that can reach the endpoint can control production. "
            "Use only behind a private tunnel/allowlist and restore bearer auth afterwards."
        )

    mcp = FastMCP(
        "cartoon-studio",
        instructions=(
            "Cartoon Studio production controller. Use the tools to inspect and manage projects, "
            "characters, episodes, scenes, generation jobs, production runs and final renders. "
            "Expensive or destructive tools require confirm=true."
        ),
        host=settings["host"],
        port=int(settings["port"]),
        streamable_http_path="/mcp",
        stateless_http=True,
        transport_security=_transport_security(
            public_url,
            list(settings.get("allowed_hosts") or []),
            list(settings.get("allowed_origins") or []),
        ),
        **auth_kwargs,
    )
    for tool in tool_registry.list_tools():
        mcp.add_tool(_make_tool_function(tool), name=tool.name, description=tool.description)
    for function in (opencode_ask, opencode_task, opencode_sessions, opencode_permission):
        mcp.add_tool(function, name=function.__name__, description=(function.__doc__ or "").strip())

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:  # noqa: ARG001
        return JSONResponse(
            {
                "status": "ok",
                "server": "cartoon-studio-mcp",
                "tools": len(tool_registry.list_tools()) + 4,
                "auth": auth_mode,
            }
        )

    @mcp.resource("cartoon://projects", description="List Cartoon Studio projects")
    async def projects_resource() -> str:
        import json

        return json.dumps(project_service.list_projects(), ensure_ascii=False)

    @mcp.resource("cartoon://projects/{project_id}", description="Project details")
    async def project_resource(project_id: str) -> str:
        import json

        return json.dumps(project_service.get_project(project_id), ensure_ascii=False)

    @mcp.resource("cartoon://episodes/{episode_id}", description="Episode details")
    async def episode_resource(episode_id: str) -> str:
        import json

        return json.dumps(episode_service.get_episode(episode_id), ensure_ascii=False)

    @mcp.resource("cartoon://production/{run_id}", description="Production run status")
    async def production_resource(run_id: str) -> str:
        import json

        return json.dumps(production_service.get_status(run_id), ensure_ascii=False)

    @mcp.prompt("plan_episode", description="Plan a production from a premise")
    def plan_episode(project_id: str, premise: str) -> str:
        return (
            "Inspect the project and approved characters, develop a short children's story, "
            "script and storyboard, then present the plan and wait for confirmation before "
            f"starting expensive generation. Project: {project_id}. Premise: {premise}"
        )

    @mcp.prompt("review_scene", description="Review a scene for quality and continuity")
    def review_scene(scene_id: str) -> str:
        return f"Review scene {scene_id} for character consistency, defects and approval status."

    return mcp


mcp = create_mcp_server()
