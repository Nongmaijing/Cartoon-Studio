from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import jsonschema

from ..core.runtime import openai_settings
from ..db import execute, now, query_one
from ..services import (
    audio_service,
    character_service,
    dialogue_service,
    episode_service,
    production_service,
    project_service,
    quality_control_service,
    scene_service,
    script_service,
    storyboard_service,
)
from ..services.audit_service import log
from ..services.errors import ServiceError
from ..services.assets import get_asset
from ..services.jobs import get_job


@dataclass
class ToolContext:
    actor: str = "ai_director"
    conversation_id: str | None = None
    project_id: str | None = None
    episode_id: str | None = None
    scopes: str = "production"


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any], ToolContext], Awaitable[dict[str, Any]]]
    scope: str = "read"
    confirmation_required: bool = False
    timeout_seconds: float = 300.0
    tags: list[str] = field(default_factory=list)


def _obj(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


PROJECT_ID = {"type": "string", "description": "Project identifier"}
EPISODE_ID = {"type": "string", "description": "Episode identifier"}
CHARACTER_ID = {"type": "string", "description": "Character identifier"}
SCENE_ID = {"type": "string", "description": "Scene identifier"}
RUN_ID = {"type": "string", "description": "Production run identifier"}
JOB_ID = {"type": "string", "description": "Generation job identifier"}
ASSET_ID = {"type": "string", "description": "Asset identifier"}
LINE_ID = {"type": "string", "description": "Dialogue line identifier"}
CONFIRM = {"type": "boolean", "default": False, "description": "Explicit confirmation for expensive/destructive actions"}
IDEMPOTENCY = {"type": "string", "description": "Optional idempotency key for safe retries"}


def _project(args: dict[str, Any], ctx: ToolContext) -> str:
    value = args.get("project_id") or ctx.project_id
    if not value:
        raise ServiceError("project_id is required.")
    return str(value)


def _episode(args: dict[str, Any], ctx: ToolContext) -> str:
    value = args.get("episode_id") or ctx.episode_id
    if not value:
        raise ServiceError("episode_id is required.")
    return str(value)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            lowered = key.lower()
            if any(secret in lowered for secret in ("api_key", "authorization", "password", "secret", "bearer")):
                result[key] = "[redacted]"
            else:
                result[key] = _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if not tool:
            raise ServiceError(f"Unknown tool '{name}'.", status_code=404, code="unknown_tool")
        return tool

    def list_tools(self) -> list[Tool]:
        return sorted(self._tools.values(), key=lambda item: item.name)

    def openai_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            }
            for tool in self.list_tools()
        ]

    def mcp_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": tool.name, "description": tool.description, "inputSchema": tool.input_schema}
            for tool in self.list_tools()
        ]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any] | None,
        context: ToolContext,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        tool = self._tools.get(name)
        if not tool:
            return {
                "ok": False,
                "tool": name,
                "error": f"Unknown tool '{name}'.",
                "code": "unknown_tool",
                "status_code": 404,
            }
        args = dict(arguments or {})
        idempotency_key = idempotency_key or args.pop("idempotency_key", None)
        if "confirm" in (tool.input_schema.get("properties") or {}):
            args.setdefault("confirm", False)
        try:
            jsonschema.validate(args, tool.input_schema)
        except jsonschema.ValidationError as exc:
            return {
                "ok": False,
                "tool": name,
                "error": f"Invalid arguments: {exc.message}",
                "code": "validation_error",
            }
        if tool.confirmation_required and not args.get("confirm"):
            return {
                "ok": False,
                "tool": name,
                "confirmation_required": True,
                "message": "This operation is expensive or destructive. Ask the user for explicit confirmation, then call again with confirm=true.",
            }
        if idempotency_key:
            existing = query_one(
                "SELECT result_json, status FROM ai_tool_executions WHERE tool_name = ? AND idempotency_key = ?",
                (name, idempotency_key),
            )
            if existing:
                try:
                    result = json.loads(existing.get("result_json") or "{}")
                except json.JSONDecodeError:
                    result = {}
                return {"ok": True, "tool": name, "idempotent_replay": True, **result}
        execution_id = uuid.uuid4().hex[:12]
        execute(
            """INSERT INTO ai_tool_executions
               (id, conversation_id, tool_name, arguments_json, result_json, status, actor, idempotency_key, created_at)
               VALUES (?, ?, ?, ?, '{}', 'running', ?, ?, ?)""",
            (
                execution_id,
                context.conversation_id,
                name,
                json.dumps(_redact(args)),
                context.actor,
                idempotency_key,
                now(),
            ),
        )
        try:
            result = await asyncio.wait_for(tool.handler(args, context), timeout=tool.timeout_seconds)
            result = _redact(result) if isinstance(result, dict) else {"result": _redact(result)}
            result.setdefault("ok", True)
            result["tool"] = name
            execute(
                "UPDATE ai_tool_executions SET status='completed', result_json=?, finished_at=? WHERE id=?",
                (json.dumps(result), now(), execution_id),
            )
            log(context.actor, f"tool:{name}", "tool_execution", execution_id, {"ok": True})
            return result
        except asyncio.TimeoutError:
            error = f"Tool '{name}' timed out after {tool.timeout_seconds}s."
            execute(
                "UPDATE ai_tool_executions SET status='failed', error=?, finished_at=? WHERE id=?",
                (error, now(), execution_id),
            )
            log(context.actor, f"tool:{name}", "tool_execution", execution_id, {"error": error})
            return {"ok": False, "tool": name, "error": error, "code": "timeout"}
        except ServiceError as exc:
            execute(
                "UPDATE ai_tool_executions SET status='failed', error=?, finished_at=? WHERE id=?",
                (exc.message, now(), execution_id),
            )
            log(context.actor, f"tool:{name}", "tool_execution", execution_id, {"error": exc.message})
            return {"ok": False, "tool": name, "error": exc.message, "code": exc.code, "status_code": exc.status_code}
        except Exception as exc:  # noqa: BLE001
            execute(
                "UPDATE ai_tool_executions SET status='failed', error=?, finished_at=? WHERE id=?",
                (str(exc)[:4000], now(), execution_id),
            )
            log(context.actor, f"tool:{name}", "tool_execution", execution_id, {"error": str(exc)[:1000]})
            return {"ok": False, "tool": name, "error": str(exc), "code": "tool_error"}


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()

    async def list_projects(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return {"projects": project_service.list_projects(bool(args.get("include_archived", False)))}

    async def create_project(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return {"project": project_service.create_project(args["name"], args.get("description", ""), actor=ctx.actor)}

    async def get_project_details(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return {"project": project_service.get_project(_project(args, ctx))}

    async def update_project(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        project_id = _project(args, ctx)
        updates = {key: args[key] for key in ("name", "description", "archived", "memory") if key in args}
        return {"project": project_service.update_project(project_id, actor=ctx.actor, **updates)}

    async def archive_project(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return {"project": project_service.archive_project(_project(args, ctx), actor=ctx.actor)}

    registry.register(Tool("list_projects", "List projects.", _obj({"include_archived": {"type": "boolean"}}), list_projects))
    registry.register(Tool("create_project", "Create a project.", _obj({"name": {"type": "string"}, "description": {"type": "string"}}, ["name"]), create_project, scope="write"))
    registry.register(Tool("get_project_details", "Get project details, counts and memory.", _obj({"project_id": PROJECT_ID}), get_project_details))
    registry.register(Tool("update_project", "Update project name, description, archive flag or memory.", _obj({"project_id": PROJECT_ID, "name": {"type": "string"}, "description": {"type": "string"}, "archived": {"type": "boolean"}, "memory": {"type": "object"}}, ["project_id"]), update_project, scope="write"))
    registry.register(Tool("archive_project", "Archive a project without deleting its data.", _obj({"project_id": PROJECT_ID}, ["project_id"]), archive_project, scope="write"))

    async def list_episodes(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return {"episodes": episode_service.list_episodes(args.get("project_id") or ctx.project_id)}

    async def create_episode(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return {"episode": episode_service.create_episode(_project(args, ctx), args["name"], args.get("description", ""), actor=ctx.actor)}

    async def get_episode_details(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return {"episode": episode_service.get_episode(_episode(args, ctx))}

    async def update_episode(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return {"episode": episode_service.update_episode(_episode(args, ctx), name=args.get("name"), description=args.get("description"), actor=ctx.actor)}

    async def delete_episode(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return episode_service.delete_episode(_episode(args, ctx), actor=ctx.actor, confirm=bool(args.get("confirm")))

    async def get_episode_status(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return episode_service.get_status(_episode(args, ctx))

    registry.register(Tool("list_episodes", "List episodes for a project.", _obj({"project_id": PROJECT_ID}), list_episodes))
    registry.register(Tool("create_episode", "Create an episode.", _obj({"project_id": PROJECT_ID, "name": {"type": "string"}, "description": {"type": "string"}}, ["project_id", "name"]), create_episode, scope="write"))
    registry.register(Tool("get_episode_details", "Get an episode, timeline and memory.", _obj({"episode_id": EPISODE_ID}), get_episode_details))
    registry.register(Tool("update_episode", "Update episode name or description.", _obj({"episode_id": EPISODE_ID, "name": {"type": "string"}, "description": {"type": "string"}}, ["episode_id"]), update_episode, scope="write"))
    registry.register(Tool("delete_episode", "Delete an episode. Requires confirm=true.", _obj({"episode_id": EPISODE_ID, "confirm": CONFIRM}, ["episode_id"]), delete_episode, scope="write", confirmation_required=True))
    registry.register(Tool("get_episode_status", "Read episode export and production status.", _obj({"episode_id": EPISODE_ID}, ["episode_id"]), get_episode_status))

    async def list_characters(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return {"characters": character_service.list_characters(args.get("project_id") or ctx.project_id)}

    async def create_character(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        fields = {key: args[key] for key in ("description", "style", "clothing", "appearance", "voice_engine", "voice_name", "voice_rate", "voice_pitch", "voice_volume") if key in args}
        return {"character": character_service.create_character(_project(args, ctx), name=args["name"], actor=ctx.actor, **fields)}

    async def update_character(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        fields = {key: args[key] for key in ("name", "description", "style", "clothing", "appearance", "voice_engine", "voice_name", "voice_rate", "voice_pitch", "voice_volume", "memory_json") if key in args}
        return {"character": character_service.update_character(args["character_id"], fields, actor=ctx.actor)}

    async def get_character_details(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return {"character": character_service.get_character(args["character_id"])}

    async def generate_character_sheet(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        values = {key: args[key] for key in ("kind", "label", "width", "height", "steps", "cfg", "seed", "prompt", "negative_prompt", "reference_asset_id", "reference_mode", "denoise", "control_strength") if key in args}
        return await character_service.generate_sheet(args["character_id"], actor=ctx.actor, **values)

    async def get_character_references(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return character_service.get_references(args["character_id"])

    async def approve_character(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return character_service.approve_character(args["character_id"], actor=ctx.actor)

    registry.register(Tool("list_characters", "List characters.", _obj({"project_id": PROJECT_ID}), list_characters))
    registry.register(Tool("create_character", "Create a character profile.", _obj({"project_id": PROJECT_ID, "name": {"type": "string"}, "description": {"type": "string"}, "style": {"type": "string"}, "clothing": {"type": "string"}, "appearance": {"type": "string"}, "voice_engine": {"type": "string"}, "voice_name": {"type": "string"}, "voice_rate": {"type": "integer"}, "voice_pitch": {"type": "integer"}, "voice_volume": {"type": "integer"}}, ["project_id", "name"]), create_character, scope="write"))
    registry.register(Tool("update_character", "Update a character profile.", _obj({"character_id": CHARACTER_ID, "name": {"type": "string"}, "description": {"type": "string"}, "style": {"type": "string"}, "clothing": {"type": "string"}, "appearance": {"type": "string"}, "voice_engine": {"type": "string"}, "voice_name": {"type": "string"}, "voice_rate": {"type": "integer"}, "voice_pitch": {"type": "integer"}, "voice_volume": {"type": "integer"}, "memory_json": {"type": "string"}}, ["character_id"]), update_character, scope="write"))
    registry.register(Tool("get_character_details", "Get a character and memory.", _obj({"character_id": CHARACTER_ID}, ["character_id"]), get_character_details))
    registry.register(Tool("generate_character_sheet", "Generate a character reference/expression/pose image. Requires confirm=true.", _obj({"character_id": CHARACTER_ID, "kind": {"enum": ["reference", "expression", "pose"]}, "label": {"type": "string"}, "width": {"type": "integer"}, "height": {"type": "integer"}, "steps": {"type": "integer"}, "cfg": {"type": "number"}, "seed": {"type": "integer"}, "prompt": {"type": "string"}, "negative_prompt": {"type": "string"}, "reference_asset_id": {"type": "string"}, "reference_mode": {"enum": ["identity", "pose"]}, "denoise": {"type": "number"}, "control_strength": {"type": "number"}, "confirm": CONFIRM}, ["character_id"]), generate_character_sheet, scope="production", confirmation_required=True, timeout_seconds=600))
    registry.register(Tool("get_character_references", "Get canonical, reference, expression and pose assets.", _obj({"character_id": CHARACTER_ID}, ["character_id"]), get_character_references))
    registry.register(Tool("approve_character", "Approve a character and snapshot its version.", _obj({"character_id": CHARACTER_ID}, ["character_id"]), approve_character, scope="write"))

    async def generate_story(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return await script_service.generate_story(_project(args, ctx), args["premise"], args.get("episode_id") or ctx.episode_id, actor=ctx.actor)

    async def generate_script(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return await script_service.generate_script(_episode(args, ctx), args.get("instructions"), actor=ctx.actor)

    async def revise_script(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return await script_service.revise_script(_episode(args, ctx), args["instructions"], actor=ctx.actor)

    async def approve_script(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return script_service.approve_script(_episode(args, ctx), actor=ctx.actor)

    async def create_storyboard(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return await storyboard_service.create_storyboard(_episode(args, ctx), actor=ctx.actor)

    async def get_storyboard(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return storyboard_service.get_storyboard(_episode(args, ctx))

    registry.register(Tool("generate_story", "Generate a children's story with OpenAI and store it in the episode.", _obj({"project_id": PROJECT_ID, "premise": {"type": "string"}, "episode_id": EPISODE_ID}, ["project_id", "premise"]), generate_story, scope="write", timeout_seconds=300))
    registry.register(Tool("generate_script", "Generate a production script from the episode story.", _obj({"episode_id": EPISODE_ID, "instructions": {"type": "string"}}, ["episode_id"]), generate_script, scope="write", timeout_seconds=300))
    registry.register(Tool("revise_script", "Revise the episode script with instructions.", _obj({"episode_id": EPISODE_ID, "instructions": {"type": "string"}}, ["episode_id", "instructions"]), revise_script, scope="write", timeout_seconds=300))
    registry.register(Tool("approve_script", "Approve the episode script.", _obj({"episode_id": EPISODE_ID}, ["episode_id"]), approve_script, scope="write"))
    registry.register(Tool("create_storyboard", "Create scenes and dialogue from the approved script.", _obj({"episode_id": EPISODE_ID}, ["episode_id"]), create_storyboard, scope="write", timeout_seconds=300))
    registry.register(Tool("get_storyboard", "Get the episode storyboard and scenes.", _obj({"episode_id": EPISODE_ID}, ["episode_id"]), get_storyboard))

    async def list_scenes(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return {"scenes": scene_service.list_scenes(args.get("project_id") or ctx.project_id)}

    async def get_scene_details(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return {"scene": scene_service.get_scene_details(args["scene_id"])}

    async def update_scene(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        fields = {key: args[key] for key in ("name", "description", "dialogue", "action", "camera", "duration", "background_id", "character_ids", "settings") if key in args}
        return {"scene": scene_service.update_scene(args["scene_id"], fields, actor=ctx.actor)}

    async def generate_scene_image(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        values = {key: args[key] for key in ("prompt", "negative_prompt", "width", "height", "steps", "cfg", "seed", "workflow_id", "reference_asset_id", "reference_mode", "denoise", "control_strength") if key in args}
        return await scene_service.generate_scene_image(args["scene_id"], actor=ctx.actor, **values)

    async def regenerate_scene(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        values = {key: args[key] for key in ("prompt", "negative_prompt", "width", "height", "steps", "cfg", "seed", "workflow_id", "reference_asset_id", "reference_mode", "denoise", "control_strength") if key in args}
        return await scene_service.regenerate_scene(args["scene_id"], actor=ctx.actor, **values)

    async def approve_scene(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return scene_service.approve_scene(args["scene_id"], actor=ctx.actor, notes=args.get("notes", ""))

    async def reject_scene(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return scene_service.reject_scene(args["scene_id"], actor=ctx.actor, notes=args.get("notes", ""))

    registry.register(Tool("list_scenes", "List scenes.", _obj({"project_id": PROJECT_ID}), list_scenes))
    registry.register(Tool("get_scene_details", "Get scene, cast, media and quality status.", _obj({"scene_id": SCENE_ID}, ["scene_id"]), get_scene_details))
    registry.register(Tool("update_scene", "Update scene text, camera, duration, cast or settings.", _obj({"scene_id": SCENE_ID, "name": {"type": "string"}, "description": {"type": "string"}, "dialogue": {"type": "string"}, "action": {"type": "string"}, "camera": {"type": "string"}, "duration": {"type": "number"}, "background_id": {"type": "string"}, "character_ids": {"type": "array", "items": {"type": "string"}}, "settings": {"type": "object"}}, ["scene_id"]), update_scene, scope="write"))
    registry.register(Tool("generate_scene_image", "Generate a scene keyframe. Requires confirm=true.", _obj({"scene_id": SCENE_ID, "prompt": {"type": "string"}, "negative_prompt": {"type": "string"}, "width": {"type": "integer"}, "height": {"type": "integer"}, "steps": {"type": "integer"}, "cfg": {"type": "number"}, "seed": {"type": "integer"}, "workflow_id": {"type": "string"}, "reference_asset_id": {"type": "string"}, "reference_mode": {"enum": ["identity", "pose"]}, "denoise": {"type": "number"}, "control_strength": {"type": "number"}, "confirm": CONFIRM}, ["scene_id"]), generate_scene_image, scope="production", confirmation_required=True, timeout_seconds=600))
    registry.register(Tool("regenerate_scene", "Regenerate a scene keyframe. Requires confirm=true.", _obj({"scene_id": SCENE_ID, "prompt": {"type": "string"}, "negative_prompt": {"type": "string"}, "width": {"type": "integer"}, "height": {"type": "integer"}, "steps": {"type": "integer"}, "cfg": {"type": "number"}, "seed": {"type": "integer"}, "workflow_id": {"type": "string"}, "reference_asset_id": {"type": "string"}, "reference_mode": {"enum": ["identity", "pose"]}, "denoise": {"type": "number"}, "control_strength": {"type": "number"}, "confirm": CONFIRM}, ["scene_id"]), regenerate_scene, scope="production", confirmation_required=True, timeout_seconds=600))
    registry.register(Tool("approve_scene", "Approve a scene.", _obj({"scene_id": SCENE_ID, "notes": {"type": "string"}}, ["scene_id"]), approve_scene, scope="write"))
    registry.register(Tool("reject_scene", "Reject a scene and record notes.", _obj({"scene_id": SCENE_ID, "notes": {"type": "string"}}, ["scene_id"]), reject_scene, scope="write"))

    async def animate_scene(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        values = {key: args[key] for key in ("prompt", "negative_prompt", "width", "height", "steps", "cfg", "seed", "length", "fps", "start_image", "workflow_id") if key in args}
        return await scene_service.animate_scene(args["scene_id"], actor=ctx.actor, **values)

    async def regenerate_animation(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        values = {key: args[key] for key in ("prompt", "negative_prompt", "width", "height", "steps", "cfg", "seed", "length", "fps", "start_image", "workflow_id") if key in args}
        return await scene_service.regenerate_animation(args["scene_id"], actor=ctx.actor, **values)

    async def get_animation_preview(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return scene_service.get_animation_preview(args["scene_id"])

    async def approve_animation(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return scene_service.approve_animation(args["scene_id"], actor=ctx.actor)

    registry.register(Tool("animate_scene", "Animate a scene keyframe. Requires confirm=true.", _obj({"scene_id": SCENE_ID, "prompt": {"type": "string"}, "negative_prompt": {"type": "string"}, "width": {"type": "integer"}, "height": {"type": "integer"}, "steps": {"type": "integer"}, "cfg": {"type": "number"}, "seed": {"type": "integer"}, "length": {"type": "integer"}, "fps": {"type": "number"}, "start_image": {"type": "string"}, "workflow_id": {"type": "string"}, "confirm": CONFIRM}, ["scene_id"]), animate_scene, scope="production", confirmation_required=True, timeout_seconds=600))
    registry.register(Tool("regenerate_animation", "Regenerate a scene animation. Requires confirm=true.", _obj({"scene_id": SCENE_ID, "prompt": {"type": "string"}, "negative_prompt": {"type": "string"}, "width": {"type": "integer"}, "height": {"type": "integer"}, "steps": {"type": "integer"}, "cfg": {"type": "number"}, "seed": {"type": "integer"}, "length": {"type": "integer"}, "fps": {"type": "number"}, "start_image": {"type": "string"}, "workflow_id": {"type": "string"}, "confirm": CONFIRM}, ["scene_id"]), regenerate_animation, scope="production", confirmation_required=True, timeout_seconds=600))
    registry.register(Tool("get_animation_preview", "Get generated animation previews for a scene.", _obj({"scene_id": SCENE_ID}, ["scene_id"]), get_animation_preview))
    registry.register(Tool("approve_animation", "Approve the latest scene animation.", _obj({"scene_id": SCENE_ID}, ["scene_id"]), approve_animation, scope="write"))

    async def generate_dialogue(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        line = await dialogue_service.create_line(
            args["scene_id"],
            character_id=args.get("character_id"),
            text=args["text"],
            emotion=args.get("emotion", "neutral"),
            start_ms=int(args.get("start_ms", 0)),
            actor=ctx.actor,
        )
        generated = await dialogue_service.generate_line(line["id"], actor=ctx.actor)
        return {"line": generated, "asset_id": generated.get("audio_asset_id")}

    async def generate_voice(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return {"line": await dialogue_service.generate_line(args["line_id"], actor=ctx.actor)}

    async def generate_sound_effects(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return await audio_service.generate_sfx(_project(args, ctx), args.get("kind", "sparkle"), actor=ctx.actor)

    async def generate_background_music(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return await audio_service.generate_music(_project(args, ctx), float(args.get("duration", 30.0)), actor=ctx.actor)

    async def get_audio_status(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return dialogue_service.audio_status(args["scene_id"])

    registry.register(Tool("generate_dialogue", "Create and voice a dialogue line.", _obj({"scene_id": SCENE_ID, "character_id": {"type": "string"}, "text": {"type": "string"}, "emotion": {"type": "string"}, "start_ms": {"type": "integer"}}, ["scene_id", "text"]), generate_dialogue, scope="production", timeout_seconds=300))
    registry.register(Tool("generate_voice", "Regenerate audio for a dialogue line.", _obj({"line_id": LINE_ID}, ["line_id"]), generate_voice, scope="production", timeout_seconds=300))
    registry.register(Tool("generate_sound_effects", "Generate a local sound effect and store it.", _obj({"project_id": PROJECT_ID, "kind": {"type": "string"}}, ["project_id"]), generate_sound_effects, scope="production"))
    registry.register(Tool("generate_background_music", "Generate an original local music bed.", _obj({"project_id": PROJECT_ID, "duration": {"type": "number"}}, ["project_id"]), generate_background_music, scope="production"))
    registry.register(Tool("get_audio_status", "Check dialogue audio completeness.", _obj({"scene_id": SCENE_ID}, ["scene_id"]), get_audio_status))

    async def start_production(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return production_service.start_production(_project(args, ctx), _episode(args, ctx), plan=args.get("plan"), actor=ctx.actor, confirm=bool(args.get("confirm")))

    async def pause_production(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return production_service.pause_production(args["run_id"], actor=ctx.actor)

    async def resume_production(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return production_service.resume_production(args["run_id"], actor=ctx.actor)

    async def cancel_production(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return production_service.cancel_production(args["run_id"], actor=ctx.actor, confirm=bool(args.get("confirm")))

    async def get_production_status(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return production_service.get_status(args["run_id"])

    async def get_production_queue(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return {"runs": production_service.get_queue(args.get("project_id") or ctx.project_id)}

    async def get_job_status(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return get_job(args["job_id"]) or {"id": args["job_id"], "status": "not_found"}

    async def get_generation_logs(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return production_service.get_logs(args["run_id"], int(args.get("limit", 200)))

    registry.register(Tool("start_production", "Start the automated production run. Requires confirm=true.", _obj({"project_id": PROJECT_ID, "episode_id": EPISODE_ID, "plan": {"type": "object"}, "confirm": CONFIRM}, ["episode_id"]), start_production, scope="production", confirmation_required=True, timeout_seconds=120))
    registry.register(Tool("pause_production", "Pause a running production.", _obj({"run_id": RUN_ID}, ["run_id"]), pause_production, scope="production"))
    registry.register(Tool("resume_production", "Resume a paused production.", _obj({"run_id": RUN_ID}, ["run_id"]), resume_production, scope="production"))
    registry.register(Tool("cancel_production", "Cancel production. Requires confirm=true.", _obj({"run_id": RUN_ID, "confirm": CONFIRM}, ["run_id"]), cancel_production, scope="production", confirmation_required=True))
    registry.register(Tool("get_production_status", "Get production run state, tasks and progress.", _obj({"run_id": RUN_ID}, ["run_id"]), get_production_status))
    registry.register(Tool("get_production_queue", "List recent production runs.", _obj({"project_id": PROJECT_ID}), get_production_queue))
    registry.register(Tool("get_job_status", "Get a generation job status.", _obj({"job_id": JOB_ID}, ["job_id"]), get_job_status))
    registry.register(Tool("get_generation_logs", "Get production and audit logs.", _obj({"run_id": RUN_ID, "limit": {"type": "integer"}}, ["run_id"]), get_generation_logs))

    async def review_scene(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return quality_control_service.review_scene(args["scene_id"], actor=ctx.actor)

    async def review_episode(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return quality_control_service.review_episode(_episode(args, ctx), actor=ctx.actor)

    async def get_quality_report(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return quality_control_service.get_quality_report(args["entity_type"], args["entity_id"])

    async def regenerate_failed_scenes(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return production_service.regenerate_failed_scenes(_episode(args, ctx), actor=ctx.actor, confirm=bool(args.get("confirm")))

    registry.register(Tool("review_scene", "Run deterministic quality checks on a scene.", _obj({"scene_id": SCENE_ID}, ["scene_id"]), review_scene))
    registry.register(Tool("review_episode", "Run deterministic quality checks on an episode.", _obj({"episode_id": EPISODE_ID}, ["episode_id"]), review_episode))
    registry.register(Tool("get_quality_report", "Get a stored scene or episode quality report.", _obj({"entity_type": {"enum": ["scene", "episode"]}, "entity_id": {"type": "string"}}, ["entity_type", "entity_id"]), get_quality_report))
    registry.register(Tool("regenerate_failed_scenes", "Retry failed/rejected scenes. Requires confirm=true.", _obj({"episode_id": EPISODE_ID, "confirm": CONFIRM}, ["episode_id"]), regenerate_failed_scenes, scope="production", confirmation_required=True, timeout_seconds=120))

    async def render_episode(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return episode_service.render_episode(_episode(args, ctx), args.get("timeline"), actor=ctx.actor, confirm=bool(args.get("confirm")))

    async def get_episode_preview(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return episode_service.get_preview(_episode(args, ctx))

    async def get_episode_assets(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        return episode_service.get_assets(_episode(args, ctx))

    registry.register(Tool("render_episode", "Render/export the episode MP4. Requires confirm=true.", _obj({"episode_id": EPISODE_ID, "timeline": {"type": "object"}, "confirm": CONFIRM}, ["episode_id"]), render_episode, scope="production", confirmation_required=True, timeout_seconds=120))
    registry.register(Tool("get_episode_preview", "Get the rendered episode preview URLs.", _obj({"episode_id": EPISODE_ID}, ["episode_id"]), get_episode_preview))
    registry.register(Tool("export_episode", "Alias for render_episode. Requires confirm=true.", _obj({"episode_id": EPISODE_ID, "timeline": {"type": "object"}, "confirm": CONFIRM}, ["episode_id"]), render_episode, scope="production", confirmation_required=True, timeout_seconds=120))
    registry.register(Tool("get_episode_assets", "Get rendered and scene assets for an episode.", _obj({"episode_id": EPISODE_ID}, ["episode_id"]), get_episode_assets))

    return registry


tool_registry = build_registry()
