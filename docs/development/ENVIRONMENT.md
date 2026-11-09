# Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | For AI Director/story generation | Server-side OpenAI key. Never returned by APIs. |
| `OPENAI_MODEL` | For AI Director/story generation | Model ID available to your account. Validated at request time. |
| `OPENAI_BASE_URL` | No | Defaults to `https://api.openai.com/v1`. |
| `OPENAI_MAX_TOOL_ROUNDS` | No | Tool-call loop limit, default 8. |
| `OPENAI_TIMEOUT_SECONDS` | No | Timeout configuration value. |
| `CARTOON_STUDIO_BASE_URL` | No | Base URL for internal/docs references. |
| `COMFYUI_BASE_URL` | No | Documented override; runtime uses `config/config.json` `comfyui.server_url`. |
| `CARTOON_STUDIO_DB_PATH` | No | Direct SQLite path override (useful for tests). |
| `DATABASE_URL` | No | Supports `sqlite:///D:/path/cartoon_studio.db`. |
| `REDIS_URL` | No | Reserved. The existing SQLite queue is retained; no second queue is introduced. |
| `MCP_ENABLED` | No | Informational flag for MCP status. |
| `MCP_TRANSPORT` | No | `streamable-http` (default) or `stdio`. |
| `MCP_HOST` / `MCP_PORT` | No | Default `127.0.0.1:8020`. |
| `MCP_PUBLIC_URL` | For remote connectors | HTTPS tunnel URL used in MCP/OAuth metadata. |
| `MCP_BEARER_TOKEN` | For MCP HTTP | Bearer token accepted by the MCP server. |
| `MCP_AUTH_MODE` | No | `bearer` (default) or `none` (local ChatGPT testing only). |
| `MCP_ALLOW_UNAUTHENTICATED` | Required for `none` | Safety guard; must be `true` or the MCP server refuses to start. |
| `MCP_ALLOWED_HOSTS` | For tunnels | Comma-separated extra Host header values accepted by the MCP transport. |
| `MCP_ALLOWED_ORIGINS` | For tunnels | Comma-separated extra Origin values accepted by the MCP transport. |
| `ALLOW_CLOUD_GENERATION` | No | Enables opt-in cloud image provider. Default false. |
| `OPENAI_IMAGE_MODEL` | No | Cloud image model, default `gpt-image-1` in the adapter example. |
| `ENABLE_AI_QC` | No | Reserved for AI-assisted QC; deterministic QC works without it. |

## Secrets

- Secrets are read from the environment/`.env`.
- `.env` is ignored by Git.
- MCP tokens are stored hashed in `mcp_tokens`.
- API responses redact keys containing `api_key`, `authorization`, `password`, `secret`, `bearer`.

## Database path

`config/config.json` remains the default source. `CARTOON_STUDIO_DB_PATH` and `sqlite:///` URLs are optional overrides.

## Image model configuration

Selected checkpoints, VAE, LoRA, workflows and 6 GB presets are stored under the `models` key in `config/config.json`. Use **Model Studio** (`/models`) to edit them. This is separate from ComfyUI’s own model files; Cartoon Studio never downloads or modifies model weights.
