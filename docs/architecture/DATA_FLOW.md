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

## 7. Image model resolution

```
UI / AI tool / MCP / production task
  -> submit_image(purpose=character|background|scene|expression|pose)
  -> model_config_service.resolve_image_model()
       -> selected architecture (SDXL by default, SD 1.5 fallback)
       -> checkpoint / VAE / LoRA
       -> workflow and preset
  -> jobs._run_job()
       -> apply checkpoint override
       -> validate VAE / LoRA availability
       -> build_prompt()
       -> apply_vae() / apply_lora() graph injection
       -> ComfyUI
```

The Model Studio reads the same configuration. It never downloads files; it only scans model directories and reports readiness. If no SDXL checkpoint is configured, `resolve_image_model` falls back to SD 1.5 and records the fallback reason in the job parameters.
