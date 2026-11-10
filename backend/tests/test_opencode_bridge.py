from __future__ import annotations

import pytest

from app.ai import opencode_client as oc


def test_parse_model_splits_provider_and_id():
    assert oc.parse_model("opencode-go/beam-free") == {
        "providerID": "opencode-go",
        "id": "beam-free",
    }
    assert oc.parse_model("ollama/hf.co/Qwen/Qwen3-VL-8B-Instruct-GGUF:Q4_K_M") == {
        "providerID": "ollama",
        "id": "hf.co/Qwen/Qwen3-VL-8B-Instruct-GGUF:Q4_K_M",
    }
    assert oc.parse_model("") is None
    assert oc.parse_model("no-provider") is None


def test_assistant_content_extraction():
    message = {
        "type": "assistant",
        "content": [
            {"type": "reasoning", "text": "hidden"},
            {"type": "text", "text": "first"},
            {"type": "tool", "name": "bash"},
            {"type": "text", "text": "second"},
        ],
    }
    assert oc._assistant_text(message) == "first\nsecond"
    assert oc._tool_names(message) == ["bash"]


@pytest.fixture
def fake_session(monkeypatch):
    def _install(messages, session_time, permissions=None):
        monkeypatch.setattr(oc, "get_session", lambda session_id: {"id": session_id, "title": "t", "time": session_time, "location": {"directory": "D:\\bro"}})
        monkeypatch.setattr(oc, "list_messages", lambda session_id, limit=60: messages)
        monkeypatch.setattr(oc, "list_permissions", lambda session_id: permissions or [])

    return _install


def test_task_status_completed(fake_session):
    fake_session(
        [
            {"type": "assistant", "finish": "stop", "content": [{"type": "text", "text": "done"}]},
            {"type": "user", "text": "go"},
        ],
        {"busy": 100, "idle": 200},
    )
    result = oc.task_status("ses_test")
    assert result["status"] == "completed"
    assert result["text"] == "done"


def test_task_status_stays_running_while_busy(fake_session):
    fake_session(
        [
            {"type": "assistant", "finish": "tool-calls", "content": [{"type": "tool", "name": "bash"}]},
            {"type": "user", "text": "go"},
        ],
        {"busy": 200, "idle": 100},
    )
    result = oc.task_status("ses_test")
    assert result["status"] == "running"


def test_task_status_permission_required(fake_session):
    fake_session(
        [{"type": "user", "text": "go"}],
        {"busy": 200, "idle": 100},
        permissions=[{"id": "perm_1", "action": "shell"}],
    )
    result = oc.task_status("ses_test")
    assert result["status"] == "waiting_for_permission"
    assert result["pending_permissions"][0]["id"] == "perm_1"


def test_task_status_failed(fake_session):
    fake_session(
        [
            {
                "type": "assistant",
                "finish": "error",
                "error": {"message": "quota"},
                "content": [],
            },
            {"type": "user", "text": "go"},
        ],
        {"busy": 100, "idle": 200},
    )
    result = oc.task_status("ses_test")
    assert result["status"] == "failed"
    assert result["error"] == "quota"


def test_start_task_reuses_existing_session(monkeypatch):
    monkeypatch.setattr(oc, "get_session", lambda session_id: {"id": session_id, "title": "existing", "location": {"directory": "D:\\bro"}})
    calls = []

    def fake_api(method, path, **kwargs):
        calls.append((method, path, kwargs.get("body")))
        return {"data": {"id": "msg_1"}}

    monkeypatch.setattr(oc, "_api", fake_api)
    result = oc.start_task("hello", session_id="ses_existing")
    assert result["session_id"] == "ses_existing"
    assert result["message_id"] == "msg_1"
    assert calls[0][1] == "/api/session/ses_existing/prompt"
