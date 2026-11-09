# Cartoon Studio — System Architecture

## Services and ports

| Service | Port | Notes |
|---|---:|---|
| FastAPI backend + production build | 8010 | Existing app, extended with `/api/v1` |
| Vite dev frontend | 5173 | Optional; proxies `/api` to 8010 |
| MCP server | 8020 | Separate process, bearer-token protected |
| ComfyUI | 8188 | Existing local engine |

## Runtime components

```
React UI (existing pages + AI Director)
        |
        v
FastAPI routers
  /api/*        legacy, preserved
  /api/v1/*     AI, production, providers, MCP support, health
        |
        v
Shared service layer
  project_service, episode_service, character_service, scene_service
  dialogue_service, audio_service, script_service, storyboard_service
  asset_service, approval_service, quality_control_service
        |
        v
Production orchestrator
  workflow_engine, production_orchestrator
        |
        v
Provider registry
  comfyui image/video, kokoro audio, ffmpeg editing, optional OpenAI image
        |
        +--> SQLite (data/cartoon_studio.db)
        +--> ComfyUI 8188
        +--> Kokoro/SAPI
        +--> FFmpeg
        +--> outputs/
```

The MCP server and AI Director call the **same** `ToolRegistry`, which calls the shared services. Neither interface has its own production engine.

## Existing functionality preserved

- Existing `/api` routers and React pages.
- Existing `jobs` table and single-worker ComfyUI queue.
- Existing workflows, mappings, model readiness and asset pipeline.
- Existing Kokoro/SAPI TTS.
- Existing FFmpeg episode export and subtitle generation.

## New persistence

- `schema_migrations`
- `ai_conversations`, `ai_messages`, `ai_tool_executions`, `ai_context_snapshots`
- `production_runs`, `production_tasks`, `audit_logs`
- `provider_configs`
- `character_versions`, `asset_versions`, `scene_reviews`
- `mcp_tokens`
- approval/memory columns on `projects`, `characters`, `scenes`, `episodes`, `assets`

## Hardware model

- RTX 4050 Laptop, ~6 GB VRAM, ~32 GB RAM.
- One ComfyUI generation job at a time.
- TTS and FFmpeg are CPU-side and serialized separately.
- Cloud image generation is opt-in only (`ALLOW_CLOUD_GENERATION=true`).
- The orchestrator queues dependent work and does not run heavy local jobs concurrently.

## Security boundary

- Local UI is unauthenticated by design.
- MCP HTTP requires a bearer token by default; explicit no-auth mode exists only for local ChatGPT testing behind a private tunnel.
- AI Director is project-scoped and uses server-side OpenAI credentials.
- No MCP tool exposes the filesystem or raw ComfyUI graphs.
- Expensive/destructive tools require `confirm=true`.
- All mutating tool calls are audited.
