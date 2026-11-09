# OpenAI API Setup

## Environment

Add to `D:\bro\CartoonStudio\.env`:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=your-available-model-id
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MAX_TOOL_ROUNDS=8
```

`OPENAI_MODEL` must be a model available to your account. The integration does not hardcode a permanent model ID. Check availability with the OpenAI models API or your account dashboard.

## Verify

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/v1/ai/health
```

Expected when configured:

```json
{
  "status": "ok",
  "openai": {"configured": true, "api_key_present": true, "model": "..."},
  "model": "..."
}
```

When not configured, the AI Director returns HTTP 503 with a clear message. The MCP server and production tools remain usable.

## Use the AI Director

1. Open `/director`.
2. Select the active project and episode.
3. Ask for a plan, story, script, storyboard or production action.
4. The Director uses the Responses API with the shared tool registry.
5. Expensive actions require explicit confirmation.
6. Job/asset IDs in tool results are authoritative.

## What the Director can do

- Inspect projects, characters, episodes and scenes.
- Create/update characters and episodes.
- Generate stories/scripts/storyboards.
- Generate character sheets, scene images and animations.
- Generate dialogue/audio/music/SFX.
- Start/pause/resume/cancel production runs.
- Review scenes/episodes and regenerate failed scenes.
- Render/export episodes.

## Cost and safety

- Image/video generation is the expensive part; text generation is cheaper.
- Confirmation gates protect expensive/destructive actions.
- Cloud image generation is separate and disabled unless `ALLOW_CLOUD_GENERATION=true`.
- The Director never claims completion until a backend job reports completed.
- Secrets are never returned in API/tool responses.

## Responses API implementation

`app/ai/openai_director.py` uses the official `openai` Python SDK:

- `AsyncOpenAI`
- `client.responses.create(...)`
- function tools from `ToolRegistry.openai_tools()`
- `previous_response_id` continuation
- `function_call_output` items
- persisted response IDs in `ai_conversations.last_response_id`

The loop is covered by a mocked test (`tests/test_ai_director_mock.py`). A live call requires your API key and a valid model ID.
