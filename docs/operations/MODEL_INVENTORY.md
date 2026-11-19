# Model Inventory — 2026-11-11

## Authoritative state

The live backend/ComfyUI/MCP processes are currently **down**, so the model
catalog API is unavailable. This inventory is from the configured model
directories on disk.

Model roots:

- `D:\bro\ComfyUI\Models` (primary, 69 GB)
- `C:\Users\pagau\AppData\Local\Comfy-Desktop\ComfyUI-Shared\models` (4 GB)
- `D:\bro\CartoonStudio\models\asr`
- `D:\bro\CartoonStudio\tools\kokoro`

## Installed

| Model | Path | Size |
|---|---|---:|
| DreamShaper XL 1.0 | `D:\bro\ComfyUI\Models\checkpoints\DreamShaperXL_1.0.safetensors` | 6.60 GB |
| SDXL Inpainting 0.1 | `D:\bro\ComfyUI\Models\checkpoints\SDXL_Inpainting_0.1.safetensors` | 6.46 GB |
| DreamShaper 8 (SD1.5) | `...\ComfyUI-Shared\models\checkpoints\DreamShaper_8_pruned.safetensors` | 1.99 GB |
| SD1.5 base | `...\ComfyUI-Shared\models\checkpoints\v1-5-pruned-emaonly-fp16.safetensors` | 1.99 GB |
| Wan 2.2 TI2V-5B | `D:\bro\ComfyUI\Models\diffusion_models\wan2.2_ti2v_5B_fp16.safetensors` | 9.31 GB |
| Wan text encoder | `D:\bro\ComfyUI\Models\text_encoders\umt5_xxl_fp8_e4m3fn_scaled.safetensors` | 6.27 GB |
| Wan VAE | `D:\bro\ComfyUI\Models\vae\wan2.2_vae.safetensors` | 1.31 GB |
| 4x-UltraSharp | `...\ComfyUI-Shared\models\upscale_models\4x-UltraSharp.pth` | 0.06 GB |
| faster-whisper small | `D:\bro\CartoonStudio\models\asr\faster-whisper-small\model.bin` | 0.46 GB |
| Kokoro ONNX | `D:\bro\CartoonStudio\tools\kokoro\kokoro-v1.0.onnx` | 0.31 GB |
| Kokoro voices | `D:\bro\CartoonStudio\tools\kokoro\voices-v1.0.bin` | 0.03 GB |

So Wan 2.2, Kokoro, faster-whisper, the upscaler and the SDXL/SD1.5 image
models are already installed. The static recommendations list is stale for
some entries (for example faster-whisper).

## Installed in this pass

| Source | Filename | Size | Verified |
|---|---|---:|---|
| SDXL Base 1.0 | `D:\bro\ComfyUI\Models\checkpoints\sd_xl_base_1.0.safetensors` | 6.46 GB | SHA-256 verified by service |
| Blue Pencil XL | `D:\bro\ComfyUI\Models\checkpoints\blue_pencil-XL-v7.0.0.safetensors` | 6.46 GB | SHA-256 verified by service |
| Juggernaut XL | `D:\bro\ComfyUI\Models\checkpoints\JuggernautXL_Ragnarok_ByRunDiffusion.safetensors` | 6.62 GB | SHA-256 verified by service |

DreamShaper XL was not downloaded again because it is already installed under
`DreamShaperXL_1.0.safetensors`. D: now has ~199 GB free.

Download tool:

```powershell
cd D:\bro\CartoonStudio
backend\.venv\Scripts\python.exe scripts\download_vetted_models.py --dry-run
backend\.venv\Scripts\python.exe scripts\download_vetted_models.py --wait
```

The tool uses `model_download_service` (not direct writes), verifies SHA256 and
resumes partial files.

## Not downloaded — and why

The recommendations list also contains experimental or manual-install models:

- LTX-Video, HunyuanVideo, CogVideoX
- Qwen-Image-Edit, FLUX.1 Kontext
- SUPIR
- Qwen3-TTS, Chatterbox, CosyVoice
- AudioGen, MusicGen, ACE-Step, Stable Audio Open
- Wav2Lip / SadTalker / Rhubarb

They do **not** have a vetted direct-download entry in
`model_download_service.SOURCES`. Several are too large for the 6 GB RTX 4050,
non-commercial, or unnecessary for the current 2D preschool pilot. Downloading
“all” would add tens of GB of unused/experimental weight and require manual
license review.

## Optional control/identity/upscale — installed and verified

| Source | Target | Size | Licence | SHA-256 |
|---|---|---:|---|---|
| ControlNet SDXL OpenPose | `D:\bro\ComfyUI\Models\controlnet\controlnet-openpose-sdxl-1.0.safetensors` | 2.33 GB | Apache-2.0 | `b8524e55…cc06c5` |
| IP-Adapter Plus SDXL (ViT-H) | `D:\bro\ComfyUI\Models\ipadapter\ip-adapter-plus_sdxl_vit-h.safetensors` | 0.79 GB | Apache-2.0 | `3f5062b8…e6581` |
| CLIP ViT-H-14 image encoder | `D:\bro\ComfyUI\Models\clip_vision\CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` | 2.35 GB | Apache-2.0 | `6ca9667d…07b030` |
| CLIP ViT-bigG-14 image encoder (VIT-G preset) | `D:\bro\ComfyUI\Models\clip_vision\CLIP-ViT-bigG-14-laion2B-39B-b160k.safetensors` | 3.44 GB | Apache-2.0 | `657723e0…5d64d` |
| Real-ESRGAN x4plus | `D:\bro\ComfyUI\Models\upscale_models\RealESRGAN_x4plus.pth` | 0.06 GB | BSD-3-Clause (verify weights) | `4fa0d389…82f1` |

Full hashes:

- ControlNet OpenPose `b8524e557a7df60d081f5d4a0eb109967d107df217943bf88c2d99b9ebcc06c5`
- IP-Adapter Plus `3f5062b8400c94b7159665b21ba5c62acdcd7682262743d7f2aefedef00e6581`
- CLIP ViT-H-14 `6ca9667da1ca9e0b0f75e46bb030f7e011f44f86cbfb8d5a36590fcd7507b030`
- CLIP ViT-bigG-14 `657723e09f46a7c3957df651601029f66b1748afb12b419816330f16ed45d64d`
- Real-ESRGAN x4plus `4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1` (no published hash; locally recorded)

**Encoder pairing matters.** `ip-adapter-plus_sdxl_vit-h` needs the 1280-wide
ViT-H encoder (`h94/IP-Adapter/models/image_encoder`, 2.35 GB). The file in
`sdxl_models/image_encoder` (3.44 GB) is **ViT-bigG**, hidden size 1664, and only
matches the VIT-G preset. Mixing them fails at `Resampler.proj_in` with
`[1280,1280]` vs `[1280,1664]`. Both encoders are kept; the Plus workflow uses
ViT-H.

The first smoke test ran the ControlNet and upscale graphs successfully. IP-Adapter
failed with exactly that shape mismatch until the ViT-H encoder was installed.

`comfyui_extra_model_paths.yaml` in `config/` is a reference file for running
ComfyUI with `--extra-model-paths-config`; Comfy Desktop does not read it.

### How ComfyUI actually sees these paths

Comfy Desktop generates `%APPDATA%\Comfy Desktop\instance-model-paths\<install-id>.yaml`
with `D:\bro\ComfyUI\Models` as the default base path. That generated map covers
`checkpoints`, `controlnet`, `clip_vision`, `upscale_models` and the other core
categories — but **not** `ipadapter`, which is a custom-node category.

`ComfyUI_IPAdapter_plus` registers `ipadapter` from `<ComfyUI>/models/ipadapter`.
A directory junction was created so that folder resolves to the downloaded file:

```
C:\Users\pagau\AppData\Local\Comfy-Desktop\ComfyUI-Installs\Waikhom Studio\ComfyUI\models\ipadapter
  -> D:\bro\ComfyUI\Models\ipadapter
```

Verified in the ComfyUI venv with the generated path config loaded:

```
checkpoints: sd_xl_base_1.0, DreamShaperXL_1.0, blue_pencil-XL-v7.0.0, JuggernautXL..., SDXL_Inpainting_0.1, DreamShaper_8, v1-5
controlnet:  controlnet-openpose-sdxl-1.0.safetensors
clip_vision: CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors, CLIP-ViT-bigG-14-laion2B-39B-b160k.safetensors
upscale_models: 4x-UltraSharp.pth, RealESRGAN_x4plus.pth
ipadapter:   ip-adapter-plus_sdxl_vit-h.safetensors
```

## Custom node: ComfyUI_IPAdapter_plus

| Item | Value |
|---|---|
| Repository | `https://github.com/cubiq/ComfyUI_IPAdapter_plus` |
| Commit | `a0f451a5113cf9becb0847b92884cb10cbdec0ef` (2025-04-14) |
| Install path | `...\ComfyUI-Installs\Waikhom Studio\ComfyUI\custom_nodes\ComfyUI_IPAdapter_plus` |
| Nodes registered | 37 (35 matching `IPAdapter*`) |
| Extra Python deps | none beyond ComfyUI's existing `einops`/`torchvision` |
| InsightFace | optional, only for FaceID presets; not used by the Plus preset |

Import-tested inside the ComfyUI venv (Python 3.13.12, torch 2.12.1+cu130):
`NODE_CLASS_MAPPINGS` loads cleanly. `get_ipadapter_file("PLUS (high strength)", True)`
and `get_clipvision_file(...)` both resolve to the installed files.

To remove: delete the `custom_nodes\ComfyUI_IPAdapter_plus` folder and the
`models\ipadapter` junction. If ComfyUI Desktop is reinstalled or the install is
recreated, re-create the junction; otherwise the node reports no adapter models.

## New workflows

| Workflow | Purpose | Status |
|---|---|---|
| `sdxl_controlnet_pose` | SDXL + OpenPose ControlNet pose consistency | Auto-selected for SDXL pose references |
| `sdxl_ipadapter_identity` | SDXL + IP-Adapter Plus identity conditioning | Explicit selection only |
| `upscale_4x_real_esrgan` | Real-ESRGAN x4plus upscale | Explicit selection; `upscale_4x` remains the default |

## Download and verification commands

Download tool: `scripts/download_optional_models.py`.

```powershell
cd D:\bro\CartoonStudio
backend\.venv\Scripts\python.exe scripts\download_optional_models.py --dry-run
backend\.venv\Scripts\python.exe scripts\download_optional_models.py --accept-licenses
backend\.venv\Scripts\python.exe scripts\download_optional_models.py --verify
```

### Hash-verification incident (resolved)

The first run compared files against the CDN `ETag` header instead of the
HuggingFace LFS digest, so three complete, correct files were quarantined as
`*.part.bad`. The quarantined files matched the official LFS SHA-256 exactly and
were renamed to their final targets without re-downloading. The script now uses
the official LFS hashes and re-hashing via `--verify` returns `OK` for all four.

## Integration status — live-verified

ComfyUI was started headless on port 8188 and the graphs were executed for real.

| Capability | Result | Evidence |
|---|---|---|
| SDXL ControlNet pose | **Executed** | 512², 8 steps, 14 s; OpenPose model loaded, `ControlNetApplyAdvanced` applied |
| IP-Adapter identity | **Executed** | 512², 8 steps, 14 s, after installing the correct ViT-H encoder |
| Real-ESRGAN upscale | **Executed** | 512 → 2048 px output in 5 s |

Smoke-test artifacts (throwaway, not episode assets):

```
<ComfyUI>\output\cartoon_studio\smoke_controlnet_00001_.png   512x512
<ComfyUI>\output\cartoon_studio\smoke_ipadapter2_00001_.png   512x512
<ComfyUI>\output\cartoon_studio\smoke_esrgan_00001_.png       2048x2048
```

The images are low-step wiring tests, not quality references. The IP-Adapter
output mostly reproduces the test reference because the reference dominates at
8 steps; weight and step count still need tuning on real character art.

The app reads results through ComfyUI's `/view`, so the headless output folder
(`<ComfyUI>\output`) is fine and does not need to match `D:\bro\ComfyUI\Output`.

Note: running headless occupies port 8188. Close it before opening Comfy Desktop,
which would otherwise conflict.
