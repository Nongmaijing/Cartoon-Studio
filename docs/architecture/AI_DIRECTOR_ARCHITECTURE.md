# AI Director Architecture

## Purpose

A conversational production controller that can plan and execute real Cartoon Studio work.

## Components

- `app/ai/openai_director.py` — Responses API loop, tool calls, previous_response_id.
- `app/ai/tool_registry.py` — 56 shared tools, validation, confirmation, idempotency, audit.
- `app/ai/conversation_manager.py` — persisted conversations/messages/context snapshots.
- `app/ai/context_manager.py` — project/episode/character/scene/job context and system prompt.
- `app/ai/llm_text.py` — structured story/script JSON generation.
- `app/routers/ai_director.py` — REST + SSE endpoints.

## Responses API loop

1. Load conversation and context.
2. Send system prompt, recent history and user message to the Responses API with the shared tool schemas.
3. If the model returns function calls:
   - validate arguments,
   - enforce confirmation/permissions,
   - execute through the shared services,
   - append `function_call_output` items,
   - continue with `previous_response_id`.
4. Save the assistant message, tool records, response ID and context snapshot.
5. Return a structured result.

## Confirmation policy

- Image/video generation, production start/cancel, failed-scene regeneration, episode delete and render require `confirm=true`.
- If a tool is called without confirmation, it returns `confirmation_required` and does not execute.
- The Director asks the user for explicit approval; only then should the model call again with `confirm=true`.

## Context awareness

The context includes:

- active project and memory,
- approved/draft characters,
- episodes and production state,
- scenes, cast, keyframes, videos, dialogue,
- production runs and recent jobs,
- integration/provider flags.

## Persistence

- `ai_conversations` — project/episode/model/response ID/context.
- `ai_messages` — user/assistant messages and tool calls.
- `ai_tool_executions` — arguments, results, status, errors, idempotency key.
- `ai_context_snapshots` — context snapshot per turn.

## Streaming

`POST /api/v1/ai/conversations/{id}/messages/stream` uses SSE and emits:

- `status`
- `tool_execution`
- `assistant_message`
- `error`
- `done`

This is progress streaming. Token-level deltas are not currently emitted; the final assistant message arrives as one event.

## No OpenAI key

The Director returns HTTP 503 with:

```
OpenAI is not configured. Set OPENAI_API_KEY and OPENAI_MODEL.
```

The MCP server and production tools remain usable without OpenAI.
