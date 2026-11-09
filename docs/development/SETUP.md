# Setup

## 1. Existing prerequisites

- Windows, Python 3.11, Node 18+.
- ComfyUI 0.44.2 running at `http://127.0.0.1:8188`.
- FFmpeg available (configured or on PATH).
- `cloudflared` installed for the one-click ChatGPT tunnel (already installed here at `C:\Program Files (x86)\cloudflared\cloudflared.exe`).
- The existing Cartoon Studio database and `outputs/` tree preserved.

## 2. Install backend dependencies

```powershell
cd D:\bro\CartoonStudio\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Important compatibility pins:

- `starlette==0.41.3` for FastAPI 0.115.6.
- `sse-starlette==2.1.3` and `mcp==1.30.0` to avoid the MCP 2.x / Starlette 1.x conflict.

## 3. Install frontend dependencies

```powershell
cd D:\bro\CartoonStudio\frontend
npm install
npm run build
```

## 4. Configure environment

Copy `.env.example` to `.env` at the repository root and fill in:

- `OPENAI_API_KEY`
- `OPENAI_MODEL` (a model available to your account)
- `MCP_BEARER_TOKEN` or create a DB token (bearer mode)
- `MCP_PUBLIC_URL` when using a tunnel
- For local ChatGPT testing only: `MCP_AUTH_MODE=none` + `MCP_ALLOW_UNAUTHENTICATED=true` + tunnel host in `MCP_ALLOWED_HOSTS`

Do not commit `.env`.

## 5. Start services

```powershell
cd D:\bro\CartoonStudio
.\scripts\start_all.bat
```

Then:

```powershell
.\scripts\start_mcp.bat
```

Ports:

- UI: `http://127.0.0.1:5173`
- Backend/API: `http://127.0.0.1:8010`
- MCP: `http://127.0.0.1:8020`
- ComfyUI: `http://127.0.0.1:8188`

## 6. Verify

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/health
Invoke-RestMethod http://127.0.0.1:8010/api/v1/health
Invoke-RestMethod http://127.0.0.1:8010/api/v1/providers/status
Invoke-RestMethod http://127.0.0.1:8020/health
```

## 7. AI Director

Open `http://127.0.0.1:8010/director` or the Vite equivalent. If OpenAI is not configured, the page shows a warning; the MCP and production tools still work.

## 8. Tests

```powershell
cd D:\bro\CartoonStudio\backend
.\.venv\Scripts\python.exe -m pytest -q
```

## 9. Database

The migration runner runs automatically on backend startup:

```powershell
.\.venv\Scripts\python.exe -c "from app.db import init_db; init_db()"
```
