# Production Playbook — Painterly 2D Episodes

A practical operating guide for the current 6 GB machine. It assumes original
characters and designs, rendered in a painterly storybook tradition (soft
gouache, delicate linework, warm light) rather than copying any existing film.

## 1. Art direction

Art direction is a configuration choice:

```
config/config.json → "creative": { "art_style": "ghibli_painterly", "custom_style": "" }
```

| Preset id | Look |
|---|---|
| `ghibli_painterly` | Painterly gouache, soft watercolour, warm nostalgia — the default |
| `storybook_painterly` | Softer watercolour picture-book look |
| `clean_anime` | Crisp cel animation with painted backgrounds |
| `western_preschool` | Flat, bold-outline preschool cartoon |

API:

```
GET  /api/v1/models/styles
PUT  /api/v1/models/styles   { "art_style": "ghibli_painterly", "custom_style": "" }
```

`custom_style` appends a short phrase to every prompt for a series-specific
signature, for example `"muted teal shadows, visible paper grain"`.

Keep a **style bible** in project memory: palette swatches, line weight,
character proportions, lighting rules. A private style LoRA trained later on
approved frames is the strongest lock.

## 2. The four shot types

Use all four deliberately; do not ask one model to do everything.

| Type | What it is | How it is made | Cost |
|---|---|---|---|
| **A — Plate** | Environment with no characters | SDXL background workflow, then a slow push/pan | ~10–25 s |
| **B — Cutout** | Character over a plate, limited puppet motion | Character rendered on plain background, segmented with `rembg`, layered over plate, 2–3 pose swaps | ~3 s cutout + ~1.5 s per 6 s clip |
| **C — Keyframe** | Cast staged inside the location | SDXL + canonical reference + IP-Adapter (+ LoRA) | ~15–30 s |
| **D — Motion insert** | A short generated shot | Wan 2.2 image-to-video from an approved keyframe | 2–4 min per 3 s |

For a 7-minute episode, a healthy mix is roughly **40% A, 25% B, 30% C, 5% D**.
Type D is for reveals, weather, firelight and emotional beats — not dialogue.

Type B is implemented as a service: see `CUTOUT_PIPELINE.md` for the cutout and
parallax endpoints, camera presets and quality rules.

## 3. Pipeline and gates

```
script → style bible → cast sheets → backgrounds → shot plan
       → keyframes/cutouts → voice → sound → edit → QC → release
```

Gates (see `EPISODE_PIPELINE.md`):

1. **Character gate** — four-view turnaround, wardrobe check, human approval,
   then set the canonical image.
2. **Background gate** — reusable plates repeat cleanly across two shots.
3. **Script gate** — runtime, cast, safety and dialogue balance validated.
4. **Shot gate** — every keyframe checked for identity, costume, palette and
   continuity before it is accepted.
5. **Audio gate** — every line intelligible, levels matched, no clipping.
6. **Picture-lock gate** — timeline approved before the final export.
7. **Release gate** — full watch-through and explicit human approval.

Drafts stay drafts. Nothing is auto-approved.

## 4. Render profiles

| Use | Resolution | Steps | CFG | Sampler / scheduler | Time |
|---|---|---|---:|---|---:|
| Concept / draft | 1024×576 | 8 | 1.0 | euler / sgm_uniform (+ Lightning 8-step) | ~9–14 s |
| Final keyframe | 1216×832 or 1280×720 | 20–28 | 6.0 | dpmpp_2m / karras | ~15–25 s |
| Character sheet | 832×1216 | 8–20 | 1.0 / 6.0 | as above | ~9–20 s |
| Hero shot | 1216×832 → 4× upscale → downscale | 28 | 6.0 | dpmpp_2m / karras | ~25 s + 6 s |

Rules:

- Batch size **1**. VRAM headroom is about 0.5 GB at 1216×832.
- Do not exceed ~1.25 MP for SDXL on this GPU.
- Free VRAM between SDXL and Wan; the app exposes `POST /api/v1/resources/free`.
- Use the 8-step profile for every iteration, then re-render only approved
  shots at full quality.

## 5. Prompt templates

Keep the subject first. Style goes last because CLIP truncates.

**Background (type A)**

```
<location>, <time of day>, <weather>, <2–3 concrete details>,
<composition: wide establishing / low angle / over-the-shoulder>,
environment background art, no characters, no people, no text
```

**Character reference**

```
single full-body character, <name>, <species/age>, <silhouette>,
<face>, <hair>, <wardrobe with exact colours>, <props>,
one camera angle only, full-length wide shot, both feet visible, plain light grey background
```

**Scene keyframe (type C)**

```
<shot action>, <character A name + silhouette + wardrobe>, <character B …>,
setting: <location>, <camera direction>, <lighting>,
single animation keyframe, cinematic composition, no text
```

**Motion insert (type D)**

```
<what moves>, <what stays still>, <camera behaviour>,
minimal motion, consistent character design, no flicker, no morphing
```

Negative prompt baseline: photo, 3D, CGI, plastic, blurry, extra limbs, text,
watermark, signature. Add per-style terms from the preset.

## 6. Character consistency

1. Approve one canonical front image per character.
2. Generate side, three-quarter and back views through the automatic ControlNet
   skeleton path; see `CHARACTER_TURNAROUND.md`.
3. Fill `appearance` and `clothing` before generating views. A one-line
   description cannot hold an outfit together across angles.
4. Use it as the reference for every keyframe (`reference_mode: identity`).
3. Use ControlNet OpenPose when the pose matters; IP-Adapter Plus when the face
   and costume matter.
4. Train a per-character SDXL LoRA when a character appears in more than ~10
   shots. The pilot's `bramble_sdxl` (rank 16, 20 images, 4,800 steps) is the
   reference recipe.
5. Keep seed and prompt text stable for recurring shots; change one variable at
   a time.
6. For two-handers, prefer cuts and over-the-shoulder framing over cramming two
   full characters into one prompt.

## 7. Voice direction

- **Cast from timbre, not gender.** Kokoro has 29 voices; choose by warmth,
  age and energy, then adjust rate/pitch per character.
- **Emotion is a small offset, not a transformation.** Typical ranges:
  - calm: rate −2, pitch −4
  - excited: rate +4, pitch +10
  - afraid: rate +6, pitch +12, volume −6
  - sad: rate −6, pitch −10
  - narrator: rate −3, pitch 0
- Generate each line separately, keep the winning take, and never let a
  regeneration overwrite an accepted file.
- Resample every voice asset to 48 kHz and normalize before the mix.
- Target **−16 LUFS integrated**, **−1 dBTP true peak** for web delivery.
- Duck music 6–10 dB under dialogue; leave room tone so cuts do not feel dead.

## 8. Sound design

- Music: one theme, 2–3 variations, looped under dialogue at 25–35%.
- SFX: footsteps, cloth, doors, wind, birds, water — layered, not loud.
- Silence is a tool. Drop the music for the emotional beat.
- Every scene needs an ambience bed; pure dialogue over silence sounds empty.

## 9. Edit and motion

- Output 24 fps; render at 1280×720 and deliver 1920×1080 after upscale.
- Camera moves: 2–5% scale or pan over 4–8 s, eased. No snap zooms.
- Limited animation: hold drawings; animate 2–3 pose changes per second at most.
- Cuts inside a scene, fades only at act breaks.
- Subtitles come from dialogue text, not from guessing.
- Every export gets a new filename; keep earlier cuts.

## 10. Capacity and cadence

Per polished 7-minute episode: **3–5 hours of machine time** plus review.
A weekly cadence is realistic on this machine; a daily cadence needs a second
GPU or cloud bursts for finals.

## 11. Upgrade path

- **Now:** art presets, draft/final profiles, cutout pipeline, voice direction,
  CC0 sound library.
- **Next:** per-character LoRA training, Rhubarb lip sync, private style LoRA.
- **Later:** FLUX.1-schnell GGUF for hero frames, Chatterbox for expressive
  voices, Stable Audio Open for custom score — only if the quality gain
  justifies the iteration cost on 6 GB.
