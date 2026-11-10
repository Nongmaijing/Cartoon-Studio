# MCP Architecture

## Transport

- `stdio` for local process clients.
- `streamable-http` on port `8020` at `/mcp` for remote/custom connectors.
- Health: `GET http://127.0.0.1:8020/health`.

## Authentication

Two modes are supported:

- `MCP_AUTH_MODE=bearer` (default):
  - FastMCP `TokenVerifier` validates bearer tokens.
  - Token sources:
    1. `MCP_BEARER_TOKEN` environment variable.
    2. Hashed tokens in `mcp_tokens`, created by `POST /api/v1/mcp/tokens`.
  - The raw token is shown only once at creation.
  - Tokens have scopes (`production` by default) and can be revoked.
  - FastMCP exposes resource metadata for protected MCP endpoints.
- `MCP_AUTH_MODE=none` (explicit local-testing mode):
  - Requires `MCP_ALLOW_UNAUTHENTICATED=true`; the server refuses to start otherwise.
  - Used for ChatGPT "No authentication" connectors behind a private tunnel.
  - Any client that can reach the endpoint can control production. Restore bearer mode afterwards.

Transport host/origin validation:
- `MCP_PUBLIC_URL` host is automatically allowed.
- `MCP_ALLOWED_HOSTS` and `MCP_ALLOWED_ORIGINS` add comma-separated tunnel values.
- Unknown Host headers are rejected with HTTP 421.

### OAuth status

The server is a **resource server**. It does not implement a full OAuth authorization server. ChatGPT custom connectors support OAuth or No authentication, but not a static bearer token. Use `MCP_AUTH_MODE=none` behind a private tunnel for local testing, or place an OAuth-aware proxy/identity provider in front of `/mcp` for ongoing use. Do not claim OAuth is active unless that proxy is configured.

## Tool model

- The studio profile exposes 56 tools generated from the shared `ToolRegistry` schema; the separate OpenCode profile exposes 4 bridge tools.
- Each tool calls the same service used by the AI Director and REST API.
- Tools return structured JSON.
- Expensive/destructive tools require `confirm=true`.
- Tool execution is audited in `ai_tool_executions` and `audit_logs`.
- Optional `idempotency_key` is supported for retry-safe operations.

## Resources

- `cartoon://projects`
- `cartoon://projects/{project_id}`
- `cartoon://episodes/{episode_id}`
- `cartoon://production/{run_id}`

## Prompts

- `plan_episode`
- `review_scene`

## Safety

- No raw filesystem, shell, or ComfyUI graph execution.
- Project/entity validation in services.
- Secret redaction in tool responses.
- Prompt-injection guard: retrieved content is data, not authority.
- Rate limiting applies to AI/production REST paths; MCP tool timeouts are enforced by the registry.

## Start

```powershell
cd D:\bro\CartoonStudio
.\scripts\start_mcp.ps1
```

Or:

```powershell
cd D:\bro\CartoonStudio\backend
.\.venv\Scripts\python.exe run_mcp.py --transport streamable-http --host 127.0.0.1 --port 8020
```

## Test

See `docs/integration/CHATGPT_CONNECTION.md` for a Python MCP client test with a bearer token.
