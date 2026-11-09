from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai import conversation_manager
from app.ai.openai_director import AIDirector


class FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return SimpleNamespace(
                id="resp_1",
                output_text="",
                output=[
                    SimpleNamespace(
                        type="function_call",
                        name="list_projects",
                        arguments="{}",
                        call_id="call_1",
                    )
                ],
            )
        return SimpleNamespace(id="resp_2", output_text="The projects are listed.", output=[])


class FakeClient:
    last: "FakeClient | None" = None

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.responses = FakeResponses()
        FakeClient.last = self


@pytest.mark.asyncio
async def test_ai_director_tool_loop_with_mock_openai(monkeypatch):
    import openai

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setattr(openai, "AsyncOpenAI", FakeClient)
    conversation = conversation_manager.create_conversation(title="Mock Director")
    result = await AIDirector().run_turn(conversation["id"], "List the projects.", actor="test")
    assert "The projects are listed" in result["message"]
    assert result["tool_executions"][0]["name"] == "list_projects"
    assert result["tool_executions"][0]["result"]["ok"] is True
    assert FakeClient.last is not None
    assert len(FakeClient.last.responses.calls) == 2
    second = FakeClient.last.responses.calls[1]
    assert second["previous_response_id"] == "resp_1"
    assert second["input"][0]["type"] == "function_call_output"
    stored = conversation_manager.get_conversation(conversation["id"])
    roles = [message["role"] for message in stored["messages"]]
    assert roles == ["user", "assistant"]
    assert stored["tool_executions"][0]["tool_name"] == "list_projects"
