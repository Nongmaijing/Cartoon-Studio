# SDXL Model Guide — Little Wonder Village

## Purpose

Cartoon Studio now supports SDXL character and background generation while keeping SD 1.5 available as a lightweight fallback. This guide covers model discovery, manual installation, licensing, 6 GB VRAM settings, character consistency, and the current test status.

**No model is downloaded automatically.** Cartoon Studio only scans local model directories and reads small safetensors headers to report architecture.

---

## Current machine audit (actual)

ComfyUI 0.44.2, RTX 4050 Laptop, 6 GB VRAM, 32 GB RAM.

| Item | Installed |
|---|---|
| Checkpoints | `DreamShaper_8_pruned.safetensors` (SD 1.5), `v1-5-pruned-emaonly-fp16.safetensors` (SD 1.5) |
| SDXL checkpoint | **None** |
| VAEs | `wan2.2_vae.safetensors` (Wan), `pixel_space` (ComfyUI internal) |
| SDXL VAE | **None** |
| LoRAs | **None** |
| ControlNet models | **None** |
| Upscaler | `4x-UltraSharp.pth` |
| Custom nodes | **None** (only ComfyUI core) |
| Model directories | `D:\bro\ComfyUI\Models`, `ComfyUI-Shared\models`, install `models` |
| ComfyUI low-VRAM flag | **Not set** |

The Model Studio reports these findings and marks SDXL generation as blocked until an SDXL checkpoint is installed and selected.

---

## Manual installation (operator-initiated)

1. Download the model yourself from its official model page.
2. Put the file in one of these directories:
   - `C:\Users\pagau\AppData\Local\Comfy-Desktop\ComfyUI-Shared\models\checkpoints`
   - `D:\bro\ComfyUI\Models\checkpoints`
   - the install’s `models\checkpoints`
   - VAEs go in `models\vae`, LoRAs in `models\loras`, ControlNet in `models\controlnet`.
3. Restart ComfyUI or refresh its model list.
4. Open **Model Studio → Refresh catalog**.
5. Select the checkpoint and VAE, then **Save model config**.
6. The active model line should switch from SD 1.5 to SDXL.

Cartoon Studio never writes to ComfyUI model folders and never downloads or installs weights.

### Adding another model directory

Use **Settings → Storage → Model directories** (one path per line), save, then **Model Studio → Refresh catalog**. The catalog scans each configured directory recursively.

---

## 6 GB VRAM settings

Recommended starting point:

| Setting | Value |
|---|---|
| Resolution | 1024 × 1024 (character), 1216 × 832 (background/16:9), 832 × 1216 (full-body pose) |
| Steps | 25–30 |
| CFG | 5–7 |
| Batch size | 1 |
| Sampler | DPM++ 2M Karras (`dpmpp_2m` / `karras`) |
| VAE decode | Tiled (`VAEDecodeTiled`, tile 512, overlap 64) |
| Precision | ComfyUI’s stable low-VRAM path; fp16 checkpoint preferred |
| ComfyUI launch | `--lowvram` or `--normalvram` recommended on 6 GB |

The SDXL dimension guard rejects requests above 1,250,000 pixels with a clear error. That means 1024×1024, 1216×832, 832×1216 and 1152×896 are safe; 1536×1536 is rejected before a job is queued.

Model CPU offload and attention mode are ComfyUI launch flags. Cartoon Studio reports the live flags and recommends settings, but does not restart ComfyUI automatically. Use `--lowvram` for SDXL on this GPU and keep tiled VAE enabled.

---

## Workflow templates

| Workflow | Use |
|---|---|
| `sdxl_txt2img` | General SDXL text-to-image |
| `sdxl_img2img` | Reference conditioning / identity |
| `sdxl_character_turnaround` | Front, three-quarter, side and back views |
| `sdxl_character_expression` | Eight expressions from an approved reference |
| `sdxl_character_pose` | Eight poses from an approved reference |
| `sdxl_background` | 16:9 Little Wonder Village environments |

All SDXL templates:

- use `CheckpointLoaderSimple` + `CLIPTextEncode` + `EmptyLatentImage`/`ImageScale` + `KSampler` + `VAEDecodeTiled` + `SaveImage`;
- support optional VAE and LoRA injection by the workflow adapter;
- default to batch size 1;
- are structurally valid against the live ComfyUI node set;
- are **not runnable until an SDXL checkpoint is installed** (reported by `/api/workflows`).

The SD 1.5 workflows are unchanged and remain runnable.

---

## Character consistency

- **Master reference:** `characters.canonical_asset_id`, approved through the character approval action.
- **Approval gate:** expression and pose sheets require an approved character. An unapproved reference is not used silently; the API returns `409`.
- **Turnaround bootstrap:** if no reference exists, turnaround views are generated from text with one shared seed.
- **Reference conditioning:** when a reference exists, it is uploaded once and reused for every image in the sheet through `sdxl_img2img`/`sd15_img2img`.
- **Stable seed:** each sheet uses one base seed across all views/expressions/poses.
- **Character-specific settings:** architecture, checkpoint, VAE, LoRA, LoRA strength, reference strength and denoise are stored in `characters.memory_json["model"]`; no DB migration.
- **No auto-approval:** generated characters remain draft until the operator approves them.

Sheet endpoints:

```text
POST /api/characters/{id}/sheet/turnaround
POST /api/characters/{id}/sheet/expressions
POST /api/characters/{id}/sheet/poses
GET  /api/characters/{id}/sheets/{sheet_id}
GET  /api/characters/{id}/sheets
PATCH /api/characters/{id}/model
POST /api/characters/{id}/approve
```

The jobs use the existing single-worker queue. No parallel GPU load is introduced.

---

## Recommended SDXL models

These are recommendations only. Verify the exact license and current version on the model page before production use. Cartoon Studio does not download or endorse them.

| Model | Source | License | Approx. size | VRAM | Suitability |
|---|---|---|---|---|---|
| **SDXL Base 1.0** | `stabilityai/stable-diffusion-xl-base-1.0` | CreativeML Open RAIL++-M | ~6.9 GB fp16 | 8–10 GB recommended; 6 GB with low-VRAM/tiled VAE | General base; add a cartoon LoRA |
| **DreamShaper XL** | Civitai model page | CreativeML Open RAIL++-M (verify version) | ~6.5–7 GB | 6–8 GB with low-VRAM | Good stylized illustration starting point |
| **Blue Pencil XL** | Civitai model page | CreativeML Open RAIL++-M (verify version) | ~6.5 GB | 6–8 GB with low-VRAM | Line-art/illustration; test flat-color prompts |
| **Juggernaut XL** | Civitai model page | CreativeML Open RAIL++-M (verify version) | ~6.5–7 GB | 8 GB preferred | Detailed/general; less suited to flat 2D TV cartoons |
| **Cartoon style SDXL LoRA** | Civitai/Hugging Face | Varies by model card | ~100–300 MB | Minimal | Style layer on SDXL Base/DreamShaper; check commercial terms |

Reference conditioning: img2img works with the core workflow. SDXL ControlNet/IPAdapter need separate, SDXL-compatible model files; none are currently installed. Pose mode falls back to img2img and reports the fallback.

---

## Actual test results

| Test | Result |
|---|---|
| Model discovery | Passed — 2 checkpoints, 2 VAEs, 0 LoRAs, 0 ControlNet, 1 upscaler |
| SDXL missing-checkpoint reporting | Passed — catalog marks SDXL as blocked and falls back to SD 1.5 |
| No automatic download | Passed — the catalog only scans files and reads safetensors headers |
| SDXL workflow structural validation | Passed — all six SDXL workflows are structurally valid |
| SDXL workflow runnable status | Blocked — no SDXL checkpoint installed |
| SDXL character generation | Blocked — no SDXL checkpoint installed |
| Four-view turnaround | Implemented; mocked queue test passed; live SDXL run blocked |
| Expression sheet | Implemented; mocked 8-image queue test passed; live SDXL run blocked |
| Pose sheet | Implemented; mocked queue test passed; live SDXL run blocked |
| 16:9 village background | Template valid; live SDXL run blocked |
| SD 1.5 regression | Passed — live 512×512 job `49d325544c3f`, asset `d5c70209dd33` |
| Cartoon Studio asset registration | Passed for the SD 1.5 regression output |
| Automated tests | **35 passed** |
| Frontend production build | Passed |
| Model Studio page | HTTP 200, bundle contains the new UI |

VRAM measured during the audit:

- Total: ~6.0 GB
- Free at audit: ~2.87 GB
- ComfyUI low-VRAM flag: not set
- SDXL runtime VRAM is not measured because no SDXL checkpoint is installed.

---

## Limitations on a 6 GB RTX 4050

- SDXL at 1024×1024 is feasible with tiled VAE and low-VRAM mode, but slower than SD 1.5.
- Higher resolutions and batch sizes can cause CUDA OOM; the dimension guard blocks the most dangerous requests and batch size is fixed to 1 for SDXL.
- SDXL ControlNet/IPAdapter models are not installed; pose/reference work uses img2img.
- SDXL video is not part of this upgrade; Wan 2.2 remains the video path.
- Quick generation of 8-expression/8-pose sheets is serialized by the single-worker queue and can take a long time. Start with one view/expression for quality checks.
- ComfyUI must be restarted manually to apply `--lowvram`; Cartoon Studio only reports and recommends it.
- Model licensing and commercial-use terms are the operator’s responsibility.

---

## Next operator action

1. Choose an SDXL checkpoint from the table above.
2. Download it manually and place it in a configured `checkpoints` directory.
3. Optionally install an SDXL VAE and a cartoon LoRA.
4. Restart/refresh ComfyUI.
5. Open **Model Studio**, refresh, select the checkpoint/VAE/LoRA, save.
6. Run one 1024×1024 character test before queueing full sheets.
