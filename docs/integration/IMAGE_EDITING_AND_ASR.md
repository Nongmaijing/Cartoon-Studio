# Image Editing, Identity Checks and Speech Recognition

## Purpose

This document covers three capabilities added after the SDXL checkpoint validation:

1. **Image editing** — SDXL whole-image refinement and masked inpainting.
2. **Character identity checks** — automated comparison of a generated image against an
   approved canonical reference using the local vision model.
3. **Speech recognition** — local audio transcription with SRT export via faster-whisper.

All three run locally. No cloud API is required.

---

## Image editing

### Endpoints

```text
GET  /api/v1/editing/status
POST /api/v1/editing/edit
```

`POST /api/v1/editing/edit` body:

| Field | Type | Notes |
|---|---|---|
| `source_asset_id` | string | Image asset to edit; must belong to a project |
| `prompt` | string | What should change; keep unchanged details explicit |
| `mask_asset_id` | string \| null | White-on-black PNG mask; enables masked inpainting |
| `negative_prompt` | string \| null | Defaults to a cartoon-safe negative prompt |
| `seed` | int \| null | Fixed seed for reproducibility |
| `steps` | int \| null | Defaults to the SDXL preset (28) |
| `cfg` | float \| null | Defaults to the SDXL preset (6.0) |
| `denoise` | float | Whole-image mode only. Default 0.55; masked mode forces 1.0 |
| `width`, `height` | int \| null | Defaults to the source size, clamped to `max_pixels` |

### Two modes

**Whole-image edit (`sdxl_img2img`)**
- Re-renders the entire frame at the requested denoise.
- Works without extra models.
- Suitable for style refinement, lighting, line cleanup and small corrections.
- It is **not** an instruction-following editor. At low denoise it preserves the source but
  may ignore the requested change; at high denoise it follows the prompt but also alters the
  character. To replace a background or remove an object, use a mask.

**Masked edit (`sdxl_inpaint`)**
- Requires an SDXL inpainting checkpoint and a white-on-black mask image.
- White areas are regenerated; black areas are kept.
- `VAEEncodeForInpaint` grows the mask by 8 px to blend the seam.
- Uses the same 6 GB-safe tiled VAE decode.

### Installing the SDXL inpainting checkpoint

Source: `diffusers/stable-diffusion-xl-1.0-inpainting-0.1`
Licence: **CreativeML Open RAIL++-M** (`openrail++`), not gated.

The repository is Diffusers format. It was downloaded as fp16 components (6.46 GB) to:

```text
D:\bro\ComfyUI\Models\diffusers\sdxl-inpainting-0.1
```

and converted with Hugging Face’s `convert_diffusers_to_original_sdxl.py` to:

```text
D:\bro\ComfyUI\Models\checkpoints\SDXL_Inpainting_0.1.safetensors
```

The converted UNet keeps `in_channels = 9` (`conv_in` shape `[320, 9, 3, 3]`), which is what
ComfyUI expects for an inpainting checkpoint.

Select it in the model config:

```json
"models": {
  "checkpoints": {
    "sd15": "DreamShaper_8_pruned.safetensors",
    "sdxl": "DreamShaperXL_1.0.safetensors",
    "sdxl_inpaint": "SDXL_Inpainting_0.1.safetensors"
  }
}
```

If `sdxl_inpaint` is unset, the service falls back to the first ComfyUI-visible checkpoint
whose name contains `inpaint` and `xl`/`sdxl`. If none is found, masked edits return a clear
error and whole-image editing remains available.

### Mask format

- PNG, same aspect ratio as the source (it is resized automatically).
- White = regenerate, black = keep.
- The `red` channel is read.
- A soft edge reduces visible seams.

### Measured test (whole-image mode)

| Item | Result |
|---|---|
| Source | Leo front view `343185cb8b15` (1024×1024) |
| Prompt | Replace background with sunrise meadow, keep character |
| Denoise | 0.35 |
| Job | `2ed8fb8d20e5` |
| Time | 36.4 s |
| Peak VRAM | 6118 MB of 6144 MB |
| Output | asset `1a75110352d7`, 1024×1024 |
| Visual result | Character preserved; background **not** replaced |

This confirms the expected limitation: global img2img at 0.35 is a refinement pass, not a
background-replacement tool. Masked inpainting is the correct path for that request.

### Measured test (masked mode)

| Item | Result |
|---|---|
| Source | Leo front view `343185cb8b15` (1024×1024) |
| Mask | asset `3ffc3734fb7f`, white rounded rectangle over the top-left 360×360 px |
| Prompt | Small bright red party balloon, clean outlines, flat colors |
| Checkpoint | `SDXL_Inpainting_0.1.safetensors` |
| Job | `6771e5ee82da` |
| Workflow | `sdxl_inpaint` |
| Time | 30.7 s |
| Peak VRAM | 5570 MB of 6144 MB |
| Output | asset `c77daf17c8eb`, 1024×1024 |
| Visual result | Only the masked region changed; unmasked areas were preserved |

The test mask overlapped the front-view character’s head, so the fill is a soft rectangle
rather than a clean balloon, and a faint mask boundary is visible at the edge. That is a
mask-placement/quality result, not a pipeline failure. For production edits, mask only the
background or object to change, keep the mask off the character, and use a soft edge.

---

## Character identity checks

### Endpoint

```text
POST /api/characters/{character_id}/consistency-check
```

Body:

```json
{"candidate_asset_id": "...", "model": "qwen2.5vl:7b"}
```

The character must have `canonical_asset_id` set. The candidate image must belong to the same
project. Both images are sent to the local Ollama vision model with a fixed comparison prompt.

Response fields:

- `same_character`, `confidence`, `wardrobe_match`
- `differences[]`, `summary`
- `canonical_asset_id`, `candidate_asset_id`
- `model`, `provider`
- `human_review_required` is always `true`

The check is advisory. It does not approve characters and does not change the canonical asset.

### Readiness

`character_consistency` is `ready` when:

1. the SDXL img2img workflow is runnable, and
2. a local vision model (or a configured OpenAI vision model) is available.

IP-Adapter and SDXL ControlNet are now installed and smoke-tested, and are
selected explicitly for reference-locked or pose-locked work. Reference-locked
generation still defaults to canonical reference + img2img + seed.

### Measured test

A direct vision comparison of Leo front (`343185cb8b15`) and three-quarter
(`2942e4c6e079`) returned structured JSON from `qwen2.5vl:7b` with `same_character=false` and
concrete wardrobe differences — consistent with the visible wardrobe drift in that sheet.
The endpoint correctly rejected a character without a canonical reference with HTTP 400.

---

## Speech recognition

### Endpoints

```text
GET  /api/v1/speech/status
POST /api/v1/speech/transcribe
```

Body:

```json
{"asset_id": "...", "language": "en", "vad": true, "include_srt": true}
```

Response: `text`, `language`, `language_probability`, `duration`, `segments[]` (start/end/text),
`srt`, plus model/device metadata and the source asset id.

### Installation

- Package: `faster-whisper==1.2.1` in the backend virtual environment.
- Model: `Systran/faster-whisper-small` (MIT), 461 MB.
- Path: `D:\bro\CartoonStudio\models\asr\faster-whisper-small`.
- Default device: **CPU, int8**. This keeps VRAM free for ComfyUI, which matters on a 6 GB GPU.

Environment overrides:

| Variable | Default | Notes |
|---|---|---|
| `WHISPER_MODEL_DIR` | `models/asr/faster-whisper-small` | Any CTranslate2 Whisper model directory |
| `WHISPER_DEVICE` | `cpu` | `cuda` is possible but competes with ComfyUI for VRAM |
| `WHISPER_COMPUTE_TYPE` | `int8` | Use `float16` on GPU |

### Measured test

| Item | Result |
|---|---|
| Asset | `f9726f170b8f` (`dialogue_584b4577e35f.wav`, 1.75 s) |
| Text | `Welcome to Little Wonder Village.` |
| Language | `en`, probability 0.9958 |
| Time | 3.45 s including one-time model load |
| Device | CPU, int8 |
| SRT | `00:00:00,000 --> 00:00:02,000` |

### Limitations

- CPU int8 is reliable but slower than GPU for long files; the small model is a good balance
  for children’s dialogue.
- No speaker diarisation; one transcript per audio asset.
- Transcription does not automatically replace episode subtitles. Subtitle export still builds
  from dialogue lines; use the returned `srt` to replace or align them deliberately.
- Music and sound-effect assets transcribe poorly by design; use it on dialogue.

---

## Readiness changes

`production_registry_service` now derives these statuses from live capability instead of
hardcoded values:

| Department | Before | Now |
|---|---|---|
| Image editing | `partial` (nodes but no Qwen/FLUX weights) | `ready` when img2img or masked inpaint is runnable |
| Character consistency | `partial` (no LoRA/ControlNet) | `ready` when img2img and vision review are available |
| Speech recognition | `blocked` (hardcoded) | `ready` when package and model are present |

Qwen-Image-Edit and FLUX Kontext remain listed as **optional** semantic editors, not as
blockers. They are 12–20B models and are not practical on 6 GB.

---

## Tests

Added in `backend/tests/test_editing_and_speech.py`:

- SRT formatting from segments
- speech availability shape
- inpaint workflow role mapping and node classes
- inpainting checkpoint discovery and configuration precedence
- target-size scaling without upscaling
- vision comparison input guard

Full suite: **142 passed**.
