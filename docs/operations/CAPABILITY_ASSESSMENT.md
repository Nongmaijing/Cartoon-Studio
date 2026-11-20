# Hardware Capability Assessment — 2026-11-19

Measured on the live machine with the installed ComfyUI 0.44.2 stack. Every
number below came from a job that actually ran; nothing is estimated except
where explicitly labelled.

## Verdict

This machine is a capable **limited-animation / motion-comic studio** for
7-minute 2D episodes at 720p, and can finish at 1080p after upscaling. It is not
a 24 fps full-animation renderer and not a feature-film box.

| Target | Verdict |
|---|---|
| Painterly 2D backgrounds and keyframes | **Excellent** |
| Character sheets and expression sheets | **Good** (SDXL + IP-Adapter + optional LoRA) |
| Limited animation, 2.5D camera moves, cuts | **Excellent** |
| 24 fps character animation | **No** — use selective generative motion only |
| 7-minute episode at 720p | **Yes**, a few hours of machine time |
| 1080p delivery | **Yes**, 2× upscale + downscale |
| Feature film | **No** at this VRAM; cloud or a larger GPU required |

## Hardware

| Item | Value |
|---|---|
| GPU | NVIDIA RTX 4050 Laptop, **6.0 GB VRAM** |
| CPU | Intel Core 7 240H, 10 cores / 16 threads |
| RAM | 31.7 GB (8–9 GB free with services running) |
| Disk | C: 20.6 GB free, D: **165 GB free** |
| OS / driver | Windows, NVIDIA 610.60 |
| ComfyUI | 0.44.2, PyTorch 2.12.1+cu130, launched with the Cartoon Studio model-path config |
| FFmpeg | 8.1.1 full build |

## Measured performance

### Image — DreamShaper XL 1.0

| Test | Settings | Time | Peak VRAM |
|---|---|---:|---:|
| SDXL Lightning, first run | 1024×576, 8 steps, CFG 1, euler/sgm_uniform | 13.9 s (includes model load) | 5151 MB |
| SDXL Lightning, warm | 1280×720, 8 steps, CFG 1 | **8.75 s** | 5153 MB |
| SDXL Lightning, warm | 832×1216, 8 steps, CFG 1 | **9.13 s** | 5185 MB |
| SDXL full quality | 1024×576, 20 steps, CFG 6, dpmpp_2m/karras | **13.4 s** | 5153 MB |
| SDXL background via app | 1216×832, 20 steps, CFG 6 | **24.6 s** | 5631 MB |

Throughput is roughly **1.0–1.2 s per step at ~1 MP**, and about
**0.65 s per step at 0.6 MP**. The Lightning LoRA gives a 2.5–3× speed-up with
only a small quality cost on backgrounds.

Full-quality SDXL at 1216×832 leaves only **~0.5 GB VRAM headroom**. Adding
ControlNet or IP-Adapter to that resolution is where OOM risk starts.

### Video — Wan 2.2 TI2V-5B

| Test | Settings | Time | Peak VRAM |
|---|---|---:|---:|
| Text-to-video | 320×192, 9 frames, 8 fps, 10 steps | **22.0 s** | 5717 MB |

Scaling is roughly linear in pixels and steps. A 3-second 480×272 shot is
about **2–4 minutes**. Wan is viable for a handful of hero moments, not for
every shot.

### Voice — Kokoro-82M (CPU)

| Test | Time |
|---|---:|
| First line incl. model load | 3.3 s |
| Warm line (~4 s of speech) | **0.8–1.2 s** |

A 7-minute episode with ~60 dialogue lines costs about **1–2 minutes of CPU
time**. Voice is not a bottleneck.

### Other verified paths

| Path | Result |
|---|---|
| 4× upscale (4x-UltraSharp) | 2–6 s per image |
| Real-ESRGAN x4plus | 5 s for 512→2048 |
| Character cutout (rembg U²-Net) | **3.1 s** for 768×1152 |
| Turnaround side view (ControlNet + IP-Adapter) | **40 s** at 768×1152, peak 5723 MB |
| Turnaround back view (ControlNet + IP-Adapter) | **49 s** at 768×1152, peak 5990 MB |
| Narration import + 6-plate episode | 129.5 s 720p export, 18 cues |
| Character LoRA (20 images, 24 epochs) | ~2 hours on this GPU (existing recipe) |
| Village-life episode (8 plates + score) | 64 s export, -15.7 LUFS |
| Wan I2V at 832×480 (97 frames) | 355 s, peak 5408 MB, stable scene |
| Episode final mix | loudnorm to -16 LUFS / -1.5 dBTP |
| 2.5D parallax render | **1.0 s** for 4 s at 1280×720 |
| Masked SDXL inpainting | 30.7 s at 1024×1024 |
| faster-whisper small transcription | 3.45 s for a 1.75 s line (CPU int8) |
| Kokoro SFX/music | procedural, seconds |
| FFmpeg 720p/1080p export | seconds to a few minutes |

## Quality evidence

- **Background:** asset `8a554b52cb73` — 1216×832, DreamShaper XL, 20 steps, new
  `ghibli_painterly` preset. Painterly hillside cottage with soft clouds and
  warm light; production-usable.
- **Pilot:** *Bramble and the Last Lantern* — 6:01, 41 shots, SDXL + SDXL
  Lightning + `bramble_sdxl` LoRA, Kokoro, FFmpeg.
- **Test suite:** 162 passed.

## Bottlenecks, in order of impact

1. **VRAM ceiling.** SDXL at 1 MP plus a control model is at the edge. Batch
   size must stay 1. Render 1216×832 or 1280×720, not 1536+. Free VRAM between
   SDXL and Wan. `--lowvram` is the safe operating mode for mixed sessions.
2. **Motion.** Wan is ~22 s for 1.1 s at 320×192. Full-episode generative motion
   is not affordable. The production answer is 2.5D camera moves, cutout
   layers and a small number of generated inserts.
3. **Character consistency.** Reference-locked img2img is good; a per-character
   LoRA is much better. Multi-character shots remain weak and should be
   staged as cuts or layers rather than one crowded prompt.
4. **Voice range.** Kokoro is clean and fast but not deeply emotional. Rate and
   pitch offsets help; a dedicated expressive TTS is the next upgrade.
5. **Sound design.** Procedural music/SFX is placeholder quality. A curated
   CC0/licensed library or a dedicated audio model is needed for a finished
   mix.
6. **Prompt budget.** CLIP truncates long prompts. Put the subject first, style
   last, and keep the core description under ~77 tokens per encoder.

## Capacity planning per episode

For a 7-minute episode with ~50 shots:

| Stage | Machine time |
|---|---:|
| 50 draft keyframes (8-step) | ~8 min |
| 50 final keyframes (20-step) | ~15–20 min |
| 50 upscales | ~5 min |
| 60 dialogue lines | ~2 min |
| 8–12 selective Wan inserts | 20–45 min |
| Edit + 720p export | 2–5 min |
| **One full pass** | **~1 hour** |

With iteration, review and regeneration, budget **3–5 hours of machine time**
per polished episode. Human review is the real schedule driver.

## Upgrade tiers

### Tier 0 — no downloads (do now)

- Configurable art direction (`ghibli_painterly`, `storybook_painterly`,
  `clean_anime`, `western_preschool`).
- Draft/final render profiles.
- Cutout + 2.5D camera workflow.
- Voice casting, emotion mapping and loudness standards.
- Prompt bible and shot taxonomy.

### Tier 1 — small additions (recommended)

| Addition | Size | Why |
|---|---:|---|
| Per-character LoRA training stack (kohya_ss / ai-toolkit) | Python deps + 1–2 GB | The single biggest consistency upgrade |
| Rhubarb Lip Sync | ~50 MB | Mouth cues and 2–3 mouth shapes for limited animation |
| CC0 SFX/music library | 1–5 GB | Better sound than procedural synthesis |
| Private style LoRA trained on approved frames | ~100 MB | Locks palette and linework without licensing risk |

### Tier 2 — larger experiments (optional)

| Addition | Size | Trade-off |
|---|---:|---|
| FLUX.1-schnell GGUF Q4 + encoders | ~8–10 GB | Better prompt adherence; 60–120 s per image on 6 GB |
| Chatterbox TTS | ~2–4 GB | More expressive voices; competes for CPU/GPU |
| Stable Audio Open | ~2–4 GB | Custom music beds; competes for VRAM |

### Not recommended on this GPU

LTX/Hunyuan/CogVideoX at production resolution, Wav2Lip/SadTalker rendering,
and 12–20B image editors (Qwen-Image-Edit, FLUX Kontext). They either do not fit
or are too slow to iterate.
