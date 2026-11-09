# Connecting ChatGPT to Cartoon Studio (MCP)

## What is already implemented

- MCP server on `http://127.0.0.1:8020/mcp`.
- Official MCP Python SDK, streamable HTTP transport.
- Bearer-token authentication backed by `MCP_BEARER_TOKEN` or hashed `mcp_tokens`.
- 56 tools, 4 resources, 2 prompts.
- Structured results, confirmation gates, audit logs and timeouts.
- Verified with an MCP client: initialize, list_tools, call_tool, shared project reads and writes.

## What requires your account-side action

ChatGPT custom connector availability and UI labels depend on your ChatGPT plan, workspace policy and current OpenAI product UI. This server cannot complete those account-side steps for you. The server implementation is ready; the connection must be created in ChatGPT.

## Step 1 — start the backend

```powershell
cd D:\bro\CartoonStudio
.\scripts\start_all.bat
```

Verify:

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/v1/health
```

## Step 2 — create an MCP token

Option A — environment variable:

```powershell
# Put this in D:\bro\CartoonStudio\.env
MCP_BEARER_TOKEN=replace-with-a-long-random-secret
```

Option B — database token:

```powershell
$token = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8010/api/v1/mcp/tokens `
  -ContentType "application/json" `
  -Body '{"name":"chatgpt","scopes":"production"}'
$token.token
```

The raw token is shown once. Store it securely.

## Step 3 — start the MCP server

```powershell
cd D:\bro\CartoonStudio
.\scripts\start_mcp.bat
```

Verify:

```powershell
Invoke-RestMethod http://127.0.0.1:8020/health
```

## Step 4 — expose HTTPS

ChatGPT requires a reachable HTTPS endpoint for a remote connector. Use a tunnel:

### Cloudflare Tunnel

```powershell
cloudflared tunnel --url http://127.0.0.1:8020
```

### ngrok

```powershell
ngrok http 8020
```

Copy the public HTTPS URL. Set it in `.env` and restart MCP:

```env
MCP_PUBLIC_URL=https://your-public-host.example
```

The MCP endpoint is:

```
https://your-public-host.example/mcp
```

Health:

```
https://your-public-host.example/health
```

## Step 5 — create the ChatGPT connector

In the ChatGPT workspace/connector settings:

1. Create a custom connector / MCP integration.
2. URL: `https://your-public-host.example/mcp`.
3. Authentication: **Bearer token**.
4. Paste the MCP token.
5. Save and allow the connector.

The exact menu labels and plan restrictions can change. If your connector requires OAuth rather than a bearer token, place an OAuth authorization server/reverse proxy in front of `/mcp` or use a connector that supports bearer authentication. The Cartoon Studio MCP server is a resource server; it does not claim a full OAuth authorization-server implementation.

## Step 6 — test from Python

```python
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TOKEN = "YOUR_MCP_TOKEN"

async def main():
    async with streamablehttp_client(
        "http://127.0.0.1:8020/mcp",
        headers={"Authorization": f"Bearer {TOKEN}"},
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(len(tools.tools), "tools")
            result = await session.call_tool("list_projects", {})
            print(result.content[0].text)

asyncio.run(main())
```

## Confirmations

Expensive/destructive tools require `confirm=true`:

- `start_production`
- `cancel_production`
- `regenerate_failed_scenes`
- `render_episode`
- `export_episode`
- `delete_episode`
- `generate_character_sheet`
- `generate_scene_image`
- `regenerate_scene`
- `animate_scene`
- `regenerate_animation`

Without `confirm=true`, the tool returns `confirmation_required` and does not execute.

## Security notes

- Do not paste the MCP token into public chat logs.
- Rotate or revoke tokens if exposed:
  `POST /api/v1/mcp/tokens/{id}/revoke`.
- Keep the backend, MCP server and tunnel on trusted infrastructure.
- The MCP server never exposes the filesystem or raw ComfyUI execution.
