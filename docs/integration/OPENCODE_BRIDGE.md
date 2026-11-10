# OpenCode Bridge (ChatGPT → OpenCode agent)

## What it is

Four MCP tools added to the Cartoon Studio MCP server so ChatGPT can ask a local
OpenCode agent to inspect code, create workflows, run tests, and make changes.

The bridge calls the **OpenCode HTTP API** through the `opencode api` command, so it
uses the same running service and authentication as the TUI. No second OpenCode
instance is started.

```text
ChatGPT
  └─ MCP connector (8020)
       ├─ 56 Cartoon Studio tools
       └─ 4 OpenCode tools
            └─ opencode api → local OpenCode service → agent session in D:\bro
```

## Tools

| Tool | Purpose |
|---|---|
| `opencode_ask` | Start a task: `message`, optional `session_id`, `title`, `model`, `wait_seconds` |
| `opencode_task` | Poll a task: `session_id` |
| `opencode_sessions` | List recent OpenCode sessions: `limit` |
| `opencode_permission` | Answer a pending permission request: `session_id`, `request_id`, `decision` (`once`, `always`, `reject`) |

`opencode_ask` returns immediately when `wait_seconds` is 0. With the default 45 it
waits up to 45 seconds for a result, then returns `status: "running"` and the
`session_id` to poll with `opencode_task`.

Status values:

- `running`
- `completed`
- `failed`
- `waiting_for_permission`

A completed result includes `text`, `tools`, `message_count`, `directory` and
`pending_permissions`.

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

The tools are part of the existing Cartoon Studio MCP connector. Once the
connector is connected, ask:

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

## Using it from a shell

Start MCP in bearer mode, create a token, and use `scripts/mcp_call.py`:

```powershell
cd D:\bro\CartoonStudio
$body = '{"name":"opencode-cli","scopes":"production"}'
$resp = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/v1/mcp/tokens `
  -ContentType "application/json" -Body $body
$env:MCP_TOKEN = $resp.token
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
