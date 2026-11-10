from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from typing import Any

DEFAULT_DIRECTORY = os.environ.get("OPENCODE_BRIDGE_DIR", r"D:\bro")
DEFAULT_MODEL = os.environ.get("OPENCODE_BRIDGE_MODEL", "opencode-go/beam-free")
DEFAULT_TIMEOUT = float(os.environ.get("OPENCODE_BRIDGE_TIMEOUT", "180"))
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class OpenCodeError(RuntimeError):
    pass


def _cli_path() -> str:
    candidates = [
        os.environ.get("OPENCODE_CLI", ""),
        shutil.which("opencode.exe") or "",
        os.path.expanduser(r"~\AppData\Roaming\npm\node_modules\@opencode\cli\bin\opencode.exe"),
        shutil.which("opencode.cmd") or "",
        shutil.which("opencode") or "",
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    raise OpenCodeError("OpenCode CLI not found. Set OPENCODE_CLI to the opencode executable.")


def parse_model(value: str | None) -> dict[str, str] | None:
    if not value:
        return None
    provider, _, model = value.partition("/")
    if not model:
        return None
    return {"providerID": provider, "id": model}


def _api(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    cmd = [_cli_path(), "api", method, path]
    if body is not None:
        cmd += ["--data", json.dumps(body)]
    for key, value in (params or {}).items():
        cmd += ["--param", f"{key}={value}"]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise OpenCodeError(f"OpenCode API timed out after {timeout:.0f}s: {method} {path}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[:800]
        raise OpenCodeError(f"OpenCode API failed ({method} {path}): {detail}")
    text = (completed.stdout or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise OpenCodeError(f"OpenCode API returned non-JSON output: {text[:400]}") from exc


def _payload(response: Any) -> Any:
    if isinstance(response, dict) and "data" in response:
        return response["data"]
    return response


def list_sessions(limit: int = 10) -> list[dict[str, Any]]:
    response = _api("get", "/api/session", params={"limit": max(1, min(limit, 50)), "order": "desc"})
    data = _payload(response)
    if isinstance(data, dict):
        data = data.get("data")
    return list(data or [])[: max(1, min(limit, 50))]


def get_session(session_id: str) -> dict[str, Any]:
    data = _payload(_api("get", f"/api/session/{session_id}"))
    if not isinstance(data, dict):
        raise OpenCodeError("Unexpected session response from OpenCode.")
    return data


def create_session(
    *,
    title: str,
    directory: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": title or "ChatGPT / OpenCode task",
        "location": {"directory": directory or DEFAULT_DIRECTORY},
    }
    parsed = parse_model(model if model is not None else DEFAULT_MODEL)
    if parsed:
        body["model"] = parsed
    data = _payload(_api("post", "/api/session", body=body))
    if not isinstance(data, dict) or not data.get("id"):
        raise OpenCodeError("OpenCode did not return a session id.")
    return data


def list_messages(session_id: str, limit: int = 30) -> list[dict[str, Any]]:
    response = _api(
        "get",
        f"/api/session/{session_id}/message",
        params={"limit": max(1, min(limit, 100)), "order": "desc"},
    )
    data = _payload(response)
    if isinstance(data, dict):
        data = data.get("data")
    return list(data or [])


def list_permissions(session_id: str) -> list[dict[str, Any]]:
    try:
        data = _payload(_api("get", f"/api/session/{session_id}/permission"))
    except OpenCodeError:
        return []
    if isinstance(data, dict):
        data = data.get("data")
    return list(data or [])


def reply_permission(session_id: str, request_id: str, decision: str) -> dict[str, Any]:
    if decision not in ("once", "always", "reject"):
        raise OpenCodeError("decision must be once, always or reject.")
    data = _payload(
        _api(
            "post",
            f"/api/session/{session_id}/permission/{request_id}/reply",
            body={"decision": decision},
        )
    )
    return data if isinstance(data, dict) else {"ok": True}


def start_task(
    message: str,
    *,
    session_id: str | None = None,
    title: str = "",
    model: str | None = None,
    directory: str | None = None,
) -> dict[str, Any]:
    if session_id:
        session = get_session(session_id)
    else:
        session = create_session(title=title, directory=directory, model=model)
    session_id = str(session["id"])
    prompt = _payload(_api("post", f"/api/session/{session_id}/prompt", body={"text": message}))
    return {
        "session_id": session_id,
        "title": session.get("title") or "",
        "message_id": (prompt or {}).get("id") if isinstance(prompt, dict) else None,
        "status": "running",
        "model": session.get("model"),
        "directory": (session.get("location") or {}).get("directory"),
    }


def _assistant_text(message: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in message.get("content") or []:
        if item.get("type") == "text" and item.get("text"):
            parts.append(str(item["text"]))
    return "\n".join(parts).strip()


def _tool_names(message: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in message.get("content") or []:
        if item.get("type") == "tool" and item.get("name"):
            names.append(str(item["name"]))
    return names


def task_status(session_id: str) -> dict[str, Any]:
    session = get_session(session_id)
    messages = list_messages(session_id, limit=60)
    permissions = list_permissions(session_id)
    latest_user_index = next(
        (index for index, message in enumerate(messages) if message.get("type") == "user"),
        None,
    )
    relevant = messages[:latest_user_index] if latest_user_index is not None else messages
    assistants = [message for message in relevant if message.get("type") == "assistant"]
    latest = assistants[0] if assistants else None
    text = "\n\n".join(filter(None, (_assistant_text(item) for item in reversed(assistants)))).strip()
    tools: list[str] = []
    for item in reversed(assistants):
        tools.extend(_tool_names(item))

    status = "running"
    error = None
    session_time = session.get("time") or {}
    busy = session_time.get("busy")
    idle = session_time.get("idle")
    active = busy is not None and (idle is None or idle < busy)
    if permissions:
        status = "waiting_for_permission"
    elif active:
        status = "running"
    elif latest is not None:
        if latest.get("finish") == "error" or latest.get("error"):
            status = "failed"
            error = (latest.get("error") or {}).get("message") or "OpenCode task failed."
        elif latest.get("finish"):
            status = "completed"
    elif messages and messages[0].get("type") == "idle":
        status = "completed" if messages[0].get("outcome") == "succeeded" else "failed"
        if status == "failed":
            error = (messages[0].get("error") or {}).get("message")

    return {
        "session_id": session_id,
        "title": session.get("title") or "",
        "status": status,
        "text": text,
        "tools": list(dict.fromkeys(tools)),
        "message_count": len(messages),
        "pending_permissions": permissions,
        "error": error,
        "directory": (session.get("location") or {}).get("directory"),
    }


def wait_task(session_id: str, timeout_seconds: float = 60.0) -> dict[str, Any]:
    deadline = time.time() + max(0.0, min(timeout_seconds, 300.0))
    result = task_status(session_id)
    while result["status"] == "running" and time.time() < deadline:
        time.sleep(1.5)
        result = task_status(session_id)
    if result["status"] == "running":
        result["timed_out"] = True
    return result


def ask(
    message: str,
    *,
    session_id: str | None = None,
    title: str = "",
    model: str | None = None,
    wait_seconds: int = 0,
) -> dict[str, Any]:
    started = start_task(message, session_id=session_id, title=title, model=model)
    if wait_seconds > 0:
        result = wait_task(started["session_id"], float(wait_seconds))
        result.update({"started": started, "timed_out": result.get("timed_out", False)})
        return result
    return started
