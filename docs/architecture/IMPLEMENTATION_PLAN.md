# Implementation Plan — Completion Status

Status: `[x]` implemented, `[~]` implemented with an external dependency, `[ ]` not complete.

## Phase 0 — Existing system audit
- [x] Backend/frontend/database/ComfyUI/TTS/FFmpeg inventory.
- [x] Retained vs incomplete components identified.
- [x] `EXISTING_SYSTEM_AUDIT.md`, `INTEGRATION_ARCHITECTURE.md`.
- [x] Timestamped backup: `backups/pre-ai-integration-20261109-221344.zip`.

## Phase 1 — Shared application service layer
- [x] `project_service`, `episode_service`, `character_service`, `scene_service`.
- [x] `asset_service`, `approval_service`, `quality_control_service`.
- [x] `dialogue_service`, `audio_service`, `script_service`, `storyboard_service`.
- [x] Structured `ServiceError`/`NotFoundError`/`ConfirmationRequired`/`ConfigurationError`.

## Phase 2 — Database, migrations and job integration
- [x] Versioned SQLite migration runner and `schema_migrations`.
- [x] AI conversation/message/tool-execution/context tables.
- [x] Production runs/tasks/audit logs.
- [x] Character versions, asset versions, scene reviews.
- [x] Approval/memory columns on existing tables.
- [x] Existing `jobs` queue retained as the single generation queue.

## Phase 3 — REST API and production orchestration
- [x] `/api/v1/ai`, `/api/v1/production`, `/api/v1/providers`, `/api/v1/mcp` routes.
- [x] Production state machine and legal transitions.
- [x] Dependency-aware tasks, retries, pause/resume/cancel.
- [x] Restart recovery for production runs.
- [x] Status/queue/logs endpoints.

## Phase 4 — MCP server
- [x] Official MCP SDK, stdio and streamable HTTP.
- [x] Bearer-token authentication, token hashing/revocation.
- [x] Health, structured errors, timeouts, idempotency.
- [x] 58 tools generated from the shared registry.
- [x] Resources and prompts.
- [~] OAuth: resource-server bearer authentication implemented; explicit no-auth local testing mode added for ChatGPT; full OAuth proxy is a deployment step, not claimed as active.
- [x] Verified with a real MCP client (`initialize`, `list_tools`, `call_tool`) and shared state.

## Phase 5 — OpenAI AI Director
- [x] Official OpenAI SDK + Responses API loop.
- [x] Conversation persistence and context snapshots.
- [x] Tool/function calling through the shared registry.
- [x] Confirmation gates for expensive/destructive actions.
- [x] SSE progress streaming and non-streaming endpoint.
- [x] In-app AI Director page.
- [~] Live OpenAI call: implementation complete; this machine has no `OPENAI_API_KEY`/`OPENAI_MODEL`, so live calls are not active. Mocked tool-loop test passes.

## Phase 6 — Shared production memory
- [x] Character memory/approval/version snapshots.
- [x] Project memory JSON.
- [x] Episode script/storyboard/production/continuity fields.
- [x] Approval-aware regeneration and version restore.
- [x] Asset versions.

## Phase 7 — Provider abstraction
- [x] Provider base interfaces and capabilities.
- [x] ComfyUI image provider.
- [x] ComfyUI video provider.
- [x] Kokoro/SAPI audio provider.
- [x] FFmpeg editing provider.
- [x] Optional OpenAI image adapter (disabled without key + cloud opt-in).
- [x] Registry/config/status.
- [~] Cloud video provider: interface exists; no cloud video adapter is implemented or claimed.

## Phase 8 — Scene production and quality control
- [x] Scene generation/regeneration/approval/rejection.
- [x] Deterministic QC checks.
- [x] Human review workflow and stored reports.
- [x] Failed-scene regeneration.
- [~] AI-assisted QC is reserved behind `ENABLE_AI_QC`; deterministic QC is active and no fake objective score is produced.

## Phase 9 — Frontend integration
- [x] AI Director nav/page.
- [x] Chat, tool status, production dashboard, approvals.
- [x] SSE progress updates.
- [x] Provider/GPU availability display.
- [x] One-click ChatGPT connection panel: start tunnel, copy connector URL, auto-secure after 30 minutes, manual disconnect/restore.
- [x] Production build passes.

## Phase 10 — Security and access control
- [x] Environment secrets.
- [x] MCP bearer tokens and token hashes.
- [x] Actor/scope validation and confirmation.
- [x] Rate limiting for AI/production.
- [x] Audit logging/redaction.
- [x] Prompt-injection guard.
- [~] Full OAuth authorization server: not implemented; ChatGPT can use no-auth mode behind a private tunnel for local testing, or an OAuth-aware proxy for ongoing use.

## Phase 11 — Tests
- [x] Workflow transitions.
- [x] Provider registry.
- [x] Tool validation/idempotency/confirmation.
- [x] Shared project/character/episode reads.
- [x] Mocked production task execution.
- [x] Mocked OpenAI Responses tool loop.
- [x] Existing API regression checks performed manually.
- Result: **42 passed**.

## Phase 12 — Documentation and deployment
- [x] Architecture, development, integration and operations docs.
- [x] `.env.example`.
- [x] MCP start scripts.
- [x] ChatGPT connection instructions.
- [x] Remaining limitations documented.
- [x] Git milestone committed (see repository history).

## SDXL image-generation upgrade (post-Phase 12)
- [x] Existing ComfyUI/model/workflow audit; SD 1.5 compatibility preserved.
- [x] Model discovery for checkpoints, VAEs, LoRAs, ControlNet and upscalers.
- [x] Architecture detection from safetensors metadata, filename and size, with confidence/source.
- [x] Model Studio UI: active model, GPU/VRAM, compatibility, missing dependencies, checkpoint/VAE/LoRA/workflow/preset configuration.
- [x] Local model-path configuration remains available in Settings; no automatic downloads.
- [x] SDXL workflow templates: txt2img, img2img, turnaround, expression, pose, background.
- [x] Tiled VAE, batch size 1, SDXL dimension guard and 6 GB-safe presets.
- [x] Optional VAE and LoRA injection; model availability validation.
- [x] Character-specific model overrides stored in character memory; no schema migration.
- [x] Turnaround/expression/pose sheet orchestration with approved-reference gate.
- [x] Model approval action; no auto-approval.
- [x] SD 1.5 live regression passed; SDXL live generation verified with DreamShaper XL 1.0.
- [x] `docs/integration/SDXL_MODEL_GUIDE.md`.
- [x] **158 passed** automated tests.
- [x] SDXL live character/background generation and VRAM measurement: completed on the 6 GB RTX 4050 with low-VRAM, tiled VAE and a 1.25 MP budget.

## Production Studio extension
- [x] Cross-department production registry with readiness and candidate models.
- [x] Resource manager: GPU/RAM/queue status, free-VRAM action, workflow estimates.
- [x] Priority-aware queue and job tracking migration v2 (resource class, model, estimated/actual seconds, peak VRAM, priority).
- [x] Local Ollama LLM integration for story/script generation and continuity warnings.
- [x] Local Ollama Qwen2.5-VL visual review with structured JSON and mandatory human review.
- [x] Shot plan with shot-level cast/background/camera/dialogue/audio and GPU-time estimates.
- [x] Production report with counts, statuses and resource usage.
- [x] Lip-sync viseme cue layer and migration v3; independently editable per dialogue line.
- [x] 1080p H.264/AAC/subtitle export verified.
- [x] Live tests: Wan image-to-video, 4× upscale, Kokoro dialogue, local SFX/music, SD 1.5 image, LLM/VLM.
- [x] **158 passed** automated tests.
- [x] SDXL generation: verified with DreamShaper XL 1.0.
- [ ] Image editing with Qwen-Image-Edit/FLUX Kontext: blocked by missing local weights (SDXL img2img and masked inpainting are available).
- [x] IP-Adapter/SDXL ControlNet pose control: installed and smoke-tested.
- [x] ASR: faster-whisper small verified on CPU int8.
- [ ] Lip-sync mouth rendering: blocked by missing Wav2Lip/SadTalker/Rhubarb or rig pipeline.
- [ ] LTX/Hunyuan/CogVideoX and AudioGen/MusicGen/ACE-Step/Stable Audio: blocked by missing weights.
