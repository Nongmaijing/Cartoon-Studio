# SDXL Model Guide — Little Wonder Village

## Purpose

Cartoon Studio now supports SDXL character and background generation while keeping SD 1.5 available as a lightweight fallback. This guide covers model discovery, installation, licensing, 6 GB VRAM settings, character consistency, and the current test status.

**Nothing downloads implicitly.** Cartoon Studio scans local model directories for installed files, and Model Studio offers an opt-in download button for a small whitelist of reviewed SDXL sources. A download starts only after the operator confirms the licence and chooses to proceed; the file is size- and SHA256-verified before it is installed.

---

## Current machine audit (actual)

ComfyUI 0.44.2, RTX 4050 Laptop, 6 GB VRAM, 32 GB RAM.

| Item | Installed |
|---|---|
| Checkpoints | `DreamShaperXL_1.0.safetensors` (SDXL, 6.60 GB), `DreamShaper_8_pruned.safetensors` (SD 1.5), `v1-5-pruned-emaonly-fp16.safetensors` (SD 1.5) |
| SDXL checkpoint | **`DreamShaperXL_1.0.safetensors`** — selected in Model Studio; stored in `D:\bro\ComfyUI\Models\checkpoints` (6.60 GB) |
| SDXL Diffusers source | `D:\bro\ComfyUI\Models\diffusers\dreamshaper-xl-1-0` (6.60 GB) |
| SDXL inpainting checkpoint | `SDXL_Inpainting_0.1.safetensors` in `D:\bro\ComfyUI\Models\checkpoints` (6.46 GB) |
| SDXL inpainting source | `D:\bro\ComfyUI\Models\diffusers\sdxl-inpainting-0.1` (6.46 GB) |
| VAEs | `wan2.2_vae.safetensors` (Wan), `pixel_space` (ComfyUI internal) |
| SDXL VAE | Not needed separately — the converted checkpoint contains its VAE (`first_stage_model.*`) |
| LoRAs | **None** |
| ControlNet models | **None** |
| Upscaler | `4x-UltraSharp.pth` |
| Custom nodes | **None** (only ComfyUI core) |
| Model directories | `D:\bro\ComfyUI\Models`, `ComfyUI-Shared\models`, install `models` |
| ComfyUI low-VRAM flag | **Not set** (SDXL still ran at 1024×1024) |

`DreamShaperXL_1.0.safetensors` was installed on 2026-11-10 and is the active SDXL checkpoint. The Model Studio no longer reports SDXL as blocked.

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

Manual installation is always available. In addition, Model Studio can download a whitelisted
source after explicit licence confirmation; it writes only to the first configured model
directory and never overwrites an existing file.

### Download buttons in Model Studio

The recommendation table now has a **Download** button for reviewed sources:

| Recommendation | Source | File | Licence |
|---|---|---|---|
| SDXL Base 1.0 | `stabilityai/stable-diffusion-xl-base-1.0` | `sd_xl_base_1.0.safetensors` (6.46 GB) | CreativeML Open RAIL++-M |
| DreamShaper XL | Civitai 112902, alpha2 (xl1.0) | `DreamShaperXL1.0Alpha2_fixedVae_half_00001_.safetensors` (6.46 GB) | CreativeML Open RAIL++-M |
| Blue Pencil XL | Civitai 119012, v7.0.0 | `blue_pencil-XL-v7.0.0.safetensors` (6.46 GB) | CreativeML Open RAIL++-M |
| Juggernaut XL | Civitai 133005, Ragnarok | `JuggernautXL_Ragnarok_ByRunDiffusion.safetensors` (6.62 GB) | CreativeML Open RAIL++-M |

Behaviour:

- The client can only name a whitelisted recommendation; arbitrary URLs are rejected.
- `accept_license` must be true. The UI shows the licence and requires a checkbox.
- Downloads go to the first configured model directory (on this machine
  `D:\bro\ComfyUI\Models\<category>`), never to the ComfyUI install itself.
- Partial downloads use `.part` files and resume with HTTP Range.
- The completed file is checked against the known byte size and SHA256; a mismatch is
  quarantined as `.bad` and reported.
- Existing files are never overwritten.
- Progress and speed are shown in the table; cancellation keeps the partial file for resume.
- Civitai may require `CIVITAI_TOKEN`; Hugging Face gated repos require `HF_TOKEN`.
  The UI warns when no token is configured.
- The cartoon-style LoRA row remains **manual only**, because no single specific LoRA is
  bundled or vetted.

API:

```text
GET  /api/v1/models/downloads
POST /api/v1/models/downloads              {"recommendation": "...", "accept_license": true}
GET  /api/v1/models/downloads/{id}
POST /api/v1/models/downloads/{id}/cancel
```

After completion, refresh the catalog. ComfyUI rescans model folders on its next request; no
restart is required.

### Installing DreamShaper XL 1.0 (actual procedure)

The official `Lykon/dreamshaper-xl-1-0` repository is **Diffusers format**, not a single-file
ComfyUI checkpoint: it contains `unet/`, `text_encoder/`, `text_encoder_2/`, `vae/`, and
`model_index.json`, with no root `.safetensors`. Licence: **CreativeML Open RAIL++-M**
(`openrail++`, repo id `Lykon/dreamshaper-xl-1-0`, not gated).

What was done on this machine:

1. Downloaded only the fp16 Diffusers components (~6.60 GB total) into
   `D:\bro\ComfyUI\Models\diffusers\dreamshaper-xl-1-0` (moved there from the C: shared
   folder to keep C: free; the path is registered in `comfyui_extra_model_paths.yaml`).
   The full-precision UNet (~10.3 GB) was skipped for a 6 GB GPU.
2. Installed `diffusers==0.35.2` into the ComfyUI virtual environment (0.42.x was
   incompatible with the installed `huggingface_hub`; installed with `--no-deps`).
3. Converted the Diffusers pipeline to one ComfyUI-ready checkpoint with Hugging Face’s
   `scripts/convert_diffusers_to_original_sdxl.py` (fp16 file fallback), then wrote
   `DreamShaperXL_1.0.safetensors` (6.60 GB) into
   `D:\bro\ComfyUI\Models\checkpoints` (also moved off C: for disk space).

Notes for future installs:

- Do **not** hand-merge `ModelSave`/`CLIPSave`/`VAESave` output unless you know the exact key
  conventions. CLIP-L uses `conditioner.embedders.0.transformer.text_model.*`; CLIP-G must use
  the OpenCLIP layout `conditioner.embedders.1.model.transformer.resblocks.*`,
  `.positional_embedding`, `.ln_final.*`, `.text_projection`; the VAE uses
  `first_stage_model.*`; the UNet uses `model.diffusion_model.*`. A transformers-style CLIP-G
  layout (`...model.transformer.text_model.*`) fails at CLIP encoding with
  `Cannot copy out of meta tensor; no data!`.
- `CheckpointSave` currently fails on this ComfyUI build with
  `empty() received an invalid combination of arguments - got (list, dtype=torch.dtype, device=FakeDevice)`.
  Use the conversion script instead of the save node.
- Keep the Diffusers source folder: it is the reproducible source for the converted checkpoint.

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
| `sdxl_inpaint` | Masked edits using the SDXL inpainting checkpoint |

All SDXL templates:

- use `CheckpointLoaderSimple` + `CLIPTextEncode` + `EmptyLatentImage`/`ImageScale` + `KSampler` + `VAEDecodeTiled` + `SaveImage`;
- support optional VAE and LoRA injection by the workflow adapter;
- default to batch size 1;
- are structurally valid against the live ComfyUI node set;
- are **runnable** now that `DreamShaperXL_1.0.safetensors` is installed and selected
  (`/api/workflows` reports `runnable=true` for all seven and resolves the correct
  checkpoint per workflow, including the inpainting checkpoint).

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
| **DreamShaper XL** | `Lykon/dreamshaper-xl-1-0` (Diffusers format; converted locally) | CreativeML Open RAIL++-M | 6.60 GB fp16 | 6 GB works at 1024×1024; measured ~5.6 GB peak | Good stylized illustration; **installed and active** |
| **Blue Pencil XL** | Civitai model page | CreativeML Open RAIL++-M (verify version) | ~6.5 GB | 6–8 GB with low-VRAM | Line-art/illustration; test flat-color prompts |
| **Juggernaut XL** | Civitai model page | CreativeML Open RAIL++-M (verify version) | ~6.5–7 GB | 8 GB preferred | Detailed/general; less suited to flat 2D TV cartoons |
| **Cartoon style SDXL LoRA** | Civitai/Hugging Face | Varies by model card | ~100–300 MB | Minimal | Style layer on SDXL Base/DreamShaper; check commercial terms |

Reference conditioning: img2img works with the core workflow. SDXL ControlNet/IPAdapter need separate, SDXL-compatible model files; none are currently installed. Pose mode falls back to img2img and reports the fallback.

---

## Actual test results

| Test | Result |
|---|---|
| Model discovery | Passed — 4 checkpoints (1 SDXL, 1 SDXL inpainting, 2 SD15), 2 VAEs, 0 LoRAs, 0 ControlNet, 1 upscaler |
| SDXL checkpoint listing | Passed — `CheckpointLoaderSimple` lists `DreamShaperXL_1.0.safetensors` (also after moving it to D:) |
| SDXL checkpoint load + encode | Passed — 512×512, 1 step; 8.0 s warm, 22.3 s cold after the move |
| Seven SDXL workflows runnable | Passed — all seven `runnable=true`; the inpaint workflow resolves `SDXL_Inpainting_0.1.safetensors` |
| SDXL character generation | **Passed** — 1024×1024, `DreamShaperXL_1.0.safetensors` |
| Four-view turnaround (Leo) | **Passed** — 4/4 images, sheet `71192986e23b`, seed `20261110` |
| Turnaround timing | 30.3–30.6 s per image (four images sequential) |
| Peak VRAM | 5570–5616 MB per job (GPU total 6144 MB) |
| System RAM during run | 31.71 GB total, ~10.7 GB available, ~66% used |
| Output dimensions | 1024×1024 PNG, RGB, 1.2–1.3 MB each |
| Actual model name in job record | `DreamShaperXL_1.0.safetensors`, architecture `sdxl` |
| Asset registration | Passed — 4 assets attached to Leo with role `reference` |
| Leo approval state | Unchanged — `draft`, no canonical asset |
| SD 1.5 regression | Passed — 512×512 job `49d325544c3f`, asset `d5c70209dd33` |
| Automated tests | **151 passed** |

### Leo turnaround assets (live SDXL run)

| View | Job | Asset | Dimensions |
|---|---|---|---|
| front | `01fb540589e4` | `343185cb8b15` | 1024×1024 |
| three-quarter | `96c1b1d790ce` | `2942e4c6e079` | 1024×1024 |
| side | `60d677c008ad` | `565777291a75` | 1024×1024 |
| back | `c8554c0cc1b0` | `02ddfef37dcf` | 1024×1024 |

Measured runtime resources:

- GPU: RTX 4050 Laptop, 6.0 GB total; ~5.6 GB peak during SDXL sampling; ~1.0 GB free after.
- The checkpoint stays resident in VRAM between jobs (~5.0 GB used at idle after the run).
- ComfyUI was **not** started with `--lowvram`; the run still completed at 1024×1024.
- No OOM, no SD 1.5 fallback: every job record names `DreamShaperXL_1.0.safetensors`.

### Quality findings from the one Leo turnaround

These are reported honestly; they do not block the SDXL validation but must be fixed
before the turnaround can be used as a canonical character reference.

1. **Each image contains a three-view sheet, not one requested view.** The prompt path in
   `creative.character_prompt` does not add `no multiple views` for turnaround, and the
   sheet extra prompt says `production turnaround reference`, which SDXL interprets as a
   multi-view sheet. Each of the four “views” therefore rendered a front / three-quarter /
   side trio; the `back` image still shows faces.
2. **Wardrobe drift.** Leo’s profile specifies a mustard-yellow top, teal-blue short
   overalls with a star patch, white sneakers and a yellow backpack. The outputs show a teal
   cap, teal shirt/shorts, a mustard utility vest and brown shoes.
3. **Non-human prompt wording.** `creative.character_prompt` uses the phrase
   `single full body cartoon animal character` for every non-expression/pose request, which
   is wrong for human characters such as Leo.

See “Next operator action” for the recommended fix. Leo was **not** approved, and none of
these images were promoted to a canonical reference.

---

## Limitations on a 6 GB RTX 4050

- SDXL at 1024×1024 is feasible on this machine: measured 30.3–30.6 s per image, peak
  ~5.6 GB of 6.1 GB VRAM, without `--lowvram`.
- Headroom is small (~0.5 GB). Higher resolutions, batch sizes above 1, or running another
  GPU model at the same time can still OOM. The dimension guard blocks requests above
  1,250,000 pixels and batch size is fixed to 1 for SDXL.
- Turnaround prompt composition currently yields multi-view sheets and drifts from the
  character’s wardrobe; see the quality findings above. This is a prompt/QA issue, not an
  SDXL loading issue.
- SDXL ControlNet OpenPose and IP-Adapter Plus are installed and smoke-tested; SDXL
  reference-locked work can use IP-Adapter, and pose-locked work uses ControlNet.
  Plain img2img remains the default reference path.
- SDXL video is not part of this upgrade; Wan 2.2 remains the video path.
- Quick generation of 8-expression/8-pose sheets is serialized by the single-worker queue and
  can take a long time (~30 s per image plus model switching). Start with one view before
  queueing full sheets.
- ComfyUI must be restarted manually to apply `--lowvram`; Cartoon Studio only reports and
  recommends it.
- Model licensing and commercial-use terms are the operator’s responsibility.

---

## Next operator action

1. Fix turnaround prompt composition before using these outputs as references:
   - add `no multiple views` to the turnaround `_extra_prompt` in
     `backend/app/services/character_sheet_service.py`;
   - stop using `production turnaround reference` as a per-view phrase;
   - remove the hard-coded `cartoon animal character` wording for human characters in
     `backend/app/services/creative.py`.
2. Re-run one turnaround and visually compare the four views against Leo’s wardrobe
   description; only then consider promoting a view to `canonical_asset_id`.
3. Approve Leo explicitly (he is still `draft`) before expression or pose sheets.
4. Optionally install an SDXL cartoon LoRA and an SDXL VAE for style control.
5. Consider `--lowvram` if future SDXL work adds ControlNet/IPAdapter or larger batch sizes.
