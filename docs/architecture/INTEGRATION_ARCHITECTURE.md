# Integration Architecture

## 1. Goals

Add two control surfaces without replacing the working application:

1. **External ChatGPT via MCP**
2. **In-app AI Director via OpenAI Responses API**

Both must use the same service layer, database, job queue, providers and assets.

## 2. High-level architecture

```
ChatGPT custom connector
        |
        v
MCP server (official MCP SDK, separate port)
        |
        v
Shared tool registry
        |
        v
Shared application services
        |
        v
Production orchestrator
        |
        v
Provider registry
  +--> ComfyUI image provider
  +--> ComfyUI video provider
  +--> Kokoro/SAPI audio provider
  +--> FFmpeg editing provider
  +--> optional cloud image provider (opt-in)
        |
        v
SQLite + outputs/ assets

Cartoon Studio UI
  +--> existing pages
  +--> AI Director page
        |
        v
FastAPI `/api/v1/ai/director`
        |
        v
OpenAI Responses API (tool calling)
        |
        v
Shared tool registry -> same services
```

## 3. Shared application services

The new layer wraps and reuses the existing implementation:

- `project_service.py` — project CRUD and summaries.
- `episode_service.py` — episodes, timeline, export.
- `character_service.py` — characters, references, canonical identity, approvals.
- `scene_service.py` — scenes, scene generation, approvals.
- `script_service.py` — story/script generation and storage.
- `storyboard_service.py` — storyboard → scenes.
- `production_service.py` — production runs, tasks, pause/resume/cancel.
- `asset_service.py` — asset lookup, versions, safe delivery.
- `approval_service.py` — human approvals and version history.
- `quality_control_service.py` — deterministic checks plus optional AI review.

Existing routers remain the public legacy API. New AI/MCP/production endpoints call the shared services. Where practical, routers are refactored to call the services, but working behaviour is preserved.

## 4. Provider abstraction

`providers/base.py` defines:

- `ProviderInfo` (name, type, capabilities, constraints, resource estimate, availability, config).
- `ImageProvider`, `VideoProvider`, `AudioProvider`, `EditingProvider` interfaces.
- Standard job methods: `get_job_status`, `cancel_job`.

Implementations:

- `providers/comfyui_image.py` — wraps `submit_image`, `jobs.get_job`, `jobs.runner.cancel`.
- `providers/comfyui_video.py` — wraps `submit_video` and Wan workflows.
- `providers/kokoro_audio.py` — wraps `tts.synthesize`.
- `providers/ffmpeg_editing.py` — wraps `episode_export`.
- `providers/openai_image.py` — optional cloud image provider, disabled unless `OPENAI_API_KEY` and `ALLOW_CLOUD_GENERATION=true`.

The provider registry reads defaults and `provider_configs` from SQLite. The orchestrator only uses the registry, never a concrete provider.

## 5. Production orchestration

Persistent tables:

- `production_runs` — episode-level run state and plan.
- `production_tasks` — stage/scene tasks with job IDs and retry counters.
- `audit_logs` — actor, action, entity and detail.

States:

`DRAFT → PLANNING → SCRIPT_GENERATION → SCRIPT_REVIEW → STORYBOARD_GENERATION → STORYBOARD_REVIEW → CHARACTER_PREPARATION → SCENE_GENERATION → SCENE_REVIEW → ANIMATION → ANIMATION_REVIEW → AUDIO_GENERATION → FINAL_EDITING → FINAL_REVIEW → COMPLETED`

Failure/pause branches: `FAILED`, `PAUSED`, `CANCELLED`.

The orchestrator:

- validates legal transitions
- creates independent tasks
- respects approvals and dependencies
- submits generation through providers
- records job IDs
- retries with backoff
- persists every task
- resumes pending runs on startup
- emits progress via the existing job polling/SSE surface

## 6. AI Director

`ai/openai_director.py`:

- uses the official OpenAI Python SDK
- calls the **Responses API**
- model ID comes from `OPENAI_MODEL`
- tool definitions come from the shared tool registry
- conversation history and provider response IDs are persisted
- tool calls execute shared services
- expensive/destructive tools require explicit confirmation
- the assistant never claims completion until a service/backend confirms it

Tables:

- `ai_conversations`
- `ai_messages`
- `ai_tool_executions`
- `ai_context_snapshots`

Endpoints:

- `POST /api/v1/ai/conversations`
- `GET /api/v1/ai/conversations`
- `GET /api/v1/ai/conversations/{id}`
- `POST /api/v1/ai/conversations/{id}/messages`
- `POST /api/v1/ai/conversations/{id}/messages/stream`
- `GET /api/v1/ai/tool-executions`

## 7. MCP server

`mcp/server.py` uses the official MCP Python SDK.

Transports:

- `stdio` for local testing
- `streamable-http` on a separate port for remote connections

Security:

- `MCP_BEARER_TOKEN` is required for HTTP mode.
- Requests without a valid token are rejected.
- Tools use the same registry and permission checks as the AI Director.
- No raw filesystem or ComfyUI access is exposed.
- Destructive operations require `confirm=true`.
- Responses redact secrets and internal paths.
- `MCP_PUBLIC_URL` is used in discovery/documentation; a tunnel (Cloudflare Tunnel, ngrok, Tailscale Funnel) provides HTTPS.

OAuth:

- A minimal token verifier is implemented for bearer tokens.
- ChatGPT connector account-side OAuth requirements vary by plan/connector type.
- If the connector requires OAuth, configure the connector to use the bearer token or place an OAuth reverse proxy in front of the MCP server.
- The server exposes health and metadata; full OAuth authorization-server implementation is documented as an optional extension, not claimed as active.

## 8. Shared memory

Existing tables are extended with JSON memory and approval fields. New version tables preserve history:

- `characters` gains `memory_json`, `approval_status`, `approved_at`.
- `scenes` gains `approval_status`, `approved_at`, `quality_json`.
- `episodes` gains `production_state`, `production_json`, `approved_at`.
- `character_versions`, `asset_versions`, `scene_reviews`.

Approved references are never overwritten. Regeneration creates new assets/versions.

## 9. Frontend

Add a new **AI Director** page:

- project and episode selectors
- conversation history
- chat composer
- streaming/progress events
- tool execution list
- production run status and tasks
- scene approval/rejection controls
- provider/GPU availability
- job links

The existing pages remain unchanged except for navigation and any approval controls added to scene/episode detail.

## 10. Security model

Actors:

- `user` — local UI, full access
- `ai_director` — project-scoped production access
- `mcp` — token-scoped access

Controls:

- API keys only from environment/config, never returned.
- Bearer token for MCP HTTP.
- Input validation via Pydantic schemas.
- Project/entity ownership validation in services.
- Rate limiting on AI/MCP production endpoints.
- Audit logging for all mutating tool executions.
- Confirmation required for destructive/expensive operations.
- Prompt-injection guard: retrieved text/assets are data, not instructions or authorization.
- No arbitrary shell, filesystem, or ComfyUI graph execution through MCP.

## 11. Hardware scheduling

- Existing single-worker ComfyUI queue is retained.
- Provider registry reports GPU/VRAM and local availability.
- Cloud image generation is disabled unless explicitly enabled.
- Video generation locally defaults to the existing Wan queue.
- CPU TTS and FFmpeg exports remain serialized separately.
- Production orchestration queues dependent jobs instead of running heavy jobs concurrently.
