# Production Scripts

Small, dry-run-first helpers for the Little Wonder Village pilot. They call the
live Cartoon Studio API or the project database and never overwrite accepted
assets.

## Background drafts

```powershell
cd D:\bro\CartoonStudio
backend\.venv\Scripts\python.exe scripts\generate_pilot_backgrounds.py `
  --project-id 16556b67d331 --dry-run

backend\.venv\Scripts\python.exe scripts\generate_pilot_backgrounds.py `
  --project-id 16556b67d331 `
  --output C:\Users\pagau\AppData\Local\Temp\opencode\background_drafts
```

Creates missing background records for the Old Oak, garden, village path and
stream, then generates one 16:9 draft each. Re-running reuses records but adds a
new image instead of overwriting an existing one.

## Draft storyboard

```powershell
cd D:\bro\CartoonStudio
backend\.venv\Scripts\python.exe scripts\create_pilot_storyboard.py `
  --project-id 16556b67d331 --episode-id 073b5d75f0c4 --dry-run
```

Refuses to run when the project already has scenes. Creates 4 draft scenes from
the existing script, maps backgrounds by scene title, and links cast members.

## Missing dialogue

```powershell
backend\.venv\Scripts\python.exe scripts\add_pilot_dialogue.py `
  --project-id 16556b67d331 --episode-id 073b5d75f0c4 --dry-run
```

Idempotently adds dialogue lines to scenes that do not have any yet. It does not
approve the script, scenes or episode.

## Pilot preflight

```powershell
backend\.venv\Scripts\python.exe scripts\pilot_preflight.py `
  --project-id 16556b67d331 --episode-id 073b5d75f0c4
```

Read-only. Reports script approval, per-character approval/canonical state, scene
counts, background availability, keyframes, and gate readiness.

## Script validation

```powershell
backend\.venv\Scripts\python.exe scripts\validate_script.py `
  --path docs\operations\S01E01_SCRIPT_V2.json `
  --project-id 16556b67d331 --target-minutes 7
```

Read-only. Checks four-scene structure, cast, backgrounds, dialogue fields,
runtime estimate, scene durations and preschool-safe vocabulary.

## Script and shot-plan tooling

```powershell
# Validate a script file (structure, cast, runtime, balance, safety)
backend\.venv\Scripts\python.exe scripts\validate_script.py `
  --path docs\operations\S01E01_SCRIPT_V3.json `
  --project-id 16556b67d331 --target-minutes 7

# Validate the 16-shot plan against the script and DB
backend\.venv\Scripts\python.exe scripts\validate_shot_plan.py `
  --path docs\operations\S01E01_SHOT_PLAN_V1.json `
  --script docs\operations\S01E01_SCRIPT_V3.json `
  --project-id 16556b67d331

# Regenerate the human-readable shot-plan markdown
backend\.venv\Scripts\python.exe scripts\render_shot_plan_md.py
```

## Vector draft tooling

```powershell
backend\.venv\Scripts\python.exe scripts\build_vector_character_drafts.py
backend\.venv\Scripts\python.exe scripts\build_vector_character_drafts_v2.py
backend\.venv\Scripts\python.exe scripts\validate_vector_drafts.py --manifest manifest.json
backend\.venv\Scripts\python.exe scripts\validate_vector_drafts.py --manifest manifest_v2.json
```

Builds editable SVG groups and matching PNG previews for Pip and Ollie under
`docs/operations/vector_drafts/`. Nothing is registered or canonicalized.

## Script revision API tests

```powershell
cd D:\bro\CartoonStudio\backend
.\.venv\Scripts\python.exe -m pytest tests\test_script_revisions.py -q
```

The API is implemented but migration 4 is not live; see
`docs/operations/SCRIPT_REVISION_API.md`.

## Model downloads

```powershell
cd D:\bro\CartoonStudio
backend\.venv\Scripts\python.exe scripts\download_vetted_models.py --dry-run
backend\.venv\Scripts\python.exe scripts\download_vetted_models.py --wait
```

Downloads only the vetted `model_download_service` sources, checks SHA256 and
resumes partial files. See `docs/operations/MODEL_INVENTORY.md`.

Optional control/identity/upscale weights:

```powershell
backend\.venv\Scripts\python.exe scripts\download_optional_models.py --dry-run
backend\.venv\Scripts\python.exe scripts\download_optional_models.py --accept-licenses
backend\.venv\Scripts\python.exe scripts\download_optional_models.py --verify
```

Hashes must be official HuggingFace LFS digests (API `siblings[].lfs.sha256`),
never CDN `ETag` values.

## Custom nodes

`ComfyUI_IPAdapter_plus` is installed at
`...\ComfyUI-Installs\Waikhom Studio\ComfyUI\custom_nodes\ComfyUI_IPAdapter_plus`
(pinned commit `a0f451a5`, no extra Python deps). The `ipadapter` model category
is exposed through a junction at `<ComfyUI>\models\ipadapter` because Comfy
Desktop's generated path map does not list that non-core folder. See
`docs/operations/MODEL_INVENTORY.md`.

## Gate rules

- Dry-run before mutating.
- Never delete or overwrite accepted assets.
- Drafts remain drafts until reviewed.
- Character approval and canonical promotion are separate, human-owned gates.
