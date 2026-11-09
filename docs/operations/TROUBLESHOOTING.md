# Troubleshooting

## Existing app still works, new endpoints missing

- Confirm backend version is `0.7.0`:
  `Invoke-RestMethod http://127.0.0.1:8010/api/health`.
- Restart backend after code changes.
- Check `logs/backend-*.err.log` for import errors.

## Database migration issues

```powershell
cd D:\bro\CartoonStudio\backend
.\.venv\Scripts\python.exe -c "from app.db import init_db; init_db()"
```

Check:

```sql
SELECT * FROM schema_migrations;
```

Restore the pre-integration backup if needed:
`backups/pre-ai-integration-20261109-221344.zip`.

## AI Director returns 503

The backend is running but OpenAI is not configured.

```
OpenAI is not configured. Set OPENAI_API_KEY and OPENAI_MODEL.
```

Fix `.env`, restart backend, then check `/api/v1/ai/health`. The model ID must be available to your account.

## AI Director returns an OpenAI model/API error

- Verify `OPENAI_MODEL` is valid for the key/account.
- Check billing/quota and organization access.
- Check the backend log for the provider error.
- The model ID is not hardcoded; it is configuration.

## MCP health works but ChatGPT cannot connect

- ChatGPT needs a public HTTPS URL or Secure MCP Tunnel, not `127.0.0.1`.
- Start a tunnel and set `MCP_PUBLIC_URL`, `MCP_ALLOWED_HOSTS` and `MCP_ALLOWED_ORIGINS`.
- Endpoint must include `/mcp`.
- ChatGPT connectors use OAuth or No authentication; they do not accept a static bearer token.
- For local testing, set `MCP_AUTH_MODE=none` and `MCP_ALLOW_UNAUTHENTICATED=true`, select **No authentication** in ChatGPT, then restore bearer mode.
- For ongoing use, configure an OAuth-aware proxy.
- Check `/health` through the tunnel; it reports the active auth mode.

## MCP returns 401

- Missing/incorrect `Authorization: Bearer <token>`.
- Token revoked or wrong token.
- `MCP_BEARER_TOKEN` changed but MCP process not restarted.
- Create a new token with `POST /api/v1/mcp/tokens`.

## Tool returns confirmation_required

That is expected for expensive/destructive tools. Call again with `confirm=true` only after explicit user approval.

## Production run does not start

- Episode and scenes must exist.
- The plan must contain scene IDs.
- `confirm=true` is required.
- Check `/api/v1/production/status/{run_id}` and task errors.
- Check provider status; ComfyUI must be online for image/video tasks.
- Check the existing job queue for running jobs.

## Production task failed

- Read `production_tasks.error`.
- Check `logs/backend.log` and the job row.
- Use `regenerate_failed_scenes` or retry after fixing the provider/model.
- The orchestrator retries up to `max_attempts` (default 2).

## Provider unavailable

- ComfyUI provider: check `/api/v1/providers/status` and `comfyui_connected`.
- Kokoro: check `tools/kokoro/kokoro-v1.0.onnx` and `voices-v1.0.bin`.
- FFmpeg: check `ffmpeg` on PATH or the configured path.
- OpenAI image: requires `OPENAI_API_KEY` and `ALLOW_CLOUD_GENERATION=true`.

## Tests fail with DB locks or wrong data

Tests use `CARTOON_STUDIO_DB_PATH` and a temporary DB. Ensure no external process has overridden that variable. Run:

```powershell
cd D:\bro\CartoonStudio\backend
.\.venv\Scripts\python.exe -m pytest -q
```

## Port conflicts

- 8010 backend
- 5173 Vite
- 8020 MCP
- 8188 ComfyUI

Run `scripts\stop_all.ps1` to stop Cartoon Studio ports, then restart.

## SDXL model not detected

- Confirm the checkpoint is inside a configured `checkpoints` directory:
  `D:\bro\ComfyUI\Models\checkpoints`, `ComfyUI-Shared\models\checkpoints`, or the install’s `models\checkpoints`.
- Restart/refresh ComfyUI, then click **Model Studio → Refresh catalog**.
- Check `/api/comfy/models`; if the file is not in `checkpoints`, ComfyUI cannot load it.
- The catalog reports architecture from safetensors metadata, filename, or size. “Unknown” means verify the model card manually.

## SDXL is reported as blocked

- The `missing` list in Model Studio shows the reason. The most common cause is no SDXL checkpoint selected.
- Install a checkpoint manually, select it in Model Studio, save, then refresh.
- Cartoon Studio intentionally falls back to SD 1.5 rather than pretending SDXL works.

## SDXL CUDA out of memory

- Use 1024×1024, 1216×832, or 832×1216. The dimension guard rejects larger requests.
- Keep batch size 1 and tiled VAE enabled.
- Restart ComfyUI with `--lowvram` (or `--normalvram`) on the 6 GB GPU.
- Close other GPU applications.
- SDXL ControlNet/IPAdapter add extra VRAM; install only if needed.

## SDXL workflow is valid but not runnable

- Check `/api/workflows` → `model_status` for the missing checkpoint or VAE.
- Ensure the selected checkpoint is in the live ComfyUI `CheckpointLoaderSimple` options.
- The workflow templates use a placeholder `sd_xl_base_1.0.safetensors`; the runtime replaces it with the selected checkpoint.

## Character sheet is blocked

- Expression and pose sheets require an approved character with a master reference.
- Approve the character in Character Studio, then retry.
- Turnaround can run without a reference and will use text-to-image for all four views.

## LoRA or VAE selection fails

- The file must be in `models\loras` or `models\vae` and visible in ComfyUI.
- Refresh the catalog after installing it.
- The LoRA architecture must match the active model (SDXL LoRA for SDXL, SD 1.5 LoRA for SD 1.5).

## Local LLM is unavailable

- Start Ollama and confirm `ollama list`.
- Check `GET /api/v1/llm/health`.
- Set `LLM_PROVIDER=ollama` and `OLLAMA_MODEL=qwen3:8b` (or another installed completion model).
- The AI Director chat still needs OpenAI; local Ollama powers story/script tools and the LLM API.

## Vision review fails

- Confirm a vision model is installed in Ollama, e.g. `qwen2.5vl:3b`.
- Check `GET /api/v1/llm/health` → `ollama.models` capabilities include `vision`.
- The first vision call can take 30+ seconds on this GPU. Use the 3B model for faster previews.
- AI review never auto-approves; review the JSON manually.

## Shot plan is empty

- The episode needs a storyboard or at least one scene in the project.
- Build the shot plan from the Episode Editor.
- Building a plan does not queue generation jobs.

## VRAM is still low after Free VRAM

- Check whether another process is using the GPU.
- ComfyUI `/free` unloads its models, but Windows and other apps may hold VRAM.
- Restart ComfyUI with `--lowvram` when working with SDXL or video.

## Wan video is slow

- Wan 2.2 on 6 GB is slow. Use 320×192, 5 frames, 4 steps for pipeline tests.
- Use one short shot at a time; do not queue full episodes.
- Prefer LTX-Video only after installing and testing its weights.

## Lip-sync cues exist but no mouth animation

- The cue layer is intentionally separate. Mouth rendering needs Wav2Lip/SadTalker/Rhubarb or a rig/cut-out pipeline, none of which are installed.
- Edit cues via `PUT /api/v1/lip-sync/lines/{id}` and render them in the chosen 2D animation tool.
