from __future__ import annotations

import pytest

from app.ai.openai_director import _chat_tools, resolve_director_model
from app.routers import ai_director as ai_router


def test_resolve_prefixed_conversation_model():
    assert resolve_director_model({"model": "openai:gpt-test"}) == ("openai", "gpt-test")
    assert resolve_director_model({"model": "ollama:qwen3:8b"}) == ("ollama", "qwen3:8b")


def test_explicit_selection_overrides_conversation():
    conversation = {"model": "openai:gpt-test"}
    assert resolve_director_model(conversation, "ollama", "qwen2.5vl:7b") == (
        "ollama",
        "qwen2.5vl:7b",
    )


def test_default_prefers_openai_when_configured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    assert resolve_director_model({}) == ("openai", "gpt-test")


def test_default_falls_back_to_local_model_without_openai(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:8b")
    assert resolve_director_model({}) == ("ollama", "qwen3:8b")


def test_chat_tools_are_nested_for_chat_completions():
    converted = _chat_tools(
        [
            {
                "type": "function",
                "name": "list_projects",
                "description": "List projects",
                "parameters": {"type": "object", "properties": {}},
            }
        ]
    )
    assert converted[0]["type"] == "function"
    assert converted[0]["function"]["name"] == "list_projects"
    assert converted[0]["function"]["parameters"]["type"] == "object"


@pytest.mark.asyncio
async def test_director_models_lists_openai_and_local(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")

    async def fake_ollama_models():
        return [
            {
                "name": "qwen3:8b",
                "parameter_size": "8B",
                "quantization": "Q4_K_M",
                "capabilities": ["completion", "tools"],
            },
            {
                "name": "qwen2.5vl:7b",
                "parameter_size": "7B",
                "quantization": "Q4_K_M",
                "capabilities": ["completion", "vision"],
            },
        ]

    monkeypatch.setattr(ai_router.llm_provider, "ollama_models", fake_ollama_models)
    result = await ai_router.director_models()
    by_id = {item["id"]: item for item in result["models"]}
    assert by_id["openai:gpt-test"]["tools"] is True
    assert by_id["ollama:qwen3:8b"]["tools"] is True
    assert by_id["ollama:qwen2.5vl:7b"]["tools"] is False
    assert result["default"] == "openai:gpt-test"
