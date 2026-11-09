from __future__ import annotations

import json
from typing import Any, AsyncGenerator

from ..core.runtime import openai_settings
from ..services.errors import ConfigurationError, ServiceError
from . import conversation_manager, context_manager
from .tool_registry import ToolContext, ToolRegistry, tool_registry


def _extract_response(response: Any) -> tuple[str, list[dict[str, Any]]]:
    text_parts: list[str] = []
    calls: list[dict[str, Any]] = []
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        text_parts.append(output_text.strip())
    for item in getattr(response, "output", []) or []:
        item_type = getattr(item, "type", None)
        if item_type == "message":
            for content in getattr(item, "content", []) or []:
                value = getattr(content, "text", None)
                if isinstance(value, str) and value.strip():
                    text_parts.append(value.strip())
        elif item_type == "function_call":
            arguments = getattr(item, "arguments", None)
            calls.append(
                {
                    "name": getattr(item, "name", ""),
                    "call_id": getattr(item, "call_id", None),
                    "arguments": arguments,
                }
            )
    # Some SDK versions expose output items as dictionaries.
    for item in getattr(response, "output", []) or []:
        if isinstance(item, dict):
            if item.get("type") == "message":
                for content in item.get("content") or []:
                    if isinstance(content, dict) and isinstance(content.get("text"), str):
                        text_parts.append(content["text"])
            elif item.get("type") == "function_call":
                calls.append(
                    {
                        "name": item.get("name", ""),
                        "call_id": item.get("call_id"),
                        "arguments": item.get("arguments"),
                    }
                )
    return "\n".join(dict.fromkeys(text_parts)).strip(), calls


def _parse_arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


class AIDirector:
    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or tool_registry

    async def run_turn(
        self,
        conversation_id: str,
        message: str,
        *,
        project_id: str | None = None,
        episode_id: str | None = None,
        actor: str = "ai_director",
    ) -> dict[str, Any]:
        settings = openai_settings()
        if not settings["api_key"] or not settings["model"]:
            raise ConfigurationError("OpenAI is not configured. Set OPENAI_API_KEY and OPENAI_MODEL.")
        conversation = conversation_manager.get_conversation(conversation_id)
        project_id = project_id or conversation.get("project_id")
        episode_id = episode_id or conversation.get("episode_id")
        conversation_manager.add_message(conversation_id, "user", message)
        context = context_manager.build_context(project_id, episode_id)
        conversation_manager.add_context_snapshot(conversation_id, project_id, context)
        system = context_manager.system_prompt(project_id, episode_id)
        history = conversation_manager.get_conversation(conversation_id)["messages"]
        input_items: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for item in history[-24:]:
            if item.get("role") in ("user", "assistant") and item.get("content"):
                input_items.append({"role": item["role"], "content": item["content"]})
        tool_context = ToolContext(
            actor=actor,
            conversation_id=conversation_id,
            project_id=project_id,
            episode_id=episode_id,
        )
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings["api_key"], base_url=settings["base_url"])
        tools = self.registry.openai_tools()
        assistant_text = ""
        tool_records: list[dict[str, Any]] = []
        response_id: str | None = None
        previous_response_id: str | None = None
        next_input: Any = input_items
        confirmation_required = False
        for _ in range(max(1, settings["max_tool_rounds"])):
            request: dict[str, Any] = {
                "model": settings["model"],
                "input": next_input,
                "tools": tools,
                "tool_choice": "auto",
            }
            if previous_response_id:
                request["previous_response_id"] = previous_response_id
            response = await client.responses.create(**request)
            response_id = getattr(response, "id", None) or response_id
            text, calls = _extract_response(response)
            if text:
                assistant_text = (assistant_text + "\n" + text).strip() if assistant_text else text
            if not calls:
                break
            tool_outputs: list[dict[str, Any]] = []
            for call in calls:
                call_id = call.get("call_id") or call.get("id")
                if not call_id:
                    continue
                result = await self.registry.execute(
                    call.get("name", ""),
                    _parse_arguments(call.get("arguments")),
                    tool_context,
                    idempotency_key=None,
                )
                if result.get("confirmation_required"):
                    confirmation_required = True
                tool_records.append(
                    {
                        "name": call.get("name"),
                        "call_id": call_id,
                        "arguments": _parse_arguments(call.get("arguments")),
                        "result": result,
                    }
                )
                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(result, ensure_ascii=False),
                    }
                )
            if not tool_outputs:
                break
            previous_response_id = response_id
            next_input = tool_outputs
        if not assistant_text:
            if confirmation_required:
                assistant_text = "This action needs your explicit confirmation. Reply 'yes' to proceed."
            elif tool_records:
                assistant_text = "I completed the requested actions. Review the tool results for the exact job and asset IDs."
            else:
                assistant_text = "I did not receive a response from the model. Please try again."
        conversation_manager.add_message(
            conversation_id,
            "assistant",
            assistant_text,
            tool_calls=tool_records,
            response_id=response_id,
        )
        conversation_manager.update_conversation(
            conversation_id,
            last_response_id=response_id,
            context=context,
            project_id=project_id,
            episode_id=episode_id,
        )
        return {
            "conversation_id": conversation_id,
            "message": assistant_text,
            "tool_executions": tool_records,
            "response_id": response_id,
            "confirmation_required": confirmation_required,
            "context": context,
        }

    async def stream_turn(
        self,
        conversation_id: str,
        message: str,
        *,
        project_id: str | None = None,
        episode_id: str | None = None,
        actor: str = "ai_director",
    ) -> AsyncGenerator[dict[str, Any], None]:
        yield {"event": "status", "data": {"message": "Thinking…"}}
        try:
            result = await self.run_turn(
                conversation_id,
                message,
                project_id=project_id,
                episode_id=episode_id,
                actor=actor,
            )
            for execution in result.get("tool_executions") or []:
                yield {
                    "event": "tool_execution",
                    "data": {
                        "name": execution.get("name"),
                        "result": execution.get("result"),
                    },
                }
            yield {
                "event": "assistant_message",
                "data": {
                    "message": result.get("message"),
                    "confirmation_required": result.get("confirmation_required"),
                    "response_id": result.get("response_id"),
                },
            }
        except ServiceError as exc:
            yield {"event": "error", "data": {"error": exc.message, "code": exc.code}}
        except Exception as exc:  # noqa: BLE001
            yield {"event": "error", "data": {"error": str(exc), "code": "ai_error"}}
        yield {"event": "done", "data": {}}


director = AIDirector()
