# Connecting ChatGPT to Cartoon Studio (MCP)

## Important correction about authentication

ChatGPT custom MCP connectors support these authentication modes:

- **OAuth**
- **No authentication**
- **OAuth or no authentication**

ChatGPT **does not** accept a static bearer token / custom API key for a custom
MCP connector. That means the Cartoon Studio bearer token is not something you
can paste into the ChatGPT connector UI.

Cartoon Studio therefore supports two practical paths:

| Path | Security | Effort | Use case |
|---|---|---|---|
| A. No-auth mode behind a private tunnel | Low — anyone with the URL can control production | Low | Local testing on a trusted machine |
| B. OAuth-aware proxy | High | Medium/high | Ongoing or remote use |
| C. Bearer-capable MCP client | High | Low | Codex/Claude/Cursor/Python instead of ChatGPT |

Also note: custom MCP server connections are currently a **ChatGPT Business /
Enterprise / Edu** feature on ChatGPT web. Plan availability and UI labels can
change. If your account does not show "Add custom MCP server", your plan or
workspace policy does not allow it.

## If you are using Desktop Commander

Desktop Commander gives ChatGPT a shell, not the studio tool catalog. To keep the MCP
server local and authenticated, create an MCP token and call tools through
`scripts/mcp_call.py`:

```powershell
D:\bro\CartoonStudio\backend\.venv\Scripts\python.exe `
  D:\bro\CartoonStudio\scripts\mcp_call.py call list_projects "{}"
```

See **`docs/integration/MCP_TOOLS.md` → Calling these tools from Desktop Commander or a
shell** for token creation, examples and safety rules. Use this instead of exposing port
8020 with `MCP_AUTH_MODE=none` when ChatGPT only needs a few studio actions.

### OpenCode bridge connector

The agent-collaboration tools are a **separate MCP server** on port 8030:

```powershell
D:\bro\CartoonStudio\scripts\start_mcp_opencode.bat
```

Add a second ChatGPT connector pointing at the tunnel URL from **Connect OpenCode**
in AI Director (or `http://127.0.0.1:8030/mcp` for a bearer-capable client). It uses
tokens with scope `opencode`, not `production`. See
`docs/integration/OPENCODE_BRIDGE.md`.

The **Connect ChatGPT** button exposes the studio server on 8020; **Connect OpenCode**
exposes the agent bridge on 8030. They are independent.

---

## Fastest path — one-click from the Cartoon Studio UI

1. Start the backend and open the **AI Director** page:
   `http://127.0.0.1:8010/director`
2. Find the **ChatGPT Connection** panel.
3. Click **Connect ChatGPT**.
4. Wait for the connector URL, for example:
   `https://random-words.trycloudflare.com/mcp`
5. Copy the URL.
6. In ChatGPT, add a custom MCP server with that URL and **No authentication**.
7. Click **Disconnect & secure** when finished.

What the button does:

- starts `cloudflared tunnel --url http://127.0.0.1:8020`;
- captures the public URL;
- restarts MCP with `MCP_AUTH_MODE=none`, `MCP_ALLOW_UNAUTHENTICATED=true`, and the tunnel host allowlist;
- verifies local and public health;
- shows the connector URL;
- auto-stops the tunnel and restores bearer auth after the selected session length (30 minutes to 8 hours; default 30 minutes), or immediately when you click **Disconnect & secure**. Selecting **Never auto-stop** disables the timer; the tunnel then stays active until you disconnect or the backend/cloudflared stops.

Requirements:

- `cloudflared` installed and on PATH (already installed here).
- ChatGPT Business/Enterprise/Edu with custom MCP connectors enabled.
- Keep the backend running while the tunnel is active.

Security: the connector is unauthenticated while the tunnel is live. Anyone with
the URL can control production. Use it for a short local test and click
**Disconnect & secure** afterwards.

The manual steps below are the same flow without the UI.

---

## Path A — local ChatGPT test with no authentication

This is the fastest way to prove the connection. It disables MCP authentication,
so only do it behind a private/temporary tunnel and turn it back off afterwards.

### 1. Start the backend

```powershell
cd D:\bro\CartoonStudio
.\scripts\start_all.bat
```

Verify:

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/health
```

### 2. Start an HTTPS tunnel to the MCP port

Cloudflare quick tunnel:

```powershell
cloudflared tunnel --url http://127.0.0.1:8020
```

or ngrok:

```powershell
ngrok http 8020
```

Copy the public HTTPS host, for example:

```
https://random-words.trycloudflare.com
```

### 3. Configure no-auth mode

Edit `D:\bro\CartoonStudio\.env`:

```env
MCP_PUBLIC_URL=https://random-words.trycloudflare.com
MCP_AUTH_MODE=none
MCP_ALLOW_UNAUTHENTICATED=true
MCP_ALLOWED_HOSTS=random-words.trycloudflare.com
MCP_ALLOWED_ORIGINS=https://random-words.trycloudflare.com
```

`MCP_ALLOW_UNAUTHENTICATED=true` is a deliberate safety guard. The MCP server
refuses to start in `none` mode without it.

If the tunnel host changes, update `MCP_PUBLIC_URL`, `MCP_ALLOWED_HOSTS` and
`MCP_ALLOWED_ORIGINS` and restart MCP.

### 4. Restart MCP

```powershell
cd D:\bro\CartoonStudio
.\scripts\stop_all.bat
.\scripts\start_all.bat
.\scripts\start_mcp.bat
```

Or directly:

```powershell
cd D:\bro\CartoonStudio\backend
.\.venv\Scripts\python.exe run_mcp.py --transport streamable-http --host 127.0.0.1 --port 8020
```

Verify through the tunnel:

```powershell
Invoke-RestMethod https://random-words.trycloudflare.com/health
```

Expected:

```json
{"status":"ok","server":"cartoon-studio-mcp","tools":56,"auth":"none"}
```

Also verify the MCP endpoint is reachable:

```
https://random-words.trycloudflare.com/mcp
```

### 5. Add the connector in ChatGPT

The exact labels depend on your ChatGPT version:

- **Newer UI:** open `https://chatgpt.com/plugins`, select **+**, then
  **Add custom MCP server**.
- **Workspace UI:** **Workspace settings → Apps → Create**.
- **User UI:** **Settings → Apps → Create**.

Fill in:

| Field | Value |
|---|---|
| Name | `Cartoon Studio` |
| Description | `Local cartoon production controller` |
| Connection | `https://random-words.trycloudflare.com/mcp` |
| Authentication | **No authentication** |

Then:

1. Acknowledge the risk warning.
2. Select **Create as a plugin** / **Create**.
3. Run **Scan Tools** and wait for the 56 studio tools to appear.
4. Install/enable the plugin for your account or workspace.

### 6. Use it in a chat

Type `@` in the message box and select **Cartoon Studio**, then ask:

```
List my Cartoon Studio projects.
```

or:

```
Open project f892aded525b and show me the episode status.
```

ChatGPT will ask for confirmation before write actions by default. Cartoon
Studio additionally requires `confirm=true` for expensive/destructive tools.

### 7. Re-secure immediately after testing

Stop the tunnel, then restore bearer mode in `.env`:

```env
MCP_AUTH_MODE=bearer
# remove MCP_ALLOW_UNAUTHENTICATED or set it to false
```

Restart MCP. Confirm:

```powershell
Invoke-RestMethod http://127.0.0.1:8020/health
```

should again report `"auth": "bearer"`.

---

## Path B — OAuth-aware proxy (recommended for ongoing use)

ChatGPT expects an OAuth 2.1 authorization flow with discovery metadata, PKCE,
and refresh-token support. Cartoon Studio does **not** currently implement a full
OAuth authorization server. Do not claim OAuth is active unless you configure a
proxy or identity provider.

A practical pattern is:

```
ChatGPT
  -> HTTPS OAuth-aware proxy / identity provider
  -> authorized request + injected upstream credential
  -> Cartoon Studio MCP (bearer mode)
```

The proxy handles ChatGPT's OAuth discovery/authorization/token flow, then adds
the Cartoon Studio bearer token (or a signed JWT the MCP server trusts) to the
upstream MCP request.

Two implementation options:

1. **OAuth proxy that injects the existing bearer token.** No Cartoon Studio code
   change is needed. Configure the proxy to forward to
   `http://127.0.0.1:8020/mcp` and add:
   `Authorization: Bearer <MCP token>`.
2. **OAuth provider + JWT verification in Cartoon Studio.** Extend
   `CartoonTokenVerifier` to validate issuer, audience, expiry and scopes from
   your provider's JWKS, then use the provider's discovery metadata for
   ChatGPT. This is a code change and has not been implemented.

Requirements for the OAuth route:

- Public HTTPS endpoint ending in `/mcp`.
- OAuth discovery endpoint:
  `/.well-known/oauth-authorization-server` or
  `/.well-known/openid-configuration`.
- Authorization code flow with PKCE.
- Refresh tokens (`offline_access` where applicable).
- Correct issuer/audience validation.
- Access logging that does not store tokens.

If you want, the next implementation step is to add an OAuth provider adapter
and JWT verification to the MCP server.

---

## Path C — use a bearer-capable MCP client now

If you do not need ChatGPT specifically, the existing bearer-token server works
with clients that support custom headers.

### Python client

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

Create a token:

```powershell
$token = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8010/api/v1/mcp/tokens `
  -ContentType "application/json" `
  -Body '{"name":"local-client","scopes":"production"}'
$token.token
```

The raw token is shown once. Clients such as Codex CLI, Claude Desktop, Cursor
and other MCP-capable tools can use the same endpoint and Authorization header.

---

## Secure MCP Tunnel option

If your ChatGPT plan offers **Secure MCP Tunnel**, you can avoid exposing port
8020 publicly:

1. Create a tunnel in OpenAI Platform tunnel settings.
2. Run `tunnel-client` on this machine with access to
   `http://127.0.0.1:8020`.
3. In ChatGPT, choose **Tunnel** and select the tunnel instead of a public URL.
4. Authentication still applies at the MCP layer. Use no-auth mode only for
   local testing, or put OAuth in front for ongoing use.

The tunnel keeps the network path private, but it does not replace MCP
authentication/authorization.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| ChatGPT has no "Add custom MCP server" option | Custom MCP is a Business/Enterprise/Edu feature; check plan/workspace policy |
| ChatGPT scan fails with 401 | The connector is using OAuth/no-auth but MCP is still in bearer mode. Set `MCP_AUTH_MODE=none` with the guard for local testing |
| ChatGPT scan fails with 421 Invalid Host header | Add the tunnel host to `MCP_PUBLIC_URL`, `MCP_ALLOWED_HOSTS`, `MCP_ALLOWED_ORIGINS`, then restart MCP |
| Tunnel URL works in a browser but not ChatGPT | Use the exact `/mcp` path and HTTPS URL |
| Health says `"auth":"none"` and you are done testing | Restore `MCP_AUTH_MODE=bearer`, remove the no-auth guard, restart MCP, stop the tunnel |
| Tools appear but writes fail | ChatGPT requires confirmation for write actions; Cartoon Studio also requires `confirm=true` for expensive/destructive tools |
| No OpenAI key | The MCP/ChatGPT path does not need OpenAI. Only the in-app AI Director does |

## Security warning

No-auth mode means any client that can reach the tunnel can create projects,
queue GPU work, start production, render episodes, or archive data. Use it only
on a trusted machine, with a temporary tunnel, for a short test. Restore bearer
mode and stop the tunnel immediately afterwards.
