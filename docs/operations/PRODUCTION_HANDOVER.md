# Production Handover — Little Wonder Village

## Ownership

| Responsibility | Owner |
|---|---|
| Creative direction and series vision | **ChatGPT** |
| Story development, scripts and dialogue | **ChatGPT** |
| Technical implementation and debugging | **OpenCode** |
| Character and asset consistency | **ChatGPT + OpenCode** |
| Image, animation and audio production | **Cartoon Studio** (operated by OpenCode) |
| Technical testing and production diagnostics | **OpenCode** |
| Creative and quality review | **ChatGPT** |
| Final supervision and major approvals | **Human supervisor** |

OpenCode does not overrule creative decisions. If a technical constraint conflicts with
a creative request, OpenCode reports the constraint and proposes options; ChatGPT
decides the creative direction; the human decides major approvals.

The supervisor is not expected to operate the UI day to day. OpenCode drives the
studio and reports decisions that need sign-off.

## Decision rights

Creative direction, story, scripts, dialogue and quality judgement belong to ChatGPT.
OpenCode implements that direction, provides technical evidence, and flags conflicts
instead of making silent creative changes.

OpenCode may proceed without asking on:

- code fixes, tests, docs, refactors that preserve behavior
- generating draft assets for review
- running local models already installed
- building shot plans, storyboards and scripts as drafts
- validating workflows and running read-only checks

Explicit approval is required for:

- approving characters, canonical references or final episode cuts
- installing or downloading new models or weights
- paid API usage beyond configured defaults
- deleting project data, assets, migrations or git history
- publishing, uploading or sharing episodes publicly
- leaving a public no-auth tunnel open beyond an active working session

If a required action is blocked by a missing approval, record the blocker and
continue with independent work.

## Collaboration protocol

ChatGPT reaches the agent through the standalone OpenCode bridge:

```text
MCP: http://127.0.0.1:8031/mcp
UI:  http://127.0.0.1:8040
```

Tools: `opencode_ask`, `opencode_task`, `opencode_sessions`, `opencode_permission`.

Rules:

- ChatGPT proposes; OpenCode implements and verifies.
- One writer at a time. ChatGPT must not edit the same files concurrently.
- OpenCode reports commit hashes, test results and generated asset IDs.
- Draft outputs are never described as approved.
- No silent fallback from SDXL to SD 1.5; failures are reported with the real error.

## Current state (2026-11-10)

- Project: `16556b67d331` — Children Stories — Little Wonder Village
- Episode: `073b5d75f0c4` — S01E01 — The Little Seed — `draft`
- Scenes: 0
- Characters: 6, all `draft`, none with a canonical reference
- Assets: 8 images, 0 audio, 0 video
- Image stack: DreamShaper XL 1.0, SDXL inpainting, 4× UltraSharp
- Video: Wan 2.2 (short low-resolution shots)
- Voice: Kokoro; ASR: faster-whisper small
- Character prompt composition fixed and committed (`2fd5260`)
- Studio and bridge MCP servers are separate; scoped bearer tokens

## Milestones

1. **Character lock pack** — regenerate turnarounds with the fixed prompts, select
   one canonical reference per character, record approval or rejection.
2. **Episode 1 blueprint** — lock script, scene list, shot plan and timing for a
   7-minute episode.
3. **Keyframe package** — generate and review scene keyframes against approved
   character references.
4. **Audio package** — dialogue, music, SFX, subtitle/ASR alignment.
5. **Animation and assembly** — short Wan shots where needed; timeline assembly.
6. **Final QC and 1080p export** — continuity, audio mix, subtitle check, export.

## Reporting

- OpenCode posts a short status after each milestone or blocker.
- Every claim is backed by a job ID, asset ID, test result or commit.
- Public tunnels are reported explicitly with their current state.
