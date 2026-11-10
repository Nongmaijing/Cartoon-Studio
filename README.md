# Cartoon Studio

Local, dark-themed production app for Western 2D cartoon episodes, powered by an existing **ComfyUI** installation. **All six production phases plus the dual AI integration are complete:** application shell, dashboard, ComfyUI connection, workflow discovery, DreamShaper 8 image generation, 4× upscaling, project/character/background/scene management, Wan 2.2 video, character identity and pose control, Kokoro neural voice/dialogue, episode timeline and FFmpeg MP4 assembly, a shared production service layer, a provider registry, an automated production orchestrator, an authenticated MCP server for ChatGPT, and an in-app AI Director that can use OpenAI or a local Ollama model.

> **AI integration complete (v0.7.0).** The local production system remains fully usable without OpenAI. The AI Director activates when `OPENAI_API_KEY` and `OPENAI_MODEL` are configured. The MCP server is implemented and bearer-token tested; ChatGPT account-side connector setup is a deployment step.

---

## What works today

| Area | Status |
|---|---|
| Dark React shell with all 10 sidebar modules | Working |
| Dashboard: counts, ComfyUI status, GPU/RAM, live job queue with position/ETA, recent jobs, gallery | Working |
| ComfyUI connection test and live `/system_stats` | Working |
| ComfyUI discovery from the running process + model-path YAML | Working |
| Workflow discovery, API/UI format detection, validation against `/object_info` | Working |
| Workflow import (API format) with inferred role mapping, export | Working |
| SD 1.5 text-to-image generation through the job queue | Working — DreamShaper 8 production checkpoint |
| 4× production upscaling with 4x-UltraSharp | Working |
| Output download into `outputs/<project>/<job>/`, asset rows, preview | Working |
| Projects: create, rename, duplicate, archive, archive visibility, active-project selection | Working |
| Character Studio: profiles, reference views, expressions, poses, media library | Working |
| Character identity: canonical image, img2img consistency generation, adjustable denoise | Working |
| Pose control: ControlNet OpenPose when installed, img2img fallback otherwise | Working |
| AnimateDiff readiness and text-to-video template | Detected / template only until nodes + motion model exist |
| Background Studio: reusable environments, aspect ratios/resolutions, media library | Working |
| Scene Studio: cast, background, action, dialogue, camera, keyframe/video generation, media | Working |
| Animation: Wan 2.2 text-to-video and image-to-video, start-image upload | Working |
| Engine detection for Wan 2.2, AnimateDiff, IPAdapter, ControlNet | Working |
| Single-worker queue with positions, progress, elapsed time and ETA | Working |
| Project duplication copies characters, backgrounds, scenes, cast, dialogue lines, voice settings, media, links, episodes and exported MP4s | Working |
| Voice & Dialogue: per-character local voices, scene dialogue lines, previews, generated WAV audio | Working |
| Local TTS: **Kokoro-82M neural narration**, Windows SAPI, Piper, Coqui TTS, eSpeak NG | Kokoro ready here; SAPI fallback available |
| Story production: *Milo and the Little Light* 30-second children's motion comic | Exported and verified |
| Episode Editor: timeline segments, durations, transitions, audio tracks, subtitles, MP4 export | Working |
| FFmpeg assembly: 720p H.264 + AAC + soft subtitle track, progress/cancel/log | Working |
| Settings: server URL, paths, generation defaults, TTS paths, model listing, FFmpeg detection | Working |
| Windows start/stop scripts | Working |
| Shared application service layer, provider registry, production orchestrator | Working |
| AI Director page with chat, SSE progress, production control, approvals | Working — live OpenAI calls require a key/model |
| MCP servers (studio 8020 / OpenCode 8030, bearer + scoped tokens) | Working and tested |
| Production memory, approvals, character/asset versions, audit logs | Working |
| Model Studio: checkpoint/VAE/LoRA discovery, architecture detection, compatibility and missing-dependency reporting | Working |
| SDXL character/background workflow templates with tiled VAE and 6 GB presets | Templates valid; live SDXL blocked until an SDXL checkpoint is installed |
| Character turnaround / expression / pose sheet orchestration | Implemented; mocked tests pass; live SDXL blocked |
| SD 1.5 regression after the model-config changes | Working — live 512×512 test job completed |
| Automated tests | **42 passed** |

Verified on this machine: SD 1.5 jobs completed in seconds, saved under `outputs/<project>/<job>/`, and served at `/api/assets/{id}/file`. A scene with a cast and background generated a 512×288 keyframe, then a 320×192 / 5-frame Wan image-to-video clip using that keyframe as frame one (uploaded to ComfyUI's input root). Both outputs were copied into the project, attached to the scene as `keyframe` / `video`, and the clip was confirmed with ffprobe (`h264`, 320×192, 5 frames). In Phase 4 a character canonical image drove an SD 1.5 img2img job at denoise 0.55 (completed, attached as a reference), pose mode correctly reported an image-to-image fallback because no ControlNet model is installed, and a scene keyframe used a cast reference through img2img. AnimateDiff and ControlNet are reported as not runnable with their missing nodes/models named. In Phase 5 Windows SAPI was detected with Microsoft David and Zira, a character voice was saved, a scene line was synthesized to a 2.129 s WAV at 22.05 kHz, a narrator line and imported script lines were generated, and a duplicated project retained dialogue lines, voice settings and remapped audio files. In Phase 6 a two-segment 10-second episode (image + video, 3 dialogue tracks, fade transitions, soft subtitles) exported to 1280×720 H.264/AAC MP4 in **1.53 s** of FFmpeg time (**2.35 s** end-to-end including polling), producing a **1.68 MB** file with H.264 video, AAC stereo audio and `mov_text` subtitles; ffprobe confirmed 10.000 s duration. A duplicated project retained the episode timeline, remapped scene/audio assets and a playable copied MP4.

**Production story:** *Milo and the Little Light* is a 30.000 s children's motion comic in project `f892aded525b`. It uses five timeline segments (title card + four scenes), zoom/pan camera motion, 4× upscaled keyframes, 7 Kokoro voice lines, original music, three sparkle SFX, and soft subtitles. The final export is **4.02 MB**, 1280×720, 24 fps, H.264 + AAC stereo + `mov_text`, with 7 subtitle cues. The current file is `outputs/f892aded525b/episodes/4a0bb55ef460/episode_2.mp4` (asset `5c79ec9f1398`). The Kokoro voiceover replaced the earlier SAPI read; the old SAPI export remains as `episode.mp4` for comparison.

---

## Architecture

```
React + TypeScript + Vite  ──/api──▶  FastAPI (port 8010)
        (port 5173)                        │
                                           ├── SQLite  (data/cartoon_studio.db)
                                           ├── Job queue (single worker, one GPU job)
                                           ├── Workflow registry + mapping adapters
                                           └── ComfyUI HTTP + WebSocket (port 8188)
                                                      │
                                              ComfyUI Desktop
```

- **Backend:** Python 3.11, FastAPI, httpx, websockets, psutil, PyYAML, SQLite (stdlib).
- **Frontend:** React 18, TypeScript, Vite, React Router. No UI framework — a small custom design system in `src/styles.css`.
- **Media:** written by Cartoon Studio into its own `outputs/` tree. ComfyUI's output folder is read through `/view` and never modified.
- **Linking:** `media_links` connects any asset to a character, background or scene with a role (`reference`, `expression`, `pose`, `background`, `keyframe`, `video`, `dialogue`) and a label. Files are never copied or deleted when linking.
- **Voice:** local TTS (Windows SAPI, Piper, Coqui TTS or eSpeak NG) runs on the CPU, serialized by one lock. Generated WAV files are stored under `outputs/<project>/voice/` and registered as `audio` assets.
- **Export:** the Episode Editor reads existing images/clips/audio, renders segments, concatenates them, mixes audio, adds a soft subtitle track and writes a unique MP4 under `outputs/<project>/episodes/<episode_id>/` with FFmpeg. Timeline edits never regenerate scenes.
- **Queue:** one worker by default (`generation.max_concurrent_jobs = 1`). ComfyUI progress arrives over its WebSocket; completion is confirmed through `/history/{prompt_id}`. When a job finishes, its outputs are attached automatically if the job carried an `attach` target. Queued jobs report a stable position and the running job reports elapsed time plus an ETA.

### Ports

| Service | Port | Notes |
|---|---|---|
| Cartoon Studio backend | **8010** | Port 8000 belongs to the existing `local_ai_film_studio` app and is left untouched |
| Cartoon Studio frontend (dev) | **5173** | Vite proxies `/api` to 8010 |
| MCP server | **8020** | Separate process, bearer-token protected |
| ComfyUI | **8188** | Existing installation, used as-is |

The built frontend (`frontend/dist`) is also served by the backend at `http://127.0.0.1:8010/`, so the app can run without the Vite dev server.

---

## Directory layout

```
D:\bro\CartoonStudio\
    backend\        FastAPI app + .venv
    frontend\       React/TypeScript/Vite app + dist build
    data\           SQLite database
    projects\       per-project working files
    assets\         reserved for uploaded/reusable assets
    workflows\      API workflow JSON + <id>.mapping.json sidecars
    outputs\        generated media, <project>/<job>/
    logs\           backend.log (rotating)
    config\         config.json
    scripts\        Windows start/stop scripts
```

---

## Setup (already done on this machine)

Requirements: Python 3.11+, Node 18+, ComfyUI running locally.

```powershell
cd D:\bro\CartoonStudio\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

cd ..\frontend
npm install
```

---

## Running

### Easiest

Double-click `scripts\start_all.bat` (or run `scripts\start_all.ps1`).

This opens the backend and frontend in separate PowerShell windows and launches `http://127.0.0.1:5173`.

### Manually

```powershell
# Backend
cd D:\bro\CartoonStudio\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010

# Frontend (second terminal)
cd D:\bro\CartoonStudio\frontend
npm run dev
```

- UI: `http://127.0.0.1:5173`
- API docs: `http://127.0.0.1:8010/docs`
- Production build: `cd frontend; npm run build`, then use `http://127.0.0.1:8010/`

### Stopping

Run `scripts\stop_all.bat` (or `stop_all.ps1`). It stops **only** the processes listening on ports 8010, 5173 and 8020.

### MCP

```powershell
cd D:\bro\CartoonStudio
.\scripts\start_mcp.bat
```

Or manually:

```powershell
cd D:\bro\CartoonStudio\backend
.\.venv\Scripts\python.exe run_mcp.py --transport streamable-http --host 127.0.0.1 --port 8020
```

### Tests

```powershell
cd D:\bro\CartoonStudio\backend
.\.venv\Scripts\python.exe -m pytest -q
```

Current result: **42 passed**.

---

## ComfyUI discovery

Discovery never assumes a path. It reads, in order:

1. The running ComfyUI process command line and working directory.
2. `--output-directory`, `--input-directory`, `--extra-model-paths-config` arguments.
3. The model-path YAML referenced by that process.
4. Explicit values in `config/config.json`.

Discovered on this machine:

| Item | Value |
|---|---|
| Server | `http://127.0.0.1:8188` (0.44.2) |
| Install | `C:\Users\pagau\AppData\Local\Comfy-Desktop\ComfyUI-Installs\Waikhom Studio\ComfyUI` |
| ComfyUI output | `D:\bro\ComfyUI\Output` |
| Model dirs | `D:\bro\ComfyUI\Models`, `...\ComfyUI-Shared\models`, `...\Waikhom Studio\ComfyUI\models` |
| Production checkpoint | **DreamShaper 8** (`DreamShaper_8_pruned.safetensors`) |
| Base checkpoint | `v1-5-pruned-emaonly-fp16.safetensors` (kept as a fallback) |
| Upscaler | **4x-UltraSharp** (`4x-UltraSharp.pth`) |
| Wan 2.2 | `wan2.2_ti2v_5B_fp16.safetensors`, `umt5_xxl_fp8_e4m3fn_scaled.safetensors`, `wan2.2_vae.safetensors` |
| Custom nodes | no AnimateDiff/IPAdapter custom nodes; ControlNet core nodes exist but no ControlNet models |

Results are shown in **Settings → Discovery**. Use **Auto-discover** to refresh.

---

## Workflows and mappings

Every runnable workflow is a pair:

```
workflows\<id>.json           ComfyUI API-format graph, preserved as imported
workflows\<id>.mapping.json   sidecar mapping UI fields -> node id + input name
```

Included:

| ID | Kind | Engine |
|---|---|---|
| `sd15_txt2img` | image | DreamShaper 8 (SD 1.5) |
| `sd15_img2img` | image | DreamShaper 8 (SD 1.5 identity/pose reference re-render) |
| `sd15_controlnet_pose` | image | DreamShaper 8 + ControlNet OpenPose (when installed) |
| `upscale_4x` | image | 4x-UltraSharp upscaler |
| `wan22_t2v` | video | Wan 2.2 TI2V-5B |
| `wan22_i2v` | video | Wan 2.2 TI2V-5B |
| `animatediff_t2v` | video | DreamShaper 8 + AnimateDiff Evolved + VideoHelperSuite (when installed) |

The mapping sidecar names roles (`positive_prompt`, `negative_prompt`, `width`, `height`, `steps`, `cfg`, `seed`, `sampler`, `scheduler`, `length`, `fps`, `input_image`, `filename_prefix`, …) and the node/input that implements each role. Node IDs are **never hardcoded in the application**; they live only in the sidecar and are validated against `/object_info` before a job is submitted.

Importing an API workflow without a mapping infers roles from node classes and links (`backend/app/workflows/inference.py`). UI-format workflows are listed read-only with an explanation, because ComfyUI cannot execute them through `/prompt` directly.

Before submission the backend checks:

- mapped nodes and inputs exist in the graph,
- node classes are installed in ComfyUI,
- each mapped input exists on the live node definition,
- every node class in the graph is installed, not just the mapped ones,
- referenced checkpoint/model/text-encoder/VAE files are present.

`GET /api/workflows` exposes `runnable` and `missing_nodes` per workflow; `runnable` is false when any mapped role, node class, or model file is missing. A job fails fast with a readable message if any check fails.

---

## Production image models and upscaling

The image pipeline was upgraded for production-quality Western 2D cartoon output:

| Model | File | Location | Purpose |
|---|---|---|---|
| **DreamShaper 8** | `DreamShaper_8_pruned.safetensors` | `ComfyUI-Shared\models\checkpoints` | Default SD 1.5-family checkpoint for keyframes, characters and backgrounds |
| **4x-UltraSharp** | `4x-UltraSharp.pth` | `ComfyUI-Shared\models\upscale_models` | 4× detail-preserving upscale |
| Base SD 1.5 | `v1-5-pruned-emaonly-fp16.safetensors` | same checkpoints folder | Kept as a fallback |

What changed:

- `sd15_txt2img`, `sd15_img2img`, `sd15_controlnet_pose` and `animatediff_t2v` now point at **DreamShaper 8**.
- Production defaults: **28 steps**, **CFG 6.5**, **dpmpp_2m**, **karras**.
- Character Studio has HD presets (`768×1152`, `768×768`, `768×512`) plus a fast `512×768` option.
- **Upscale 4×** buttons appear on character media, background views and scene keyframes. The upscale workflow reads the existing asset, runs 4x-UltraSharp, saves a new unique image and attaches it back to the character/background/scene.
- No Western-cartoon LoRA was added: the available Western-cartoon LoRAs found were FLUX or SDXL, not SD 1.5-compatible. DreamShaper 8 plus the production prompt style and 4x-UltraSharp is the compatible SD 1.5 route.
- `config/comfyui_extra_model_paths.yaml` points a directly-started ComfyUI at the shared and `D:\bro\ComfyUI\Models` folders. The Comfy Desktop app uses the same directories from its own settings.

Measured on this machine (RTX 4050 Laptop, 6 GB VRAM):

| Operation | Settings | Time |
|---|---|---|
| DreamShaper 8 text-to-image | 512×512, 16 steps | **15.6 s** |
| Character img2img | 768×1152, 20 steps, denoise 0.5 | **14.9 s** |
| Upscale 256×144 → 1024×576 | 4x-UltraSharp | **2.1 s** |
| Upscale 512×512 → 2048×2048 | 4x-UltraSharp | **2.2 s** |
| Upscale 768×1152 → 3072×4608 | 4x-UltraSharp | **6.2 s** |

The 768×1152 → 3072×4608 upscale is a 14.2 MP result and completed successfully on the 6 GB RTX 4050. Higher resolutions and step counts increase time roughly linearly; 768×1152 is the recommended character production preset on this GPU.

### SDXL Model Studio (image-generation upgrade)

A new **Model Studio** page (`/models`) extends the existing model configuration without replacing the SD 1.5 pipeline.

- Scans the configured ComfyUI model directories for checkpoints, VAEs, LoRAs, ControlNet and upscalers.
- Reads safetensors metadata where available, then falls back to filename/size heuristics. Architecture detection always reports its confidence and source.
- Shows file size, ComfyUI installation status, compatible engines, detection details and local path.
- Reports missing dependencies. Vetted SDXL recommendations expose a download button: it requires an explicit licence confirmation, is whitelist-only, resumes partial files, verifies size and SHA256, and installs into the first configured model directory. Nothing is fetched without that confirmation.
- Lets the operator choose the default architecture, SDXL/SD 1.5 checkpoints, VAE, LoRA and strength, workflow per task, and 6 GB-safe resolution/sampling presets.
- Displays the active model, architecture, workflow, GPU name, VRAM usage, ComfyUI low-VRAM/attention flags, queue status and recent image outputs.
- Character Studio adds optional per-character model overrides (architecture, checkpoint, VAE, LoRA, reference strength) and turnaround/expression/pose sheet buttons.

Current machine audit:

- Installed checkpoints: **DreamShaper 8** and **SD 1.5 base** only. No SDXL checkpoint.
- VAEs: Wan 2.2 VAE and ComfyUI `pixel_space`; no external SDXL VAE.
- LoRAs: none. ControlNet models: none. Custom nodes: none.
- GPU: RTX 4050 Laptop, 6 GB VRAM; ComfyUI is not currently launched with an explicit low-VRAM flag.
- **SDXL generation tests are blocked until an SDXL checkpoint is installed and selected.** Cartoon Studio reports this rather than pretending SDXL works.

SDXL workflow templates added:

| Workflow | Purpose |
|---|---|
| `sdxl_txt2img` | General SDXL text-to-image |
| `sdxl_img2img` | SDXL reference conditioning / identity |
| `sdxl_character_turnaround` | Character reference/turnaround views |
| `sdxl_character_expression` | Expression sheet from an approved reference |
| `sdxl_character_pose` | Pose sheet from an approved reference |
| `sdxl_background` | 16:9 Little Wonder Village backgrounds |

All SDXL templates use tiled VAE decoding and batch size 1. Safe presets are 1024×1024, 1216×832 and 832×1216, with 25–30 steps and CFG 5–7. The SDXL dimension guard rejects requests above the configured 6 GB pixel budget with a clear error.

Character consistency:

- The approved canonical image remains the master reference.
- Expression and pose sheets require an approved character; an unapproved reference is not used silently.
- The same seed is used across each sheet, and each image is generated through the existing single-worker queue.
- Optional character-specific LoRA and reference strength are stored in character memory; no database migration is required.
- Generated characters are never auto-approved.

SD 1.5 remains selectable and is the automatic fallback until an SDXL checkpoint is installed and configured. A live SD 1.5 regression job completed after the model-config changes (512×512, asset `d5c70209dd33`).

See `docs/integration/SDXL_MODEL_GUIDE.md` for manual model installation, licensing, VRAM expectations and limitations.

### Production Studio milestone

The app now has a cross-department production layer in addition to the image-generation upgrade:

- **Central production registry** (`GET /api/v1/registry`) reports image, editing, consistency, video, voice, ASR, SFX, music, LLM, VLM and upscaling readiness, with candidate model sources, licenses and VRAM notes.
- **Resource manager** (`/api/v1/resources/status`, `/free`, `/estimate`) reports GPU/RAM/queue state, frees ComfyUI VRAM, and estimates workflow cost. The Model Studio has a **Free VRAM** button.
- **Job tracking** (migration v2) records resource class, model, estimated/actual seconds, peak VRAM and priority. The queue is priority-aware.
- **Local LLM/VLM** through Ollama: Qwen3 8B for story/script generation, Qwen2.5-VL 7B/3B for structured visual review. OpenAI remains an optional fallback for Director chat.
- **Shot plan** (`/api/v1/production/episodes/{id}/shot-plan`) builds a shot-level plan with cast, background, camera, dialogue, keyframe/animation needs and rough GPU-time estimates. Building a plan starts no jobs.
- **Production report** (`/api/v1/production/report`) reports counts, job statuses, resource usage, peak VRAM and recent jobs.
- **Lip-sync cue layer** (`/api/v1/lip-sync/...`) generates editable viseme cues per dialogue line. Mouth-shape rendering is a separate blocked model step.
- **1080p export** is available in the Episode Editor; a 1920×1080 H.264/AAC/subtitle test export was verified.

Actual results on this machine:

| Test | Result |
|---|---|
| Production registry | 7 ready, 3 partial, 1 blocked |
| Resource status | RTX 4050, 6.0 GB VRAM, 31.71 GB RAM |
| Free VRAM | Increased free VRAM to 4.9 GB |
| Local LLM story | Qwen3 8B, 78 s, 4-scene story |
| Local VLM review | Qwen2.5-VL 3B, 30.5 s, structured JSON |
| Lip-sync cues | 43 editable cues for a 2.75 s line |
| Shot plan | 1 shot, 19.4 s estimated GPU time |
| Wan image-to-video | 320×192, 5 frames, 16.75 s, peak 3333 MB |
| 4× upscale | 384→1536, 5.77 s, peak 2471 MB |
| Kokoro dialogue | 1.75 s WAV |
| SFX + music | Local assets generated |
| 1080p export | 1920×1080 H.264/AAC/mov_text, 6.0 s |
| Automated tests | **42 passed** |

Blocked on this machine: SDXL generation (no checkpoint), image editing (Qwen/FLUX weights missing), IPAdapter/ControlNet (weights missing), speech recognition (no Whisper), lip-sync rendering (no Wav2Lip/SadTalker/Rhubarb), LTX/Hunyuan/CogVideoX and audio-generation model weights.

See `docs/architecture/PRODUCTION_STUDIO.md` and `docs/integration/MODEL_REGISTRY.md`.

### Production voice model

The voiceover was upgraded from Windows SAPI to **Kokoro-82M**:

| Item | Value |
|---|---|
| Engine | Kokoro-82M ONNX (Apache 2.0) |
| Model | `tools/kokoro/kokoro-v1.0.onnx` (310.5 MB) |
| Voices | `tools/kokoro/voices-v1.0.bin` (26.9 MB) |
| Runtime | `kokoro-onnx` + ONNX Runtime, CPU |
| Narration | Heart (warm female) |
| Milo | Michael (friendly male) |
| Lumi | Bella (bright female) |
| Speed | ~0.8 s per typical story line on this CPU |

Kokoro replaces the robotic SAPI read with natural neural narration. SAPI remains available as a fallback engine.

---

## Character consistency and pose control (Phase 4)

- A character can store one **canonical identity** image (`characters.canonical_asset_id`). Set or clear it from Character Studio; it becomes the default reference for consistency generation.
- Consistency generation uses `sd15_img2img`: the reference/canonical image is uploaded to ComfyUI's input root, scaled, VAE-encoded and re-rendered at an adjustable **denoise** (`0.1–1.0`). Lower denoise preserves the design more strongly.
- Reference mode `identity` re-renders the design. Reference mode `pose` uses `sd15_controlnet_pose` with a ControlNet OpenPose model **only when both the ControlNet nodes and a model file are installed**; otherwise it falls back to img2img with the pose reference and reports `fallback: true`.
- The ControlNet model name is discovered from the live ComfyUI and injected into the workflow; it is not hardcoded.
- Scenes expose `GET /api/scenes/{id}/references`, combining each cast member's canonical image, reference/pose media and the scene's existing keyframes. Keyframe generation accepts `reference_asset_id`, `reference_mode`, `denoise` and `control_strength` and stores them in `settings_json`.
- `animatediff_t2v` ships as a preserved API workflow. It is listed but marked unavailable until `ADE_AnimateDiffLoaderGen1`, `VHS_VideoCombine` and a motion model are present. Nothing is downloaded automatically.
- Animation accepts a character canonical image as the start image for image-to-video, and disables video workflows that are structurally invalid or not runnable.

---

## Image editing and speech recognition

- **Whole-image SDXL edits:** `POST /api/v1/editing/edit` with `source_asset_id` and `prompt`; re-renders at the requested `denoise`. This is a refinement pass, not an instruction-following editor.
- **Masked SDXL inpainting:** add `mask_asset_id` (white = regenerate, black = keep). Uses `SDXL_Inpainting_0.1.safetensors`, `VAEEncodeForInpaint` and tiled VAE decode. Configure the checkpoint as `models.checkpoints.sdxl_inpaint`.
- **Identity checks:** `POST /api/characters/{id}/consistency-check` compares a candidate image with the approved canonical reference using the local Ollama vision model and returns `same_character`, confidence, wardrobe match and differences. It is advisory; it never approves a character.
- **Speech recognition:** `POST /api/v1/speech/transcribe` runs `faster-whisper-small` on CPU int8 and returns text, timestamped segments and an SRT string. Model path: `models/asr/faster-whisper-small`; override with `WHISPER_MODEL_DIR`, `WHISPER_DEVICE` and `WHISPER_COMPUTE_TYPE`.
- Qwen-Image-Edit and FLUX Kontext remain optional semantic editors; neither is installed. Speech recognition does not overwrite episode subtitles automatically.
- Details and measured results: `docs/integration/IMAGE_EDITING_AND_ASR.md`.

---

## Generation and outputs

- `POST /api/generate` queues a job; one job runs at a time.
- Character and background endpoints build the prompt from saved identity fields, add a fixed cartoon style and a view/expression/pose suffix, then submit through the same queue.
- Each job gets a unique `filename_prefix` (`cartoon_studio/<job_id>`), so outputs cannot collide.
- Completed files are copied from ComfyUI through `/view` into `outputs/<project_id>/<job_id>/`.
- If a filename already exists, `_2`, `_3`, … is appended — media is never silently overwritten.
- ComfyUI's own output folder and history are left intact.
- Failures are written to `logs/backend.log` and stored on the job row with status `failed` and an error message.
- Cancelling a queued job marks it `cancelled`; cancelling a running job sends ComfyUI `/interrupt`.
- Jobs left `queued`/`running` when the app restarts are marked `interrupted`.

Media endpoint: `GET /api/assets/{asset_id}/file` (path-traversal guarded to the outputs directory).

---

## Scenes and animation

- A scene stores its name, description, action, dialogue, camera direction and duration, plus generation settings in `settings_json`.
- `scene_cast` links characters to a scene; the scene's background lives in `settings_json.background_id`. Deleting or editing a scene never deletes character/background rows or media.
- Scene prompts are composed from the scene fields, the background name/description and each cast member's appearance/clothing/style, then the fixed Western 2D cartoon style and a keyframe or motion suffix.
- `POST /api/scenes/{id}/generate` with `kind: "keyframe"` uses the configured SD 1.5 image workflow. With `kind: "video"` it uses Wan 2.2.
- Video requests choose an image-to-video workflow when a start image is supplied, otherwise a text-to-video workflow. A workflow can be forced by id.
- Start images are uploaded to ComfyUI's **input root** as `cartoon_studio_<asset_id>.<ext>` so `LoadImage` can see them. ComfyUI Desktop's shared input folder does not expose subfolders to `LoadImage`.
- Wan 2.2 constraints are enforced: width/height snap to 32, frame count snaps to `4n+1`, and conservative `VAEDecodeTiled` is used for 6 GB VRAM.
- Completed keyframes/videos are attached to the scene automatically (`role=keyframe` or `role=video`) and appear in the Scene Studio and Animation pages.
- `GET /api/animation/engines` reports what the live server can actually run. Wan 2.2 is reported available only when all required nodes **and** the expected model files exist. AnimateDiff, IPAdapter and ControlNet are reported unavailable unless their nodes and model files are present; nothing is downloaded or installed automatically.

### Queue UX

- `GET /api/jobs/queue` returns the running job, pending jobs in order, and counts.
- Queued jobs expose `queue_position`; the running job reports progress, elapsed seconds and a smoothed ETA in the UI.
- Dashboard, Scene Studio and Animation all show the same queue panel.
- Cancelling a queued job removes it; cancelling a running job sends ComfyUI `/interrupt`.

---

## Voice and dialogue (Phase 5)

- Local speech engines are discovered at runtime; nothing is downloaded or installed automatically.
  - **Kokoro-82M** is the primary production voice engine. It runs locally on the CPU, uses the Apache-2.0 licensed ONNX model in `tools/kokoro/`, and provides nine narrator/character voices.
  - **Windows SAPI** is read through `System.Speech` and remains available as a fallback.
  - **Piper** is used when the executable and at least one `.onnx` voice model are configured or found beside it.
  - **Coqui TTS** is used when the `tts` command exists.
  - **eSpeak NG** is used when `espeak-ng` or `espeak` exists.
- Kokoro voices used in *Milo and the Little Light*: **Heart** (warm female narrator), **Michael** (friendly male Milo), **Bella** (bright female Lumi). Kokoro synthesizes a typical story line in under a second on this CPU.
- `GET /api/voice/engines` returns every engine with `available`, executable path, voices, notes and a project default. `POST /api/voice/preview` returns a short WAV preview without creating an asset.
- A character stores one reusable voice: engine, voice name, rate (`-10..10`), pitch (`-50..50%`) and volume (`0..100`). Assign it from **Voice & Dialogue** or `PATCH /api/characters/{id}/voice`.
- Dialogue is stored as ordered lines in `dialogue_lines`, separate from the legacy `scenes.dialogue` text field.
  - Each line has a speaker (cast member or narrator), text, emotion, voice override, start offset, generated audio asset and duration.
  - Emotions apply small rate/pitch/volume offsets at synthesis time without changing the saved base voice settings. Regenerating a line is stable and never escalates the stored values.
  - `POST /api/scenes/{id}/dialogue/import` splits the Scenes-page dialogue text into lines. A `Name: text` prefix is matched against the scene cast; `Narrator:` is recognised explicitly.
- Generated audio is written under `outputs/<project>/voice/dialogue_<line_id>.wav`, registered as an `audio` asset, linked to the scene as `role=dialogue`, and never overwrites an existing file.
- `POST /api/dialogue/{id}/generate` renders one line; `POST /api/scenes/{id}/dialogue/generate` renders all lines sequentially and reports per-line errors without hiding successes.
- TTS runs on the local CPU, is serialized by a single lock (so voices never fight over the SAPI process), and does not occupy the ComfyUI GPU queue.
- Deleting a line removes the line and its scene audio link but keeps the audio file and asset row; regenerating keeps older assets while the line points at the newest render.
- Project duplication copies dialogue lines, voice settings, generated audio assets and remapped scene links.

---

## Episodes and MP4 export (Phase 6)

- An episode stores a timeline in `episodes.timeline_json`; editing it never regenerates or modifies scenes, keyframes, clips or dialogue audio.
- Timeline model:
  - **Segments** reference an existing scene and one visual asset (keyframe image or generated clip). Each segment has a duration, trim start, transition (`cut` or `fade through black`) and label.
  - **Audio tracks** reference existing audio assets (dialogue, music, SFX) with start offset, volume and optional loop.
  - **Settings** cover resolution (1280×720 default), FPS, subtitle mode, background music/volume and fade duration.
- The Episode Editor auto-adds the selected scene’s generated dialogue audio when a segment is added, using each line’s start offset and duration.
- `PUT /api/episodes/{id}/timeline` validates every scene/asset against the project and normalizes IDs, durations and even dimensions.
- `POST /api/episodes/{id}/export` starts an asynchronous FFmpeg export:
  - each segment is scaled/padded to the target resolution, converted to H.264 `yuv420p`, and optionally faded;
  - segments are concatenated without re-encoding the already-encoded segments;
  - audio tracks are converted to 48 kHz stereo, delayed to their start offset, mixed with `amix`, limited, and encoded as AAC 192 kbps;
  - soft subtitles are built from the timeline’s dialogue audio (text and duration come from TTS asset metadata) and muxed as `mov_text`, with a matching `.srt` sidecar;
  - progress, log lines, errors and cancellation are stored on the episode and polled by the UI.
- Exports run on the local CPU, serialized by one lock, and do not touch the ComfyUI GPU queue.
- Every export writes a new unique `episode*.mp4` under `outputs/<project>/episodes/<episode_id>/`; earlier exports are never overwritten.
- Exports are registered as `video` assets, so they appear in the asset gallery and survive project duplication with remapped scene/audio references.
- API:
  - `GET/POST /api/episodes`
  - `GET/PATCH/DELETE /api/episodes/{id}`
  - `PUT /api/episodes/{id}/timeline`
  - `POST /api/episodes/{id}/export`, `GET /api/episodes/{id}/export`
  - `POST /api/episodes/{id}/cancel`
  - `GET /api/episodes/{id}/file`, `GET /api/episodes/{id}/subtitles`

---

## AI Director and MCP (v0.7.0)

Two AI front ends share the exact same production system:

- **In-app AI Director** — a React page (`/director`) backed by the OpenAI Responses API or a local Ollama model selected in the page.
- **MCP server** — an authenticated server for ChatGPT and other MCP clients, built with the official MCP Python SDK.

Neither has its own database, queue, project manager, or generator. Both call the shared `ToolRegistry`, which calls the shared service layer, which uses the existing `jobs` queue, providers, assets and FFmpeg export.

### Director model selection

The Director page has a model selector next to the conversation picker:

- **OpenAI** — the configured `OPENAI_MODEL`, using the Responses API.
- **Ollama** — any installed local model that reports the `tools` capability, using the OpenAI-compatible `/v1/chat/completions` endpoint.

`GET /api/v1/ai/models` lists both. The choice is stored with the conversation (`provider:model`) and sent with each message. Models without tool calling are shown but disabled, because the Director cannot run production actions without tools. Local turns are slower than OpenAI; a read-only `list_projects` turn on Qwen3 8B took about 129 seconds on this machine.

```
ChatGPT / MCP ──▶ Studio MCP (8020, 56 tools) ──▶ ToolRegistry ──▶ shared services
ChatGPT / MCP ──▶ OpenCode MCP (8030, 4 tools) ──▶ local OpenCode agent

In-app Director ──▶ OpenAI or Ollama ──▶ 56 studio tools

shared services ──▶ SQLite / ComfyUI / Kokoro / FFmpeg / outputs/
```

### Shared service layer

- `project_service`, `episode_service`, `character_service`, `scene_service`
- `dialogue_service`, `audio_service`, `script_service`, `storyboard_service`
- `asset_service`, `approval_service`, `quality_control_service`
- `production_service` + `orchestration/production_orchestrator.py`

These are the only path to production data. REST, AI Director and MCP all use them.

### Production memory and approvals

- Project memory (`projects.memory_json`), character memory, and episode script/storyboard/production/continuity JSON.
- Character approvals with version snapshots (`character_versions`).
- Scene approvals/rejections and deterministic quality reports (`scene_reviews`).
- Asset versions (`asset_versions`) and audit logs (`audit_logs`).
- Expensive or destructive tool calls require `confirm=true`; without it the tool returns `confirmation_required` and does nothing.

### Production orchestrator

- `production_runs` + `production_tasks` persist every stage.
- Stages: scene image, audio, optional animation, assembly.
- Supports pause, resume, cancel, retry, progress, logs and restart recovery.
- Assembly builds the episode timeline and starts the existing FFmpeg exporter; the orchestrator waits for backend confirmation before marking the run completed.
- It uses the existing generation queue; there is no parallel queue.

### AI Director capabilities

- Inspect projects, characters, episodes, scenes, jobs and production runs.
- Create/update characters, episodes, scenes and dialogue.
- Generate stories, scripts and storyboards (needs OpenAI).
- Generate character sheets, scene keyframes and animations.
- Generate dialogue audio, music and SFX.
- Start/pause/resume/cancel production and regenerate failed scenes.
- Review scenes/episodes and render/export episodes.
- The Director never claims a generation finished until the backend job reports `completed`.
- Conversations and tool executions are persisted; SSE progress events are supported. Token-level streaming is not implemented.

### MCP server status

- Official SDK `mcp==1.30.0`.
- Transports: `stdio` and `streamable-http` at `http://127.0.0.1:8020/mcp`.
- Bearer-token authentication (`MCP_BEARER_TOKEN` or hashed tokens in `mcp_tokens`).
- Studio MCP exposes 56 tools from the shared registry, 4 resources and 2 prompts. The OpenCode bridge runs separately on 8030 with 4 tools and its own `opencode` token scope.
- Structured JSON results, timeouts, idempotency keys, confirmation gates, audit logs.
- Health endpoint: `http://127.0.0.1:8020/health`.
- Verified with a real MCP client: `initialize`, `list_tools`, `call_tool`, shared project/character/episode writes and REST reads in both directions.
- OAuth: the server is a bearer-token **resource server**. A full OAuth authorization server is not implemented and is documented as a proxy/deployment step.

### Director model status on this machine

- OpenAI is configured and uses `AsyncOpenAI` + `client.responses.create(...)` with `previous_response_id` and `function_call_output` continuation.
- Local Ollama models are also supported through Chat Completions with the same tool schemas. The model must report the `tools` capability.
- The AI Director page lists both providers. A live read-only local turn on `qwen3:8b` called `list_projects` successfully in about 129 seconds.
- To change the OpenAI model, update `OPENAI_MODEL` in `D:\bro\CartoonStudio\.env` and restart the backend. To change the local model, select it in the Director page.

### One-click ChatGPT connection (UI)

Open the **AI Director** page. There are two independent connection panels:

**ChatGPT Connection** — studio tools on 8020:

1. Click **Connect ChatGPT**.
2. The backend starts a Cloudflare quick tunnel to port 8020, temporarily switches MCP to no-auth mode, waits for local and public health, and returns the connector URL.
3. Copy the displayed URL (`https://<tunnel-host>/mcp`) into a ChatGPT custom MCP connector with **No authentication**.
4. Click **Disconnect & secure** when finished. The tunnel stops, MCP returns to bearer mode, and the temporary state is removed.
5. If you forget, the tunnel auto-stops after the selected session length (30 minutes to 8 hours; default 30 minutes). You can also choose **Never auto-stop**, which keeps it active until you click **Disconnect & secure** or the backend/cloudflared stops.

**OpenCode Bridge Connection** — agent tools on 8030:

1. Click **Connect OpenCode**.
2. It starts a separate tunnel to 8030, switches only the OpenCode bridge to no-auth mode, and shows a second connector URL.
3. Add that URL as a separate ChatGPT connector, scan its four `opencode_*` tools, and enable it.
4. Click **Disconnect & secure** to restore bearer mode on 8030.

The UI uses `/api/v1/mcp/tunnel/start|stop|status` for studio and `/api/v1/mcp/tunnel/opencode/start|stop|status` for the bridge. Both require `cloudflared` on PATH. Both tunnels are public and no-auth while active, so use them only for short tests.

### Start and test MCP

```powershell
cd D:\bro\CartoonStudio
.\scripts\start_mcp.bat
Invoke-RestMethod http://127.0.0.1:8020/health
```

Create a token:

```powershell
$token = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8010/api/v1/mcp/tokens `
  -ContentType "application/json" `
  -Body '{"name":"chatgpt","scopes":"production"}'
$token.token   # shown once; store securely
```

ChatGPT custom connectors support OAuth or "No authentication"; they do **not** accept a static bearer token. For local testing, Cartoon Studio supports an explicit no-auth mode behind a private tunnel (`MCP_AUTH_MODE=none` + `MCP_ALLOW_UNAUTHENTICATED=true` + matched `MCP_PUBLIC_URL`/host). For ongoing use, put an OAuth-aware proxy in front of the MCP server. See `docs/integration/CHATGPT_CONNECTION.md` for both paths, the exact `.env` values, the ChatGPT connector fields, and the security rollback steps.

### AI/MCP limitations (honest status)

- OpenAI Director requires credentials and a valid model ID; local Ollama models work when they report tool-calling support.
- Local Director turns are substantially slower than OpenAI on this hardware.
- ChatGPT connector setup depends on the account/workspace UI and plan; not performed here.
- Full OAuth authorization server is not implemented.
- Cloud video generation is interface-only; no adapter is claimed.
- Token-level streaming is not implemented; SSE progress events are.
- AI-assisted quality scoring is reserved behind `ENABLE_AI_QC`; deterministic QC is active and does not invent an objective score.

---

## API summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | App health |
| GET | `/api/v1/health` | Integration health, providers, system stats |
| GET/POST | `/api/v1/ai/conversations` | List/create AI Director conversations |
| GET | `/api/v1/ai/conversations/{id}` | Conversation, messages and tool executions |
| POST | `/api/v1/ai/conversations/{id}/messages` | Non-streaming Director turn |
| POST | `/api/v1/ai/conversations/{id}/messages/stream` | SSE Director progress stream |
| GET | `/api/v1/ai/tools` | 56 shared tool definitions |
| POST | `/api/v1/ai/tools/{name}` | Execute a shared tool locally |
| GET | `/api/v1/ai/tool-executions` | Tool execution audit |
| GET | `/api/v1/ai/health` | OpenAI/local LLM configuration status |
| GET | `/api/v1/registry` | Cross-department production registry and candidates |
| GET | `/api/v1/resources/status` | GPU/VRAM/RAM/queue status |
| POST | `/api/v1/resources/free` | Unload ComfyUI models and free VRAM |
| POST | `/api/v1/resources/estimate` | Estimate workflow time/VRAM |
| GET | `/api/v1/llm/health` | Ollama/OpenAI status and local models |
| POST | `/api/v1/llm/generate` | Local/external text or JSON generation |
| POST | `/api/v1/llm/vision-review` | Structured visual review of an image asset |
| POST | `/api/v1/lip-sync/lines/{id}/generate` | Generate editable viseme cues |
| GET/PUT | `/api/v1/lip-sync/lines/{id}` | Read/update viseme cues |
| POST | `/api/v1/production/episodes/{id}/shot-plan` | Build shot-level plan and estimate |
| GET | `/api/v1/production/episodes/{id}/shot-plan` | Read the shot plan |
| GET | `/api/v1/production/episodes/{id}/estimate` | Preview episode resource estimate |
| POST | `/api/v1/production/episodes/{id}/shots/{shot_id}/status` | Update a shot's production status |
| GET | `/api/v1/production/report` | Production counts, statuses, resource usage |
| POST | `/api/v1/production/start` | Start a production run (confirm) |
| POST | `/api/v1/production/pause/{run}` | Pause a run |
| POST | `/api/v1/production/resume/{run}` | Resume a run |
| POST | `/api/v1/production/cancel/{run}` | Cancel a run (confirm) |
| GET | `/api/v1/production/status/{run}` | Run state, tasks, progress, logs |
| GET | `/api/v1/production/queue` | Recent production runs |
| GET | `/api/v1/production/overview` | Scene/run/provider overview |
| GET | `/api/v1/production/logs/{run}` | Production logs |
| POST | `/api/v1/production/regenerate-failed/{episode}` | Retry failed scenes (confirm) |
| POST | `/api/v1/production/scenes/{id}/review` | Deterministic scene QC |
| POST | `/api/v1/production/scenes/{id}/approve` | Approve a scene |
| POST | `/api/v1/production/scenes/{id}/reject` | Reject a scene |
| GET | `/api/v1/providers` | Provider definitions |
| GET | `/api/v1/providers/status` | Live provider status incl. ComfyUI |
| GET/PUT | `/api/v1/providers/configs[/{id}]` | Provider configs |
| GET | `/api/v1/mcp/status` | MCP status |
| GET | `/api/v1/mcp/tools` | MCP tool schemas |
| GET/POST | `/api/v1/mcp/tokens` | List/create MCP bearer tokens |
| POST | `/api/v1/mcp/tokens/{id}/revoke` | Revoke an MCP token |
| POST | `/api/v1/mcp/tools/{name}` | Execute a shared tool with MCP semantics |
| GET | `/api/dashboard` | Counts, ComfyUI status, system stats, jobs, assets |
| GET/POST | `/api/projects` | List/create projects |
| GET/PATCH | `/api/projects/{id}` | Read/update project |
| POST | `/api/projects/{id}/archive` | Archive |
| POST | `/api/projects/{id}/duplicate` | Duplicate metadata, media, characters, backgrounds, scenes, dialogue, episodes and links |
| GET/POST | `/api/characters` | List/create character profiles |
| GET/PATCH | `/api/characters/{id}` | Read/update a character |
| POST/DELETE | `/api/characters/{id}/canonical` | Set/clear the canonical identity image |
| PATCH | `/api/characters/{id}/voice` | Assign the character's local voice and tuning |
| POST | `/api/characters/{id}/generate` | Generate a reference view, expression or pose (text2img / img2img / ControlNet) |
| GET/POST | `/api/characters/{id}/media` | List media / attach an existing asset |
| GET | `/api/characters/{id}/jobs` | Generation history for a character |
| GET/POST | `/api/backgrounds` | List/create backgrounds |
| GET/PATCH | `/api/backgrounds/{id}` | Read/update a background |
| POST | `/api/backgrounds/{id}/generate` | Generate a background image |
| GET/POST | `/api/backgrounds/{id}/media` | List media / attach an existing asset |
| GET | `/api/backgrounds/{id}/jobs` | Generation history for a background |
| GET/POST | `/api/scenes` | List/create scenes |
| GET/PATCH | `/api/scenes/{id}` | Read/update a scene |
| POST | `/api/scenes/{id}/generate` | Generate a keyframe (text2img / img2img / ControlNet) or video for the scene |
| GET | `/api/scenes/{id}/references` | Combined cast canonical/reference/pose images and scene keyframes |
| GET/POST | `/api/scenes/{id}/media` | List media / attach an existing asset |
| POST/DELETE | `/api/scenes/{id}/cast[/{character_id}]` | Add/remove scene cast |
| GET | `/api/scenes/{id}/jobs` | Generation history for a scene |
| GET | `/api/animation/engines` | Detect Wan 2.2, AnimateDiff, IPAdapter, ControlNet |
| POST | `/api/animation/generate` | Queue a text-to-video or image-to-video job |
| GET | `/api/animation/jobs` | Animation job history |
| GET | `/api/voice/engines` | Detect Windows SAPI, Piper, Coqui TTS and eSpeak NG |
| POST | `/api/voice/preview` | Render a short WAV preview without saving an asset |
| GET/POST | `/api/scenes/{id}/dialogue` | List/create dialogue lines |
| POST | `/api/scenes/{id}/dialogue/import` | Split the scene dialogue text into lines |
| POST | `/api/scenes/{id}/dialogue/generate` | Render every line in the scene sequentially |
| PATCH/DELETE | `/api/dialogue/{id}` | Edit/delete a dialogue line |
| POST | `/api/dialogue/{id}/generate` | Render one dialogue line to WAV and attach it |
| GET/POST | `/api/episodes` | List/create episode timelines |
| GET/PATCH/DELETE | `/api/episodes/{id}` | Read/update/delete an episode |
| PUT | `/api/episodes/{id}/timeline` | Validate and save segments, audio and export settings |
| POST/GET | `/api/episodes/{id}/export` | Start an async FFmpeg export / read status |
| POST | `/api/episodes/{id}/cancel` | Cancel a queued or running export |
| GET | `/api/episodes/{id}/file` | Download the exported MP4 |
| GET | `/api/episodes/{id}/subtitles` | Download the generated SRT |
| GET | `/api/jobs/queue` | Running job, pending jobs and positions |
| GET | `/api/workflows` | Discovered workflows with validation/model status |
| GET | `/api/workflows/{id}` | Graph + mapping |
| POST | `/api/workflows/{id}/validate` | Live validation |
| POST | `/api/workflows/import` | Import API workflow (mapping optional) |
| GET | `/api/workflows/{id}/export` | Download graph + mapping |
| POST | `/api/generate` | Queue a generation |
| GET | `/api/jobs`, `/api/jobs/{id}` | Queue/history |
| POST | `/api/jobs/{id}/cancel` | Cancel |
| GET | `/api/assets`, `/api/assets/{id}`, `/api/assets/{id}/file` | Asset metadata/media |
| GET/PUT | `/api/settings` | Read/update config |
| GET | `/api/comfy/test` | Connection test |
| GET | `/api/comfy/discovery` | Live installation/model discovery |
| GET | `/api/comfy/models` | Models reported by `/object_info` |
| GET | `/api/comfy/queue` | ComfyUI queue depth |
| GET | `/api/comfy/object-info/{node}` | Node definition |

---

## Safety rules enforced by the design

- ComfyUI configuration and workflows are **never modified**. Model files are written only to a configured model directory after an explicit, licence-confirmed download.
- Nothing is downloaded implicitly. The only fetch path is Model Studio's licence-gated download button for whitelisted sources, which verifies size and SHA256 before install.
- Project data, workflows and outputs live under `CartoonStudio`, separate from ComfyUI.
- Output filenames are unique; existing media is never silently overwritten.
- Generated WAV files are moved into the project output tree with unique names; regenerations create new assets.
- Workflow inputs are validated against the live ComfyUI node definitions before submission.
- Only one GPU-heavy job runs at a time by default; TTS and FFmpeg exports are CPU-only and serialized separately.
- Every episode export writes a new unique MP4; existing exports are never overwritten.
- Timeline, audio and subtitle edits only read existing assets; they never regenerate or modify scenes.
- The existing `D:\bro\local_ai_film_studio` app on port 8000 is not touched.

---

## Troubleshooting

| Symptom | Check |
|---|---|
| Sidebar says ComfyUI offline | ComfyUI Desktop is running; Settings → Test connection; server URL is `http://127.0.0.1:8188` |
| Workflow shows "unavailable" | Settings → Available Models; the checkpoint/model named in the mapping is missing. Production workflows need `DreamShaper_8_pruned.safetensors`; upscaling needs `4x-UltraSharp.pth` |
| Upscale 4× is disabled or fails | Confirm `4x-UltraSharp.pth` is in `ComfyUI-Shared\models\upscale_models` and ComfyUI can see it in `UpscaleModelLoader`; refresh the Workflows page or restart ComfyUI |
| Imported workflow lists as `ui` format | Export it from ComfyUI with **Save (API format)** and import that JSON |
| Port 8010 or 5173 already in use | Run `scripts\stop_all.ps1`, then start again |
| Job failed immediately | Read the error on the job row and `logs\backend.log`; validation messages name the exact role/node |
| Image generation slow | Normal on a 6 GB laptop GPU; reduce steps or resolution for tests. Wan video can take 20+ minutes per clip |
| Animation says no video workflow | Check that `wan22_t2v` / `wan22_i2v` are valid in Workflows and that the Wan model files are listed |
| Start image not found by ComfyUI | Cartoon Studio uploads to ComfyUI's input root; restart ComfyUI only if its input folder changed, then regenerate |
| Wan job very slow or out of memory | Use 320×192, 5 frames and low steps for pipeline tests; close other GPU apps |
| No speech engine available | Windows SAPI should expose at least one installed voice; otherwise install Piper + a `.onnx` voice, Coqui TTS, or eSpeak NG and press **Re-check engines** |
| Voice preview has no sound | Check the Windows output device and volume; the preview is a WAV generated locally and played in the browser |
| Piper is installed but unavailable | Set the Piper executable and the folder containing `.onnx` voice models in Settings → Voice / TTS, then re-check engines |
| Dialogue line generates but audio is long/short | Adjust rate/pitch/volume or the emotion; SAPI voice durations vary by voice |
| Imported scene text has the speaker name in the line | Use `Name: text` where `Name` exactly matches a cast member, or `Narrator: text` |
| Export says FFmpeg was not found | Install FFmpeg or set its full path in Settings → Storage → FFmpeg path, then retry |
| Export fails during segment rendering | Check the episode error/log; the exact FFmpeg stderr tail is stored on the episode |
| Export has no audio | Add scene segments (dialogue audio is auto-added) or add audio tracks manually; check track volume and start offset |
| Subtitles are missing | Set Subtitles to “Embed soft track from dialogue”; subtitles come from dialogue audio/text, not from silent scenes |
| Export is slow | 720p H.264 is CPU-bound; lower resolution/FPS or shorten segments. The sample 10 s episode exports in about 1.5 s of FFmpeg time |
| Episode video does not play in a browser | Use the Download MP4 link or a player with H.264/AAC support; the file also contains a soft subtitle track |
| AI Director returns 503 | `OPENAI_API_KEY`/`OPENAI_MODEL` are not set; add them to `.env` and restart the backend |
| MCP health works but ChatGPT cannot connect | ChatGPT connectors use OAuth or No authentication, not a static bearer token. For local testing use `MCP_AUTH_MODE=none` + `MCP_ALLOW_UNAUTHENTICATED=true` behind a tunnel and add the tunnel host to `MCP_PUBLIC_URL`/`MCP_ALLOWED_HOSTS`; for ongoing use configure OAuth. See `docs/integration/CHATGPT_CONNECTION.md` |
| MCP returns 401 | Missing/wrong `Authorization: Bearer <token>`, revoked token, or MCP process not restarted after changing the token |
| Tool returns `confirmation_required` | Expected for expensive/destructive tools; call again with `confirm=true` only after explicit approval |
| Production run does not start | Episode and scenes must exist, the plan needs scene IDs, and `confirm=true` is required |
| Provider unavailable | Check `/api/v1/providers/status`; ComfyUI must be online for image/video, Kokoro files must exist, FFmpeg must be on PATH or configured |

---

## Phase status

- **Phase 1 — complete:** shell, dashboard, connection, discovery, SD 1.5 generation, preview/saving, projects, workflows, settings.
- **Phase 2 — complete:** Character Studio, Background Studio, active-project selection, duplication of characters/backgrounds/media.
- **Phase 3 — complete:** Scene Studio (cast, background, action, dialogue, camera), Wan 2.2 text-to-video / image-to-video, engine detection, single-worker queue with positions/progress/ETA, scene media attachment.
- **Phase 4 — complete:** character canonical identity, SD 1.5 img2img consistency generation with adjustable denoise, pose mode with ControlNet when available and honest img2img fallback, scene reference picker, AnimateDiff workflow template with readiness/missing-node reporting, identity start-image picker in Animation.
- **Phase 5 — complete:** local TTS engine discovery (Windows SAPI ready here; Piper/Coqui/eSpeak detected when installed), per-character voice assignment with rate/pitch/volume, per-scene dialogue lines with speakers and emotions, scene-script import, WAV preview and generation, automatic audio assets/links, project duplication of dialogue and audio.
- **Phase 6 — complete:** episode timeline with scene segments, adjustable durations/trims/transitions, dialogue/music/SFX audio tracks, subtitle generation from dialogue audio, asynchronous FFmpeg assembly with progress/log/cancel, 720p H.264/AAC MP4 export, SRT sidecar, unique output files, and project duplication of episodes and exports.

### AI integration status (v0.7.0)

| Phase | Area | Status |
|---|---|---|
| 0 | Existing system audit and backup | Complete |
| 1 | Shared application service layer | Complete |
| 2 | Versioned migrations, AI/production tables, jobs reuse | Complete — migration v1 applied |
| 3 | REST API and production orchestration | Complete |
| 4 | MCP servers: studio 8020 + OpenCode 8030, scoped bearer auth | Complete and client-tested; OAuth proxy is a deployment step |
| 5 | OpenAI AI Director (Responses API) | Implemented; live calls blocked by missing key/model; mocked test passes |
| 6 | Persistent project/character/episode memory and approvals | Complete |
| 7 | Provider abstraction and registry | Complete; cloud video interface-only |
| 8 | Automated production and deterministic QC | Complete; AI-assisted QC disabled by default |
| 9 | AI Director frontend | Complete, production build passes |
| 10 | Security, token auth, redaction, audit, rate limits | Complete; full OAuth server not implemented |
| 11 | Automated tests | **42 passed** |
| 12 | Documentation, `.env.example`, startup scripts | Complete |

**All six production phases and the AI integration phases are implemented.** The production pipeline is fully usable without OpenAI. The AI layers are real backend integrations, not mocks, in production code; the automated tests mock external services by design.
