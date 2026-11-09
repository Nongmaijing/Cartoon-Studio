# Existing System Audit

Date: 2026-11-09
Repository: `D:\bro\CartoonStudio`

## 1. Executive summary

Cartoon Studio is a working local production application with:

- a FastAPI backend on port `8010`
- a React + TypeScript + Vite frontend on port `5173`
- SQLite persistence in `data/cartoon_studio.db`
- ComfyUI on port `8188` as the image/video engine
- DreamShaper 8 + 4x-UltraSharp for production image generation
- Wan 2.2 TI2V-5B for text-to-video / image-to-video
- Kokoro-82M for neural TTS, with Windows SAPI fallback
- FFmpeg for 1280×720 MP4 assembly and subtitles
- a single-worker generation queue and a separate single-worker export lock

There is no authentication, AI Director, MCP server, provider registry, production state machine, approval/versioning system, or automated test suite yet. Those are the integration targets.

## 2. Backend

Framework: **FastAPI**, served by Uvicorn.

Entry point: `backend/app/main.py`

- `APP_VERSION = "0.6.2"`
- Lifespan: loads config, creates directories, runs `init_db()`, marks interrupted exports, discovers ComfyUI, starts the generation queue worker.
- CORS allows local Vite origins.
- Routers included under `/api`.

### Routers

| Router | Prefix | Responsibility |
|---|---|---|
| `dashboard.py` | `/api/dashboard` | Counts, ComfyUI status, system stats, current jobs, recent assets |
| `projects.py` | `/api/projects` | Project CRUD, archive, duplicate (characters, backgrounds, scenes, cast, dialogue, episodes, media, outputs) |
| `characters.py` | `/api/characters` | Character profiles, canonical identity, voice assignment, media, generation |
| `backgrounds.py` | `/api/backgrounds` | Background profiles, media, image generation |
| `scenes.py` | `/api/scenes` | Scene CRUD, cast, media, references, keyframe/video generation |
| `animation.py` | `/api/animation` | Wan 2.2 t2v/i2v generation and engine readiness |
| `voice.py` | `/api/voice` | TTS engine discovery and preview |
| `dialogue.py` | `/api/dialogue` | Scene dialogue line CRUD and audio generation |
| `episodes.py` | `/api/episodes` | Episode CRUD, timeline save, async FFmpeg export, MP4/SRT delivery |
| `workflows.py` | `/api/workflows` | Workflow discovery, validation, import/export |
| `generate.py` | `/api/generate` | Generic workflow submission and job endpoints |
| `assets.py` | `/api/assets` | Asset metadata, file delivery, 4× upscale |
| `settings.py` | `/api/settings` | Config read/update |
| `comfy.py` | `/api/comfy` | ComfyUI test, discovery, models, object info, queue |
| `voice.py` | `/api/voice` | Kokoro/SAPI/Piper/Coqui/eSpeak detection, WAV preview |

### Services

| Service | Responsibility |
|---|---|
| `services/generation.py` | Workflow selection, `submit_image`, `submit_video`, ComfyUI image upload |
| `services/jobs.py` | SQLite-backed single-worker queue, WebSocket progress, output download, asset/link creation, cancellation |
| `services/assets.py` | Asset listing/lookup, safe file resolution, generated-file storage, unique filenames |
| `services/media.py` | `media_links` linking, role counts, cover selection |
| `services/scenes.py` | Scene decoration, cast, background, counts |
| `services/creative.py` | Character/background/scene prompt composition, negatives, cartoon style |
| `services/dialogue.py` | Dialogue lines, script import, TTS generation, scene audio links |
| `services/tts.py` | Kokoro, Windows SAPI, Piper, Coqui, eSpeak discovery and synthesis |
| `services/engines.py` | Wan/AnimateDiff/IPAdapter/ControlNet readiness and model parsing |
| `services/conditioning.py` | ControlNet readiness and image mode selection |
| `services/workflow_checks.py` | Workflow readiness, model status, missing node classes |
| `services/episodes.py` | Episode timeline CRUD/validation/decoration, output resolution |
| `services/episode_export.py` | FFmpeg segment rendering, concat, audio mix, subtitles, progress, cancellation |
| `services/stats.py` | System stats |
| `services/conditioning.py` | Pose/identity mode selection |
| `services/workflow_checks.py` | Shared readiness checks |

### ComfyUI integration

- Client: `backend/app/comfy/client.py` (HTTP + WebSocket URL).
- Discovery: `backend/app/comfy/discovery.py`.
- Workflows: `workflows/*.json` + `*.mapping.json`.
- Current production workflows:
  - `sd15_txt2img`
  - `sd15_img2img`
  - `sd15_controlnet_pose`
  - `upscale_4x`
  - `wan22_t2v`
  - `wan22_i2v`
  - `animatediff_t2v`
- Mapping adapter: `backend/app/workflows/adapter.py`.
- Inference: `backend/app/workflows/inference.py`.
- Registry: `backend/app/workflows/registry.py`.

### Job execution

- Table `jobs` in SQLite.
- One asyncio worker (`JobRunner`) consumes an in-memory `asyncio.Queue`.
- Jobs are persisted; queued/running jobs are marked `interrupted` after restart.
- Progress comes from ComfyUI WebSocket.
- Outputs are downloaded via `/view` and stored under `outputs/<project>/<job>/`.
- Assets and `media_links` are written automatically when an `attach` target is present.
- Episode exports use a separate `asyncio.Lock` and `episodes.status/progress/log/error`.

## 3. Database

SQLite, stdlib `sqlite3`, WAL mode, foreign keys enabled.

`backend/app/db.py`

Current tables:

- `projects`
- `jobs`
- `assets`
- `media_links`
- `characters`
- `backgrounds`
- `scenes`
- `scene_cast`
- `dialogue_lines`
- `episodes`

Schema evolution uses `CREATE TABLE IF NOT EXISTS` plus `_ensure_column()` helpers. There is no migration version table yet.

## 4. Frontend

React 18 + TypeScript + Vite + React Router.

Pages:

- Dashboard
- Projects
- Characters
- Backgrounds
- Scenes
- Animation
- Voice & Dialogue
- Episode Editor
- Workflows
- Settings

Global project selection in `ProjectContext` with localStorage key `cartoon-studio.selected-project`. API client in `src/api.ts`. Types in `src/types.ts`. Shared UI components in `src/components/`.

There is no AI Director, production dashboard, approval UI, version comparison, or authentication UI.

## 5. Authentication and users

None. The app is intended for local single-user use. All endpoints are unauthenticated. This is a critical gap for remote MCP exposure.

## 6. Existing generation assets and models

- DreamShaper 8: `ComfyUI-Shared/models/checkpoints/DreamShaper_8_pruned.safetensors`
- 4x-UltraSharp: `ComfyUI-Shared/models/upscale_models/4x-UltraSharp.pth`
- Wan 2.2 TI2V-5B: `wan2.2_ti2v_5B_fp16.safetensors`
- UMT5-XXL FP8: `umt5_xxl_fp8_e4m3fn_scaled.safetensors`
- Wan VAE: `wan2.2_vae.safetensors`
- Kokoro-82M: `tools/kokoro/kokoro-v1.0.onnx` + `voices-v1.0.bin`
- Windows SAPI: Microsoft David / Zira
- FFmpeg 8.1.1

## 7. Functional components that must be retained

- Existing SQLite schema and data
- Existing ComfyUI workflows and mappings
- Existing generation queue and output pipeline
- Existing project/character/background/scene/dialogue/episode APIs
- Existing Kokoro/SAPI TTS integration
- Existing FFmpeg episode export and subtitle generation
- Existing React pages and design system

## 8. Incomplete/non-functional components

- No authentication/authorization.
- No MCP server.
- No in-app AI Director or OpenAI integration.
- No production orchestrator/state machine.
- No provider abstraction/registry.
- No approval/versioning system.
- No quality-control reports.
- No automated tests.
- No migration version tracking.
- No production audit logs.
- No cloud fallback providers.
- No AI-assisted script/storyboard generation.

## 9. Dependency map

```
React pages
  -> src/api.ts
    -> FastAPI routers
      -> service modules (generation, jobs, dialogue, tts, episodes, episode_export, media, assets)
        -> SQLite (db.py)
        -> ComfyUI (comfy/client.py + workflows/*)
        -> Kokoro/SAPI (tts.py)
        -> FFmpeg (episode_export.py)
```

Episode production flow:

```
Episode timeline -> episode_export -> FFmpeg segment renders -> concat -> audio mix -> MP4 asset
```

Scene generation flow:

```
Scene router -> creative.scene_prompt -> generation.submit_image -> JobRunner -> ComfyUI -> outputs -> assets -> media_links
```

Dialogue flow:

```
Dialogue router -> dialogue.create_line -> tts.synthesize -> outputs/<project>/voice -> assets -> media_links
```

## 10. Safety observations

- No endpoint exposes raw ComfyUI or arbitrary filesystem access.
- Asset file delivery is path-traversal guarded.
- ComfyUI config/models/workflows are not modified by the app.
- Output filenames are unique; existing media is not overwritten.
- Existing `local_ai_film_studio` on port 8000 is untouched.
- Remote exposure would currently be unsafe without authentication.

## 11. Constraints for integration

- GPU: RTX 4050 Laptop, ~6 GB VRAM.
- RAM: ~32 GB.
- One heavy local generation job at a time.
- TTS and FFmpeg are CPU-side and serialized separately.
- OpenAI/cloud calls must be opt-in; private assets must not be uploaded without permission.
- Existing app must keep working during and after integration.
