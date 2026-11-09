from __future__ import annotations

import inspect
from typing import Any

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..ai.tool_registry import ToolContext, tool_registry
from ..core.runtime import base_url, mcp_settings
from ..core.security import verify_mcp_token
from ..services import project_service
from ..services import episode_service, production_service
from ..services.errors import ServiceError

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


def create_mcp_server() -> FastMCP:
    settings = mcp_settings()
    public_url = settings.get("public_url") or base_url().replace("8010", str(settings["port"]))
    auth = AuthSettings(
        issuer_url=public_url,
        resource_server_url=public_url,
        required_scopes=["production"],
        validate_token_resource=False,
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
        token_verifier=CartoonTokenVerifier(),
        auth=auth,
        stateless_http=True,
    )
    for tool in tool_registry.list_tools():
        mcp.add_tool(_make_tool_function(tool), name=tool.name, description=tool.description)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:  # noqa: ARG001
        return JSONResponse(
            {
                "status": "ok",
                "server": "cartoon-studio-mcp",
                "tools": len(tool_registry.list_tools()),
                "auth": "bearer",
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
