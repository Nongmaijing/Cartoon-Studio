# MCP Tools

The MCP server exposes the same 56 studio tools as the AI Director registry, plus
4 OpenCode bridge tools (`opencode_ask`, `opencode_task`, `opencode_sessions`,
`opencode_permission`) — 60 tools total.

## OpenCode bridge

These tools let ChatGPT ask a local OpenCode agent to inspect code, create
workflows, run tests, and make changes through the OpenCode HTTP API. See
`docs/integration/OPENCODE_BRIDGE.md` for models, permissions and examples.

- `opencode_ask` — start a task; optionally wait up to 120 seconds.
- `opencode_task` — poll a task and read the assistant text/tools.
- `opencode_sessions` — list recent sessions.
- `opencode_permission` — answer a pending permission request (`once`, `always`, `reject`).

## Calling these tools from Desktop Commander or a shell

Desktop Commander is a **shell**, not a studio client: it does not merge the Cartoon
Studio tool catalog into ChatGPT. To let ChatGPT use the studio tools while keeping the
MCP server local and bearer-authenticated, use the included wrapper:

```text
scripts/mcp_call.py
```

It opens a streamable-HTTP MCP session, authenticates with `MCP_TOKEN`, calls one tool,
and prints the result. No public tunnel is required.

### 1. Create a token

```powershell
$body = '{"name":"desktop-commander","scopes":"production"}'
$resp = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8010/api/v1/mcp/tokens `
  -ContentType "application/json" -Body $body
$resp.token      # shown once
$resp.id         # revoke later with /tokens/{id}/revoke
```

Add it to `D:\bro\CartoonStudio\.env`:

```env
MCP_URL=http://127.0.0.1:8020/mcp
MCP_TOKEN=the-raw-token
```

Restart the backend only if you want the backend's own status view to show the token;
the wrapper reads `.env` directly.

### 2. Use it

```powershell
cd D:\bro\CartoonStudio
.\backend\.venv\Scripts\python.exe .\scripts\mcp_call.py tools
.\backend\.venv\Scripts\python.exe .\scripts\mcp_call.py call list_projects "{}"
.\backend\.venv\Scripts\python.exe .\scripts\mcp_call.py call get_episode_status "{\"episode_id\":\"...\"}"
```

The first argument can also be the tool name directly:

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\mcp_call.py list_projects "{}"
```

Expensive or destructive tools require `confirm=true` in the arguments:

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\mcp_call.py call generate_scene_image "{\"scene_id\":\"...\",\"confirm\":true}"
```

### 3. Ask ChatGPT to use it

In a ChatGPT chat with Desktop Commander enabled:

```text
Run this exact command in D:\bro\CartoonStudio and show me the output:
backend\.venv\Scripts\python.exe scripts\mcp_call.py call list_projects "{}"
```

For studio work, always prefer `scripts/mcp_call.py` over raw shell commands. Use shell
only for things the MCP tools do not cover.

### 4. Safety

- The token is a production credential. Keep it in `.env`; never paste it into a chat.
- Restrict Desktop Commander's `allowedDirectories` to `D:\bro`.
- Review every queued generation; the wrapper reports the same job IDs as the UI.
- Revoke unused tokens with `POST /api/v1/mcp/tokens/{id}/revoke`.
- Do not expose port 8020 publicly with `MCP_AUTH_MODE=none` unless you are actively
  testing and will disconnect immediately.

## Direct ChatGPT connector instead

If you want ChatGPT to see the tools natively (without the wrapper), use the built-in
**AI Director → Connect ChatGPT** flow. It starts a temporary tunnel in no-auth mode, so
only use it for a short session and click **Disconnect & secure** afterwards. See
`docs/integration/CHATGPT_CONNECTION.md`.

## Projects
- `list_projects`
- `create_project`
- `get_project_details`
- `update_project`
- `archive_project`

## Episodes
- `list_episodes`
- `create_episode`
- `get_episode_details`
- `update_episode`
- `delete_episode` (confirm)
- `get_episode_status`

## Characters
- `list_characters`
- `create_character`
- `update_character`
- `get_character_details`
- `generate_character_sheet` (confirm)
- `get_character_references`
- `approve_character`

## Story and script
- `generate_story`
- `generate_script`
- `revise_script`
- `approve_script`
- `create_storyboard`
- `get_storyboard`

## Scenes
- `list_scenes`
- `get_scene_details`
- `update_scene`
- `generate_scene_image` (confirm)
- `regenerate_scene` (confirm)
- `approve_scene`
- `reject_scene`

## Animation
- `animate_scene` (confirm)
- `regenerate_animation` (confirm)
- `get_animation_preview`
- `approve_animation`

## Audio
- `generate_dialogue`
- `generate_voice`
- `generate_sound_effects`
- `generate_background_music`
- `get_audio_status`

## Production
- `start_production` (confirm)
- `pause_production`
- `resume_production`
- `cancel_production` (confirm)
- `get_production_status`
- `get_production_queue`
- `get_job_status`
- `get_generation_logs`

## Quality control
- `review_scene`
- `review_episode`
- `get_quality_report`
- `regenerate_failed_scenes` (confirm)

## Final output
- `render_episode` (confirm)
- `get_episode_preview`
- `export_episode` (confirm)
- `get_episode_assets`

## Common result shape

```json
{
  "ok": true,
  "tool": "get_scene_details",
  "scene": { "...": "..." }
}
```

Errors:

```json
{
  "ok": false,
  "tool": "get_scene_details",
  "error": "Scene not found.",
  "code": "not_found",
  "status_code": 404
}
```

Confirmation:

```json
{
  "ok": false,
  "tool": "start_production",
  "confirmation_required": true,
  "message": "This operation is expensive or destructive..."
}
```

## Resources

- `cartoon://projects`
- `cartoon://projects/{project_id}`
- `cartoon://episodes/{episode_id}`
- `cartoon://production/{run_id}`

## Prompts

- `plan_episode`
- `review_scene`
