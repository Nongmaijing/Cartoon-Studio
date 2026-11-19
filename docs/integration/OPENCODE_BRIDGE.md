# OpenCode Bridge (ChatGPT → OpenCode agent)

## What it is

Four MCP tools run as a **separate MCP server** so ChatGPT can ask a local
OpenCode agent to inspect code, create workflows, run tests, and make changes,
without mixing them into the Cartoon Studio tool list.

The bridge calls the **OpenCode HTTP API** through the `opencode api` command, so it
uses the same running service and authentication as the TUI. No second OpenCode
instance is started.

```text
ChatGPT
  ├─ Studio connector (8020 /mcp)   → 58 Cartoon Studio tools
  └─ OpenCode connector (8030 /mcp) → 4 OpenCode tools
                                        └─ opencode api → local agent in D:\bro
```

## Server profiles

The MCP server supports three profiles:

| Profile | Tools | Default port | Purpose |
|---|---|---|---|
| `studio` | 58 studio tools | 8020 | Cartoon Studio production |
| `opencode` | 4 OpenCode tools | 8030 | Agent collaboration |
| `all` | 60 tools | 8020 | Backwards-compatible single connector |

Run separately:

```powershell
.\scripts\start_mcp.bat           # studio, 8020
.\scripts\start_mcp_opencode.bat  # opencode, 8030
```

Direct:

```powershell
backend\.venv\Scripts\python.exe backend\run_mcp.py --profile studio --port 8020
backend\.venv\Scripts\python.exe backend\run_mcp.py --profile opencode --port 8030 `
  --public-url http://127.0.0.1:8030
```

Each profile has its own token scope:

- `studio` and `all` require `production`.
- `opencode` requires `opencode`.

Create a token for each:

```powershell
# Studio
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/v1/mcp/tokens `
  -ContentType "application/json" -Body '{"name":"studio","scopes":"production"}'

# OpenCode bridge
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/v1/mcp/tokens `
  -ContentType "application/json" -Body '{"name":"opencode","scopes":"opencode"}'
```

A `production` token cannot connect to 8030, and an `opencode` token cannot connect
to 8020. That is deliberate isolation.

## Tools

| Tool | Purpose |
|---|---|
| `opencode_ask` | Start a task: `message`, optional `session_id`, `title`, `model`, `wait_seconds`, `delivery` |
| `opencode_task` | Poll a task: `session_id`, optional `message_id` |
| `opencode_sessions` | List recent OpenCode sessions: `limit` |
| `opencode_permission` | Answer a pending permission request: `session_id`, `request_id`, `decision` (`once`, `always`, `reject`) |

`opencode_ask` returns immediately when `wait_seconds` is 0. With the default 45 it
waits up to 45 seconds for a result, then returns `status: "running"` and the
`session_id` to poll with `opencode_task`.

Status values:

- `queued` — the message is waiting in the session inbox
- `running`
- `completed`
- `failed`
- `waiting_for_permission`

A completed result includes `text`, `tools`, `message_count`, `inbox_count`,
`directory` and `pending_permissions`.

## Model selection

Default: `OPENCODE_BRIDGE_MODEL=opencode-go/beam-free` (free, avoids unexpected
charges). Override in `CartoonStudio\.env`:

```env
OPENCODE_BRIDGE_MODEL=opencode-go/beam-free
# or a stronger model:
# OPENCODE_BRIDGE_MODEL=opencode-go/gpt-5.6-luna
# or local:
# OPENCODE_BRIDGE_MODEL=ollama/qwen3:8b
OPENCODE_BRIDGE_DIR=D:\bro
```

Per-call override:

```json
{"message": "Run the backend tests", "model": "ollama/qwen3:8b"}
```

Important: the default OpenCode model on this machine (`claude-fable-5-2`) failed
with **“Insufficient account funds”**. Always pass or configure a model that your
account can run.

## Using it from ChatGPT

Add a **second** custom MCP connector:

| Field | Value |
|---|---|
| Name | `OpenCode Bridge` |
| URL (ChatGPT web) | click **Connect OpenCode** in AI Director, then copy the tunnel URL |
| URL (bearer client) | `http://127.0.0.1:8030/mcp` |
| Authentication | **No authentication** for the temporary tunnel |

The tools are **not** in the studio connector. Once the OpenCode connector is
connected, ask:

```text
Use opencode_ask to inspect D:\bro\CartoonStudio\workflows and add a test for
sdxl_inpaint. Wait 45 seconds, then poll with opencode_task and report the diff.
```

```text
Use opencode_ask with session_id <id> to run: python -m pytest -q
Then report the result. Do not change files unless I approve.
```

If a result says `waiting_for_permission`, read `pending_permissions`, then call
`opencode_permission` with the request id. Use `reject` unless you understand the
action. `always` creates a durable project rule.

The **Connect OpenCode** button in AI Director starts the 8030 tunnel, switches only
the OpenCode bridge to no-auth mode, and restores bearer mode when you disconnect.
It is separate from the studio **Connect ChatGPT** button.

Add the connector, scan tools, and enable it. The OpenCode connector shows exactly
four tools.

## Using it from a shell

Start the OpenCode MCP server, create an `opencode` token, and point the CLI at
8030:

```powershell
.\scripts\start_mcp_opencode.bat
$body = '{"name":"opencode-cli","scopes":"opencode"}'
$resp = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/v1/mcp/tokens `
  -ContentType "application/json" -Body $body
$env:MCP_TOKEN = $resp.token
$env:MCP_URL = 'http://127.0.0.1:8030/mcp'
```

```powershell
@'
{"message":"Reply with exactly: OK. Do not modify files.","wait_seconds":40,
 "model":"opencode-go/beam-free","title":"Bridge test"}
'@ | .\backend\.venv\Scripts\python.exe .\scripts\mcp_call.py call opencode_ask -
```

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\mcp_call.py call opencode_task '{"session_id":"ses_..."}'
.\backend\.venv\Scripts\python.exe .\scripts\mcp_call.py call opencode_sessions '{"limit":5}'
```

Use `-` as the arguments to read JSON from stdin; this avoids PowerShell quoting
problems with spaces and quotes.

## Continue an existing session

By default `opencode_ask` creates a new session. To continue one specific session
(for example the one you are using in the TUI), set:

```env
OPENCODE_BRIDGE_SESSION_ID=ses_e43976869ffe7bEeJp7hFszSWm
```

Then every `opencode_ask` call without an explicit `session_id` continues that
session. `delivery` defaults to **queue**, so the message waits for the current
turn to finish instead of interrupting it.

- The response includes `message_id`. Pass it to `opencode_task` to track exactly
  that message; without it, polling may read the previous turn.
- A queued message reports `status: "queued"` until it is delivered.
- Remove `OPENCODE_BRIDGE_SESSION_ID` (or set it empty) and restart MCP to return
  to creating fresh sessions.
- Find an ID with `opencode_sessions`, the OpenCode UI, or
  `opencode api get /api/session/active`.

Warning: a shared session receives messages from both clients. Use `queue`
delivery, avoid sending from ChatGPT while you are actively typing in the TUI,
and expect the conversation history to include both sides.

## Session behaviour

- New sessions are created in `OPENCODE_BRIDGE_DIR` (`D:\bro` by default).
- Reusing a `session_id` continues that agent conversation with full context.
- Each call returns a normal OpenCode session that also appears in the TUI.
- The bridge does **not** stream tokens; it polls the session and returns the final
  assistant text plus tool names.
- OpenCode permissions and `opencode.jsonc` still apply. The bridge does not
  auto-approve anything.

## Security

`opencode_ask` lets ChatGPT start a coding agent that can edit files and run shell
commands under your Windows account. Treat it like Desktop Commander:

- Keep the MCP connector authenticated or behind a short-lived tunnel.
- Use a dedicated session for ChatGPT; do not point it at a session you are using.
- Review `pending_permissions` before approving.
- Prefer a free/local model for exploratory tasks and a stronger model only when
  needed.
- Revoke unused MCP tokens.
- Do not expose the MCP server publicly with `MCP_AUTH_MODE=none` beyond a test.

## Limitations

- Asynchronous by design. Long tasks must be polled.
- No token-level streaming; final text only.
- The bridge cannot see ChatGPT's conversation, only the message you send.
- Concurrent tasks in the same session are not queued by the bridge; OpenCode
  decides how to handle them.
- Model quality varies widely. `beam-free` is useful for orchestration but may be
  weak for complex code edits.
