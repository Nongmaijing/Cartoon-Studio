from __future__ import annotations

import json
from typing import Any, AsyncGenerator

from ..core.runtime import openai_settings
from ..services.errors import ConfigurationError, ServiceError
from ..services.llm_provider import llm_settings, ollama_models
from . import conversation_manager, context_manager
from .tool_registry import ToolContext, ToolRegistry, tool_registry

OPENAI_PREFIX = "openai:"
OLLAMA_PREFIX = "ollama:"


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


def _split_model_ref(value: str) -> tuple[str | None, str]:
    if value.startswith(OPENAI_PREFIX):
        return "openai", value[len(OPENAI_PREFIX) :]
    if value.startswith(OLLAMA_PREFIX):
        return "ollama", value[len(OLLAMA_PREFIX) :]
    return None, value


def resolve_director_model(
    conversation: dict[str, Any],
    provider: str | None = None,
    model: str | None = None,
) -> tuple[str, str]:
    """Resolve the requested provider/model, then conversation, then configured default."""
    provider = (provider or "").strip().lower() or None
    model = (model or "").strip() or None
    conversation_model = str(conversation.get("model") or "").strip()

    if not provider and not model and conversation_model:
        prefix, bare = _split_model_ref(conversation_model)
        if prefix:
            return prefix, bare
        model = conversation_model

    if model:
        prefix, bare = _split_model_ref(model)
        if prefix:
            return prefix, bare
        if provider in ("openai", "ollama"):
            return provider, model

    if provider not in ("openai", "ollama"):
        settings = openai_settings()
        provider = "openai" if settings["api_key"] and settings["model"] else "ollama"

    if provider == "openai":
        settings = openai_settings()
        if not settings["api_key"]:
            raise ConfigurationError("OpenAI is not configured. Set OPENAI_API_KEY or choose a local model.")
        return "openai", model or str(settings["model"])

    return "ollama", model or str(llm_settings()["ollama_model"])


def _chat_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert the registry's flat tool schema into Chat Completions format."""
    converted = []
    for tool in tools:
        converted.append(
            {
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters") or {"type": "object", "properties": {}},
                },
            }
        )
    return converted


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
        provider: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        conversation = conversation_manager.get_conversation(conversation_id)
        provider, model = resolve_director_model(conversation, provider, model)
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

        if provider == "openai":
            text, records, response_id, confirmation_required = await self._openai_loop(
                model, input_items, tool_context
            )
        else:
            text, records, response_id, confirmation_required = await self._ollama_loop(
                model, input_items, tool_context
            )

        if not text:
            if confirmation_required:
                text = "This action needs your explicit confirmation. Reply 'yes' to proceed."
            elif records:
                text = "I completed the requested actions. Review the tool results for the exact job and asset IDs."
            else:
                text = "I did not receive a response from the model. Please try again."
        conversation_manager.add_message(
            conversation_id,
            "assistant",
            text,
            tool_calls=records,
            response_id=response_id,
        )
        conversation_manager.update_conversation(
            conversation_id,
            last_response_id=response_id,
            context=context,
            project_id=project_id,
            episode_id=episode_id,
            model=f"{provider}:{model}",
        )
        return {
            "conversation_id": conversation_id,
            "message": text,
            "tool_executions": records,
            "response_id": response_id,
            "confirmation_required": confirmation_required,
            "context": context,
            "provider": provider,
            "model": model,
        }

    async def _openai_loop(
        self,
        model: str,
        input_items: list[dict[str, Any]],
        tool_context: ToolContext,
    ) -> tuple[str, list[dict[str, Any]], str | None, bool]:
        settings = openai_settings()
        if not settings["api_key"] or not model:
            raise ConfigurationError("OpenAI is not configured. Set OPENAI_API_KEY and OPENAI_MODEL.")
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
                "model": model,
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
        return assistant_text, tool_records, response_id, confirmation_required

    async def _ollama_loop(
        self,
        model: str,
        input_items: list[dict[str, Any]],
        tool_context: ToolContext,
    ) -> tuple[str, list[dict[str, Any]], str | None, bool]:
        settings = llm_settings()
        available = await ollama_models()
        target = next((item for item in available if item.get("name") == model), None)
        if target is None:
            names = ", ".join(str(item.get("name")) for item in available[:12]) or "none"
            raise ConfigurationError(
                f"Local model '{model}' is not installed in Ollama. Available: {names}."
            )
        if "tools" not in (target.get("capabilities") or []):
            raise ConfigurationError(
                f"Local model '{model}' does not support tool calling. Choose a tools-capable model."
            )
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key="ollama",
            base_url=f"{str(settings['ollama_url']).rstrip('/')}/v1",
        )
        tools = _chat_tools(self.registry.openai_tools())
        rounds = max(1, int((openai_settings().get("max_tool_rounds") or 6)))
        messages: list[dict[str, Any]] = list(input_items)
        assistant_text = ""
        tool_records: list[dict[str, Any]] = []
        response_id: str | None = None
        confirmation_required = False
        for _ in range(rounds):
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
            )
            response_id = getattr(response, "id", None) or response_id
            choice = response.choices[0].message
            text = (choice.content or "").strip()
            if text:
                assistant_text = (assistant_text + "\n" + text).strip() if assistant_text else text
            calls = list(getattr(choice, "tool_calls", None) or [])
            if not calls:
                break
            assistant_message: dict[str, Any] = {"role": "assistant", "content": text or ""}
            assistant_message["tool_calls"] = [
                {
                    "id": getattr(call, "id", None),
                    "type": "function",
                    "function": {
                        "name": getattr(getattr(call, "function", None), "name", ""),
                        "arguments": getattr(getattr(call, "function", None), "arguments", "{}"),
                    },
                }
                for call in calls
            ]
            messages.append(assistant_message)
            tool_messages: list[dict[str, Any]] = []
            for call in calls:
                function = getattr(call, "function", None)
                name = getattr(function, "name", "")
                arguments = _parse_arguments(getattr(function, "arguments", "{}"))
                call_id = getattr(call, "id", None)
                result = await self.registry.execute(
                    name,
                    arguments,
                    tool_context,
                    idempotency_key=None,
                )
                if result.get("confirmation_required"):
                    confirmation_required = True
                tool_records.append(
                    {
                        "name": name,
                        "call_id": call_id,
                        "arguments": arguments,
                        "result": result,
                    }
                )
                tool_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            if not tool_messages:
                break
            messages.extend(tool_messages)
        return assistant_text, tool_records, response_id, confirmation_required

    async def stream_turn(
        self,
        conversation_id: str,
        message: str,
        *,
        project_id: str | None = None,
        episode_id: str | None = None,
        actor: str = "ai_director",
        provider: str | None = None,
        model: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        yield {"event": "status", "data": {"message": "Thinking…"}}
        try:
            result = await self.run_turn(
                conversation_id,
                message,
                project_id=project_id,
                episode_id=episode_id,
                actor=actor,
                provider=provider,
                model=model,
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
                    "provider": result.get("provider"),
                    "model": result.get("model"),
                },
            }
        except ServiceError as exc:
            yield {"event": "error", "data": {"error": exc.message, "code": exc.code}}
        except Exception as exc:  # noqa: BLE001
            yield {"event": "error", "data": {"error": str(exc), "code": "ai_error"}}
        yield {"event": "done", "data": {}}


director = AIDirector()
