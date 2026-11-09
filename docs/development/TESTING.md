# Testing

## Run

```powershell
cd D:\bro\CartoonStudio\backend
.\.venv\Scripts\python.exe -m pytest -q
```

Current result: **42 passed**.

## Test files

| File | Covers |
|---|---|
| `tests/test_workflow_engine.py` | Legal/illegal production transitions, pause/resume, stage order |
| `tests/test_provider_registry.py` | Provider registry, availability, cloud opt-in |
| `tests/test_tool_registry.py` | Unknown tools, validation, shared reads, idempotency, confirmation gates, manual tool endpoint argument handling |
| `tests/test_production_mock.py` | Mocked scene production task execution and run completion |
| `tests/test_ai_director_mock.py` | Mocked OpenAI Responses tool loop, persistence, previous_response_id |
| `tests/test_mcp_config.py` | Transport host/origin allowlist, no-auth opt-in guard, invalid auth mode rejection |
| `tests/test_mcp_tunnel.py` | Cloudflared URL parsing, confirmation gate, inactive tunnel status shape |
| `tests/test_model_config.py` | SDXL/SD1.5 architecture detection, fallback behavior, dimension guard, LoRA/VAE graph injection, recommendations |
| `tests/test_character_sheet_mock.py` | Turnaround 4-view queue, expression 8-view queue, reference approval gate, single reference upload |
| `tests/test_production_services.py` | Resource estimates, LLM JSON parsing, viseme units, lip-sync cues, shot plan, production report, story continuity warnings |

## Mocking policy

- Tests never call ComfyUI or OpenAI.
- The production test mocks image generation and job waiting.
- The AI Director test injects a fake `AsyncOpenAI` client and asserts the function-call loop.
- A temporary SQLite database is used per test.

## Production studio live checks

Performed on the RTX 4050 6 GB machine:

| Check | Result |
|---|---|
| Production registry | 7 ready, 3 partial, 1 blocked |
| Resource status | 6.0 GB VRAM, 31.71 GB RAM |
| Free VRAM | 4.9 GB free after unload |
| Local LLM story | Qwen3 8B, 78 s, 4 scenes |
| Local VLM review | Qwen2.5-VL 3B, 30.5 s |
| Lip-sync cues | 43 cues for a 2.75 s line |
| Shot plan | 1 shot, 19.4 s estimate |
| SD 1.5 image | 384×384, asset `514163b98ec9` |
| Wan image-to-video | 320×192, 5 frames, 16.75 s, peak 3333 MB |
| 4× upscale | 384→1536, 5.77 s, peak 2471 MB |
| Kokoro dialogue | 1.75 s WAV, asset `f9726f170b8f` |
| SFX/music | assets `5e0aca751713`, `9462863c6639` |
| 1080p export | 1920×1080 H.264/AAC/mov_text, 6.0 s, asset `8ce8ace5a449` |
| SDXL | blocked — no checkpoint |
| Image editing / IPAdapter / ControlNet | blocked — missing weights |
| ASR / lip-sync rendering | blocked — missing models |

## Manual integration checks
1. Backend health: `/api/health`, `/api/v1/health`.
2. MCP health: `http://127.0.0.1:8020/health`.
3. MCP bearer-token client: `list_tools` and `list_projects`.
4. Shared state: create a project/character through MCP and read it through `/api`.
5. Reverse direction: create a scene through `/api` and read it through MCP.
6. Confirmation gate: `start_production` without `confirm=true` returns `confirmation_required`.
7. AI Director without key: returns a clear 503.
