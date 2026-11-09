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
