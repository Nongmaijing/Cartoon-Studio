# Cutout and 2.5D Parallax Pipeline

The cheapest way to get real character motion on this hardware is not a video
model. It is a cutout: render the character once, remove the backdrop, composite
it over a painted plate, then move the camera and the subject by a few pixels.
A six-second clip costs about a second of CPU time and the character never
morphs.

## What it produces

- A transparent PNG cutout of a character (and only that character).
- An H.264 MP4 clip at 1280×720 or 1920×1080, ready for the Episode Editor.

## Prerequisites

`rembg` (U²-Net) is installed in the backend virtual environment:

```powershell
cd D:\bro\CartoonStudio\backend
.\.venv\Scripts\python.exe -m pip install rembg
```

The first call downloads the 176 MB `u2net.onnx` model to
`C:\Users\<user>\.rembg\models\u2net`. After that, cutouts run locally in about
**3 seconds** for a 768×1152 character.

Colour keying remains available as `engine: "chroma"` for a fast fallback, but
`rembg` is the production path: it handles grey, green or painterly backdrops
and removes the painted floor shadow.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/motion/presets` | Camera presets and defaults |
| POST | `/api/v1/motion/cutout` | Create a transparent PNG from an image asset |
| POST | `/api/v1/motion/parallax` | Render a layered clip from a plate + cutout |

### Cutout

```json
POST /api/v1/motion/cutout
{
  "project_id": "d7db6bd0e757",
  "asset_id": "46a26558b26f",
  "engine": "auto",
  "padding": 8
}
```

`engine`: `auto` (rembg, falling back to chroma), `rembg`, or `chroma`.
Output is stored under `outputs/<project>/motion/cutouts/` and registered as an
image asset with `meta.operation = "cutout"` and `meta.engine`.

### Parallax

```json
POST /api/v1/motion/parallax
{
  "project_id": "d7db6bd0e757",
  "background_asset_id": "8a554b52cb73",
  "foreground_asset_id": "0b55c2c73ec6",
  "duration": 6,
  "fps": 24,
  "width": 1280,
  "height": 720,
  "camera": "push_in",
  "subject_height": 0.72,
  "subject_x": 0.46,
  "subject_y": 0.98,
  "motion_strength": 1.2,
  "bob_period": 2.6,
  "shadow": true
}
```

| Field | Meaning |
|---|---|
| `subject_height` | Character height as a fraction of frame height (0.55–0.8 is typical) |
| `subject_x` | Horizontal centre, 0 = left, 1 = right |
| `subject_y` | Ground line, as a fraction of frame height (0.9–1.0) |
| `motion_strength` | Bob and sway amplitude multiplier (0.6–1.5) |
| `bob_period` | Seconds per breathing cycle (2–4 is calm) |
| `shadow` | Soft contact shadow under the feet |
| `scene_id` | Optional: link the finished clip to a scene as `role=video` |

Camera presets:

| Preset | Move |
|---|---|
| `static` | Locked camera |
| `push_in` | Slow push toward the subject |
| `pull_out` | Slow pull away |
| `pan_left` | Right-to-left drift |
| `pan_right` | Left-to-right drift |
| `drift` | Diagonal drift with a slight push |

Output is stored under `outputs/<project>/motion/parallax/` and registered as a
video asset with the render parameters in `meta`.

## End-to-end example

```powershell
$cut = @{
  project_id = 'd7db6bd0e757'
  asset_id   = '46a26558b26f'
} | ConvertTo-Json

$c = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8010/api/v1/motion/cutout `
  -ContentType 'application/json' -Body $cut

$px = @{
  project_id            = 'd7db6bd0e757'
  background_asset_id   = '8a554b52cb73'
  foreground_asset_id   = $c.asset.id
  duration              = 6
  camera                = 'push_in'
  subject_height        = 0.72
  subject_x             = 0.46
  subject_y             = 0.98
  motion_strength       = 1.2
} | ConvertTo-Json

$p = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8010/api/v1/motion/parallax `
  -ContentType 'application/json' -Body $px
$p.asset.rel_path
```

Measured on this machine: cutout **3.1 s**, 4-second parallax **1.0 s**,
6-second 720p clip about **1.5 s**.

## Quality rules

1. Render the character full-body on a plain backdrop, feet visible, one
   character only.
2. Prefer a reference or pose asset with a clean silhouette; `rembg` removes the
   painted floor shadow automatically.
3. Keep the character at 55–80% of frame height; tiny subjects read as stickers.
4. Use a 2–5% camera move over 4–8 seconds. Faster moves expose the flatness.
5. Two characters means two cutouts and two passes, or a staged keyframe shot.
6. Approve the cutout before rendering several shots from it; one good cutout is
   reused for every scene.

## Limits

- A cutout cannot turn its head or change expression. Swap to another pose or
  expression cutout for a beat change.
- Hair and thin props can need a higher `padding` or manual cleanup.
- `rembg` is a segmentation model, not a matcher: it does not know which
  character is which. Keep one character per cutout.
