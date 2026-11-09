# Deployment

## Local deployment

```powershell
cd D:\bro\CartoonStudio
.\scripts\start_all.bat
.\scripts\start_mcp.bat
```

| Service | URL |
|---|---|
| UI (Vite) | `http://127.0.0.1:5173` |
| Backend / production build | `http://127.0.0.1:8010` |
| MCP | `http://127.0.0.1:8020/mcp` |
| MCP health | `http://127.0.0.1:8020/health` |
| ComfyUI | `http://127.0.0.1:8188` |

## Health checks

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/health
Invoke-RestMethod http://127.0.0.1:8010/api/v1/health
Invoke-RestMethod http://127.0.0.1:8010/api/v1/providers/status
Invoke-RestMethod http://127.0.0.1:8020/health
```

## Logs

- Backend stdout/stderr: `logs/backend-*.out.log`, `logs/backend-*.err.log`
- App rotating log: `logs/backend.log`
- MCP: `logs/mcp.out.log`, `logs/mcp.err.log`
- ComfyUI: `logs/comfyui.out.log`, `logs/comfyui.err.log`

## Restart

The backend re-runs migrations, marks interrupted episode exports, and resumes pending production runs on startup. Completed assets and task state are preserved.

```powershell
.\scripts\stop_all.ps1
.\scripts\start_all.bat
.\scripts\start_mcp.bat
```

## Remote MCP

1. Start backend and MCP.
2. Start a tunnel (Cloudflare Tunnel or ngrok) to port 8020.
3. Set `MCP_PUBLIC_URL` to the HTTPS tunnel URL.
4. Restart MCP.
5. Configure the ChatGPT custom connector to `https://<public-host>/mcp` with the bearer token.

No inbound firewall rule is required when using a tunnel.

## Production considerations

- Keep the app on a trusted machine.
- Use a long random MCP token and rotate it.
- Keep `.env` out of version control.
- Restrict tunnel access where the provider supports it.
- Back up `data/cartoon_studio.db`, `outputs/`, `config/`, `workflows/` before upgrades.
- The local UI is unauthenticated; do not expose port 8010 publicly without a reverse proxy and authentication.

## Cloud generation

Disabled by default. If enabled:

```env
ALLOW_CLOUD_GENERATION=true
OPENAI_API_KEY=...
```

Only use cloud providers with assets you are permitted to upload. The local ComfyUI path remains the default.
