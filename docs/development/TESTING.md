# Testing

## Run

```powershell
cd D:\bro\CartoonStudio\backend
.\.venv\Scripts\python.exe -m pytest -q
```

Current result: **25 passed**.

## Test files

| File | Covers |
|---|---|
| `tests/test_workflow_engine.py` | Legal/illegal production transitions, pause/resume, stage order |
| `tests/test_provider_registry.py` | Provider registry, availability, cloud opt-in |
| `tests/test_tool_registry.py` | Unknown tools, validation, shared reads, idempotency, confirmation gates, manual tool endpoint argument handling |
| `tests/test_production_mock.py` | Mocked scene production task execution and run completion |
| `tests/test_ai_director_mock.py` | Mocked OpenAI Responses tool loop, persistence, previous_response_id |
| `tests/test_mcp_config.py` | Transport host/origin allowlist, no-auth opt-in guard, invalid auth mode rejection |
| `tests/test_mcp_tunnel.py` | Cloudflared URL parsing, confirmation gate, inactive tunnel status shape |

## Mocking policy

- Tests never call ComfyUI or OpenAI.
- The production test mocks image generation and job waiting.
- The AI Director test injects a fake `AsyncOpenAI` client and asserts the function-call loop.
- A temporary SQLite database is used per test.

## Manual integration checks

1. Backend health: `/api/health`, `/api/v1/health`.
2. MCP health: `http://127.0.0.1:8020/health`.
3. MCP bearer-token client: `list_tools` and `list_projects`.
4. Shared state: create a project/character through MCP and read it through `/api`.
5. Reverse direction: create a scene through `/api` and read it through MCP.
6. Confirmation gate: `start_production` without `confirm=true` returns `confirmation_required`.
7. AI Director without key: returns a clear 503.
