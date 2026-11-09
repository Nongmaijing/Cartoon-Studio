# Data Flow

## 1. In-app AI Director

```
User message
  -> POST /api/v1/ai/conversations/{id}/messages
  -> AIDirector.run_turn()
  -> OpenAI Responses API (tools = shared registry)
  -> function_call
  -> ToolRegistry.execute()
  -> shared service
  -> SQLite / ComfyUI / Kokoro / FFmpeg
  -> tool result
  -> Responses API continuation (previous_response_id)
  -> assistant message + tool records
  -> ai_messages / ai_tool_executions
```

The SSE endpoint (`/messages/stream`) emits status, tool execution, assistant message and error events. It streams progress, not token-by-token deltas.

## 2. ChatGPT / MCP

```
ChatGPT custom connector
  -> HTTPS MCP /mcp
  -> Bearer token verifier
  -> FastMCP tool function
  -> ToolRegistry.execute()
  -> same shared service
  -> same database / queue / providers
  -> structured result
```

The MCP server does not access SQLite directly for production logic; it goes through the tool registry and services.

## 3. Character generation

```
UI / AI tool / MCP
  -> character_service.generate_sheet()
  -> provider registry: image/comfyui
  -> submit_image()
  -> existing jobs queue
  -> ComfyUI
  -> output copied to outputs/<project>/<job>/
  -> assets + media_links
```

## 4. Scene production

```
production_orchestrator.start_production()
  -> production_runs + production_tasks
  -> worker
  -> SCENE_IMAGE task -> scene_service.generate_scene_image()
  -> AUDIO task       -> dialogue_service.generate_scene()
  -> ANIMATION task   -> scene_service.animate_scene() (optional)
  -> ASSEMBLY task    -> episode timeline + episode_export
  -> episode output asset
```

Each task persists status, attempts, job ID, result and error. Failed tasks retry. Paused runs stop between tasks. Restart recovery resets interrupted running tasks and resumes the worker.

## 5. Approval and memory

```
approve_scene / approve_character / approve_script
  -> scenes/characters/episodes approval fields
  -> scene_reviews / character_versions
  -> audit_logs
  -> both UI and MCP read the same rows
```

Approved references are not overwritten. Regeneration creates new assets/versions.

## 6. Final render

```
episode timeline (segments + audio + settings)
  -> episode_export.start_export()
  -> per-segment FFmpeg render (zoom/pan/transition)
  -> concat
  -> audio mix (dialogue/music/SFX)
  -> soft subtitles
  -> unique MP4 + SRT asset
  -> episode output_url
```
