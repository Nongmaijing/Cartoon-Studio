# Episode Production Pipeline — Little Wonder Village

## Purpose

A repeatable gate-based path from character validation to a finished 7-minute pilot.
No gate is skipped, and no draft is treated as approved.

## Gate 0 — Canon inputs

- Series Bible in `projects.memory_json`.
- Character records: name, description, appearance, clothing, style.
- Approved canonical references where they exist (currently none).
- Episode `073b5d75f0c4` — S01E01 — The Little Seed.

## Gate 1 — Character visual validation

1. Generate four-view turnaround drafts with the fixed prompts.
2. Review each view for:
   - one view per image, full body, head-to-toe;
   - correct species and age;
   - exact wardrobe and palette;
   - no crop, collage, extra characters or text.
3. Run a local VLM identity/wardrobe review against the profile.
4. Compare front / three-quarter / side / back for consistency.
5. Only after review, select one front image as canonical **draft** reference.
6. Do not approve the character yet.

## Gate 2 — Canonical references

- Set a canonical only from a reference/pose asset linked to that character.
- The asset must be an image in the same project.
- Clearing or changing a canonical on an approved character is blocked.
- Approval additionally requires a valid canonical reference.

## Gate 3 — Recurring backgrounds

- Generate draft backgrounds for: The Old Oak, the garden/path, the stream,
  and any interior needed by the pilot.
- 16:9 SDXL background workflow, no characters.
- Review for consistent palette, clean staging and reusable composition.
- Promote only after repeating the same background successfully across two shots.

## Gate 4 — Pilot script and storyboard

- Use the existing four-scene pilot story as the draft script.
- Create scenes and dialogue from the script; do not overwrite the story JSON.
- Review dialogue length against the 7-minute runtime target.
- Script approval is a separate explicit gate.

## Gate 5 — Keyframes

- Generate one keyframe per shot with approved character references where possible.
- Use scene-specific staging, camera and action.
- Run continuity checks against the canonical references.
- Reject and regenerate failed frames; never overwrite accepted assets.

## Gate 6 — Animation

- Use Wan 2.2 for short, bounded shots only (current 6 GB limit).
- Keep dialogue-heavy scenes as held keyframes unless animation is clearly safe.
- Verify each shot for flicker, morphing and identity drift.

## Gate 7 — Dialogue, music, SFX and subtitles

- Kokoro for dialogue; local SFX/music.
- Transcribe or align dialogue; generate subtitles.
- Check levels, pronunciation and timing before assembly.

## Gate 8 — Edit and render

- Build the episode timeline.
- Export 1080p H.264 with stereo audio and soft subtitles.
- Verify duration, sync, loudness and subtitle placement.
- Final episode approval is separate from technical export success.

## Gate 9 — QA and release

- Watch the full episode.
- Check story clarity, continuity, character consistency and audio mix.
- Record known limitations.
- Publish only after explicit human approval.

## Operating rules

- Every generated asset gets a new ID; never overwrite an accepted asset.
- Every production mutation is checked against the live DB/MCP first.
- Every job is verified by status, assets, dimensions and model.
- No fallback is silent; SDXL failures are reported as SDXL failures.
- Drafts stay drafts until an explicit quality gate passes.
- Tunnels are temporary and should use expiry; no long-lived no-auth tunnel.
