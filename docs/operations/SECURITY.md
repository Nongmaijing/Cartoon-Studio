# Security

## Actors

| Actor | Authentication | Scope |
|---|---|---|
| Local UI user | Local app (no login) | Full local access |
| AI Director | Server-side OpenAI key + conversation | Project-scoped production tools |
| MCP client | Bearer token | Production scope, confirmation gates |

## MCP authentication

- `MCP_BEARER_TOKEN` environment token, or
- Hashed token in `mcp_tokens`, created by `POST /api/v1/mcp/tokens`.
- Raw tokens are shown once.
- Tokens can be revoked.
- FastMCP's `TokenVerifier` validates the bearer token and scopes.
- `MCP_AUTH_MODE=none` is an explicit local-testing mode and requires `MCP_ALLOW_UNAUTHENTICATED=true`. It is unsafe on a public endpoint; use a temporary private tunnel and restore bearer mode afterwards.
- The AI Director UI exposes a one-click ChatGPT tunnel (`/api/v1/mcp/tunnel/*`). It starts a Cloudflare quick tunnel, switches MCP to no-auth mode, and auto-restores bearer auth after the selected session length (30 minutes to 8 hours; default 30 minutes) or when the user clicks **Disconnect & secure**. **Never auto-stop** disables the timer but is strongly discouraged: the no-auth URL remains publicly reachable until manually disconnected or the process stops. The tunnel URL is public and unauthenticated while active; treat it as a temporary secret and do not share it.
- The server is a resource server; it does not implement a full OAuth authorization server. ChatGPT connectors support OAuth or No authentication, not static bearer tokens. Use no-auth mode behind a private tunnel for local testing, or an OAuth-aware proxy for ongoing use.

## Secrets

- `OPENAI_API_KEY`, `MCP_BEARER_TOKEN`, database paths and provider credentials come from `.env`/environment.
- `.env` is Git-ignored.
- Tool responses redact keys containing `api_key`, `authorization`, `password`, `secret`, `bearer`.
- MCP token hashes are stored, not raw tokens.

## Authorization

- Tools validate project/entity ownership through services.
- MCP tokens carry scopes (`production` by default).
- Destructive/expensive tools require `confirm=true`.
- Confirmation is enforced server-side in the tool registry, not only in the UI.

## Prompt injection

- Retrieved project text, asset metadata and external provider responses are treated as data.
- They are never treated as authorization to execute tools.
- The AI Director system prompt explicitly instructs the model to follow this rule.
- The tool registry enforces confirmations independently of model text.

## Rate limiting

- AI message and production-start endpoints use an in-process per-key rate limiter.
- Configure with `security.rate_limit_per_minute`.
- MCP tool execution has per-tool timeouts.

## Audit

- Mutating tool calls write to `ai_tool_executions`.
- Service mutations write to `audit_logs`.
- Production task transitions are persisted in `production_tasks`.

## Filesystem and ComfyUI

- No MCP tool exposes arbitrary filesystem access.
- Asset delivery is path-traversal guarded.
- No raw ComfyUI graph execution or filesystem access is exposed.
- Absolute paths are not returned in normal tool results; project-relative paths and `/api/assets/{id}/file` URLs are used.

## Cloud privacy

- Cloud image generation is disabled by default.
- Enable only with `ALLOW_CLOUD_GENERATION=true`.
- Private assets are not uploaded automatically.
- Review provider terms and licensing before commercial use.
