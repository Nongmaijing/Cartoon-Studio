# Wan 2.2 Motion Recipe

The installed Wan 2.2 TI2V-5B does produce good motion — at **832×480**, not at
the low resolutions used in the first village tests.

## Proven recipe

| Parameter | Value |
|---|---|
| Workflow | `wan22_i2v` |
| Start image | approved keyframe, same project |
| Resolution | **832×480** |
| Frames | **97** (4.04 s) |
| FPS | 24 |
| Steps | 20 |
| CFG | 5.0 |
| Sampler / scheduler | `uni_pc` / `simple` |
| Shift | 8.0 |
| Seed | fixed per shot (4242 in the pilot) |
| VAE decode | tiled (the workflow default) |
| Time | **~310 s** per 4 s shot |
| Peak VRAM | **5.7 GB** |

Existing proof clips:

```
outputs/d7db6bd0e757/d42f33d0ee48/  Bramble walking down the lane
outputs/d7db6bd0e757/8987b26606a2/  The Grumble close-up
outputs/d7db6bd0e757/c82331fa35fe/  Bramble and Tock two-shot
```

All three are 832×480, 24 fps, 4.04 s, and visually coherent.

A fourth test on a village kitchen plate (`75ea2807ea9b`) completed in
**355 s**, peak **5408 MB**, with the shelves stable and the steam moving.

## Motion proof

Project `b1ff88aadcf3`, episode `be11757efce4`:

| Shot | Asset | Time |
|---|---|---|
| Simmering pot | `75ea2807ea9b` | 355 s |
| Laundry breeze | `8340b9de6d25` | 357 s |
| Rain and tea | `7596f3ff14b0` | 357 s |

Assembled at 1280×720 with the ambient score: **12.1 s, −16.1 LUFS**.

## Do not use low resolutions

Tested and rejected:

| Resolution | Result |
|---|---|
| 320×192 | corrupted after frame 0 |
| 384×224 | corrupted |
| 480×288 | corrupted |
| 832×480 | **works** |

The model is trained for 480p-class frames. Low-resolution latents are
out-of-distribution and the decode falls apart. This was the cause of the
earlier "Wan is broken" result, not the model or VAE.

## Motion prompt pattern

Put the action first, then stability cues:

```
<subject and action>, <secondary motion>,
static camera, locked composition, consistent scene, subtle natural motion
```

Examples:

- `steam rises gently from the copper pot, hanging herbs sway slightly, warm window light, static camera, consistent kitchen`
- `white sheets lift and settle in the breeze, soft clouds drift, static camera, consistent village`
- `rain slides slowly down the window glass, lamp glow steady, static camera, cozy interior`
- `she walks forward along the lane, scarf moves in the breeze, slow camera follow, consistent character design`

Negative:

```
camera movement, pan, zoom, warping, morphing, flicker,
distorted geometry, extra objects, text, watermark
```

## Use in an edit

- Generate 4-second shots; place them in the timeline at their native duration.
- A 3-minute lifestyle piece needs **20–30 shots**, i.e. **2–2.5 hours** of
  Wan time, then upscale/export.
- Keep still plates for shots where motion adds nothing; use Wan for steam,
  cloth, rain, grass, hair and character walks.
- Upscale 832×480 to 1280×720 in the episode export; 4× image upscale is for
  stills only.

## Limits

- 97 frames is the largest tested length. Longer shots are unverified.
- Complex interiors can still warp at the edges; inspect and regenerate.
- One GPU job at a time; free VRAM before a batch.
- The model is slow: budget ~5 minutes per shot.
