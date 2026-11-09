# Production Studio Architecture

## Purpose

Cartoon Studio is extended from an image/episode tool into a modular AI-assisted animation studio. The production target is **Children Stories — Little Wonder Village**, season **Little Adventures, Big Friendships**, 12 episodes × 7 minutes, for ages 2–6.

The architecture deliberately keeps the existing FastAPI, SQLite, React, ComfyUI, Kokoro, FFmpeg and MCP foundation. New departments are additive.

## Department map

```
React UI
  ├─ Model Studio (/models)         registry, model config, GPU/VRAM, vision review
  ├─ Character Studio               master reference, expressions, poses, sheets
  ├─ Background Studio              reusable locations, 16:9 SDXL preset
  ├─ Scene / Animation              keyframes, Wan image-to-video, shot media
  ├─ Voice & Dialogue               character voices, dialogue audio, lip-sync cues
  ├─ Episode Editor                 timeline, 1080p export, shot plan
  └─ AI Director / MCP              tools, production runs, approvals
        │
        v
Shared service layer
  ├─ model_config_service            image model discovery/config
  ├─ production_registry_service     cross-department readiness and candidates
  ├─ resource_manager                GPU/RAM/queue/free-VRAM/estimates
  ├─ shot_plan_service               shot-level plan and production report
  ├─ llm_provider                    Ollama/OpenAI text + vision
  ├─ lip_sync_service                editable viseme cue layer
  ├─ quality_control_service         deterministic QC + human review
  └─ existing character/scene/audio/editing services
        │
        v
Existing single-worker queue / SQLite / ComfyUI / Kokoro / FFmpeg
```

## Model registry

`GET /api/v1/registry` aggregates:

- ComfyUI checkpoints, VAEs, LoRAs, ControlNet and upscalers.
- ComfyUI node availability for Wan, LTX, Hunyuan, CogVideoX, Qwen-Image-Edit, FLUX Kontext, ACE-Step, Stable Audio, MusicGen, AudioGen.
- Ollama text/vision models and capabilities.
- TTS engines (Kokoro/SAPI/Piper/Coqui/eSpeak detection).
- FFmpeg editing capability.
- Department status: `ready`, `partial`, or `blocked`.
- Candidate model sources, licenses, sizes, VRAM notes and commercial-use caveats.

The registry is **read-only**. It never downloads or installs weights.

## Resource manager

`GET /api/v1/resources/status` reports:

- ComfyUI connection and version.
- GPU name, total/free/used VRAM.
- System RAM.
- Queue depth.
- A 6 GB recommendation.

`POST /api/v1/resources/free` calls ComfyUI `/free` with `unload_models=true` and `free_memory=true`.

`POST /api/v1/resources/estimate` returns resource class, estimated seconds and estimated VRAM for a workflow + parameters.

## Queue and job tracking

Migration **v2** adds:

- `jobs.resource_class`
- `jobs.model_name`
- `jobs.execution_seconds`
- `jobs.peak_vram_mb`
- `jobs.priority`
- `jobs.estimated_seconds`
- equivalent resource columns on `production_tasks`
- estimated/actual seconds on `production_runs`

The existing single-worker queue now uses a priority queue (`priority DESC, created_at ASC`). It records:

- actual execution time;
- peak VRAM sampled every 2 seconds;
- resource class (`gpu_image`, `gpu_video`, `cpu_audio`, `cpu_edit`);
- model/checkpoint used;
- OOM advice on CUDA/out-of-memory failures.

No second GPU queue was introduced.

## Local LLM and VLM

`app/services/llm_provider.py` supports:

- **Ollama** first in `auto` mode (local, preferred).
- **OpenAI Responses API** as a fallback when configured.

Installed local models on this machine:

| Model | Size | Capabilities |
|---|---|---|
| `qwen3:8b` | ~5.2 GB | completion, tools, thinking |
| `qwen2.5:7b` | ~4.7 GB | completion, tools |
| `qwen2.5vl:7b` | ~6.0 GB | completion, vision |
| `qwen2.5vl:3b` | ~3.2 GB | completion, vision (faster) |
| `Qwen3-VL-8B Q4_K_M` | ~5.8 GB | completion, tools, vision |

Endpoints:

```text
GET  /api/v1/llm/health
GET  /api/v1/llm/models
POST /api/v1/llm/generate
POST /api/v1/llm/vision-review
```

Vision review returns structured JSON and always sets `human_review_required: true`. It never auto-approves an asset.

Story/script generation now uses the local LLM when Ollama is available. A continuity check reports character names not present in the project.

## Shot planning

`app/services/shot_plan_service.py` builds a shot-level plan from the episode storyboard or scenes:

- scene/shot number, start/end, duration;
- cast and background;
- camera/action;
- dialogue and audio requirements;
- keyframe/animation needs;
- generation instructions;
- image/video resource estimates;
- planned/approved status.

Endpoints:

```text
POST /api/v1/production/episodes/{id}/shot-plan
GET  /api/v1/production/episodes/{id}/shot-plan
GET  /api/v1/production/episodes/{id}/estimate
POST /api/v1/production/episodes/{id}/shots/{shot_id}/status
GET  /api/v1/production/report?project_id=...
```

Building a plan does **not** start generation.

## Lip-sync cue layer

`app/services/lip_sync_service.py` creates an editable viseme cue layer from dialogue text and audio duration.

Migration **v3** adds `dialogue_lines.lip_sync_json`.

Endpoints:

```text
POST /api/v1/lip-sync/lines/{line_id}/generate
GET  /api/v1/lip-sync/lines/{line_id}
PUT  /api/v1/lip-sync/lines/{line_id}
POST /api/v1/lip-sync/scenes/{scene_id}/generate
```

This is not a photoreal lip-sync renderer. Mouth-shape rendering is blocked until Wav2Lip/SadTalker/Rhubarb or a rig pipeline is installed.

## Department readiness on this machine

| Department | Status | Notes |
|---|---|---|
| Image generation | Ready | SD 1.5 and SDXL (`DreamShaperXL_1.0.safetensors`) installed and verified |
| Image editing | Partial | Qwen-Image-Edit/FLUX Kontext nodes exist, local weights missing; SD 1.5 img2img available |
| Character consistency | Partial | Canonical reference + img2img + LoRA injection; IPAdapter/ControlNet weights missing |
| Video generation | Partial | Wan 2.2 installed and tested; LTX/Hunyuan/CogVideoX weights missing |
| Voice generation | Ready | Kokoro/SAPI local |
| Speech recognition | Blocked | No Whisper/faster-whisper package or model |
| Sound effects | Ready | Local procedural SFX |
| Music | Ready | Local procedural music bed |
| Scriptwriting | Ready | Ollama Qwen3 8B / Qwen2.5 7B |
| Visual QC | Ready | Ollama Qwen2.5-VL |
| Upscaling | Ready | 4x-UltraSharp |

## Actual test results

| Test | Result |
|---|---|
| Production registry | Passed — 7 ready, 3 partial, 1 blocked |
| Resource status | Passed — RTX 4050, 6.0 GB total, 2.87 GB free, 31.71 GB RAM |
| Free VRAM | Passed — free VRAM increased to 4.9 GB |
| Local LLM story generation | Passed — Qwen3 8B, 78 s, 4-scene story |
| Local VLM review | Passed — Qwen2.5-VL 3B, 30.5 s, structured JSON |
| Lip-sync cues | Passed — 43 editable cues for a 2.75 s line |
| Shot plan | Passed — 1 shot, 19.4 s estimated GPU time |
| Production report | Passed — counts, statuses, resource usage, recent jobs |
| SD 1.5 image generation | Passed — 384×384, asset `514163b98ec9` |
| SDXL generation | Passed — 1024×1024, `DreamShaperXL_1.0.safetensors`, 30.3 s, peak 5602 MB, asset `343185cb8b15` |
| SDXL workflows | Passed — all six `runnable=true` |
| Four-view turnaround | Passed live — Leo sheet `71192986e23b`, 4 assets; prompt composition needs QA fixes |
| Wan image-to-video | Passed — 320×192, 5 frames, asset `8224f26eb739`, 16.75 s, peak 3333 MB |
| 4× upscale | Passed — 384→1536, asset `dd893937cbb2`, 5.77 s, peak 2471 MB |
| Kokoro dialogue | Passed — 1.75 s WAV, asset `f9726f170b8f` |
| Local SFX | Passed — asset `5e0aca751713` |
| Local music | Passed — asset `9462863c6639` |
| 1080p episode export | Passed — 1920×1080 H.264, AAC stereo, mov_text, 6.0 s, asset `8ce8ace5a449` |
| Automated tests | **42 passed** |
| Frontend build | Passed |

## Remaining limitations

- SDXL is installed, but turnaround prompts can produce multi-view sheets and drift from the
  character’s wardrobe; fix prompt composition before promoting references.
- No Qwen-Image-Edit/FLUX Kontext local weights; image-edit tests are blocked.
- No IPAdapter/SDXL ControlNet weights; reference conditioning uses img2img.
- No Whisper/faster-whisper; ASR and audio-to-lip alignment are blocked.
- No lip-sync rendering model; only the cue layer exists.
- No LTX/Hunyuan/CogVideoX weights; video production uses Wan 2.2.
- No AudioGen/MusicGen/ACE-Step/Stable Audio weights; current audio uses Kokoro and local synthesis.
- Seven-minute episodes require many sequential shots; the current single-worker queue is reliable but slow.
- ComfyUI low-VRAM mode is reported/recommended but not changed automatically.

## Recommended hardware upgrades

1. **24 GB GPU** (RTX 4090/5090 or A6000-class) for SDXL/video without aggressive offloading.
2. **64 GB system RAM** for model loading/unloading and ComfyUI CPU offload.
3. **Fast NVMe storage** for multi-GB checkpoints and video assets.
4. A second machine or external GPU host for video generation if episode throughput matters.

## Operating guidance

- Use SD 1.5 for quick iteration; SDXL (`DreamShaperXL_1.0.safetensors`) is now the verified character-art checkpoint.
- Use Wan only for short shots at low resolution on this GPU.
- Keep batch size 1 and tiled VAE enabled.
- Free VRAM between model families.
- Build a shot plan before starting expensive generation.
- Keep human review in the loop; AI QC never approves assets.
- Never download community checkpoints without checking source and license.
