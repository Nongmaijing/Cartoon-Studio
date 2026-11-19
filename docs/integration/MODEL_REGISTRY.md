# Model Compatibility and Candidate Report

Machine-specific report, last verified against the model directories and live
ComfyUI runs on **2026-11-19**. Candidate rows are research recommendations;
verify the exact checkpoint, licence and current version on the official model
page before installation. Model Studio can download a small whitelist after
explicit licence confirmation and SHA256 verification; nothing is fetched
implicitly.

## Installed inventory

| Department | Installed | Status |
|---|---|---|
| SDXL checkpoints | DreamShaper XL 1.0 (default), SDXL Base 1.0, Blue Pencil XL v7, Juggernaut XL Ragnarok | Ready |
| SD 1.5 checkpoints | DreamShaper 8, SD 1.5 base | Ready (fallback) |
| VAE | Checkpoint-embedded SDXL/SD 1.5 VAE, Wan 2.2 VAE, ComfyUI `pixel_space` | Ready |
| LoRA | SDXL-Lightning 8-step, SDXL-Lightning 4-step, `bramble_sdxl` character LoRA | Ready |
| ControlNet | ControlNet OpenPose SDXL 1.0 | Ready |
| IP-Adapter | IP-Adapter Plus SDXL (ViT-H) + CLIP ViT-H-14 and ViT-bigG-14 encoders | Ready |
| Upscaler | 4x-UltraSharp (default), Real-ESRGAN x4plus | Ready |
| Video | Wan 2.2 TI2V-5B + text encoder + VAE | Ready (slow on 6 GB) |
| TTS | Kokoro-82M, Windows SAPI | Ready |
| LLM | Ollama Qwen3 8B, Qwen2.5 7B | Ready |
| VLM | Ollama Qwen2.5-VL 7B/3B, Qwen3-VL 8B | Ready |
| ASR | faster-whisper small (CPU int8) | Ready |
| Image editing | SDXL img2img + SDXL Inpainting 0.1 | Ready (masked inpaint verified) |
| SFX/music models | None | Procedural local synthesis is available |
| Custom nodes | ComfyUI_IPAdapter_plus | Installed |
| Semantic editors | Qwen-Image-Edit, FLUX.1 Kontext | Nodes only — weights missing (optional) |

Hardware: RTX 4050 Laptop, 6 GB VRAM, 32 GB RAM, ComfyUI 0.44.2, PyTorch 2.12.1+cu130, FFmpeg 8.1.1.

Live evidence: SDXL keyframes for the 6:01 *Bramble and the Last Lantern*
pilot (DreamShaper XL + SDXL Lightning 8-step + `bramble_sdxl` LoRA at 0.80),
ControlNet/IP-Adapter smoke tests, masked inpainting, Real-ESRGAN upscale and a
faster-whisper transcription all completed on this machine.

## Candidate comparison

| Department | Candidate | Source | License | Size | VRAM / hardware | Status | Recommendation |
|---|---|---|---|---|---|---|---|
| Image | DreamShaper XL 1.0 | Installed | CreativeML Open RAIL++-M (verify) | 6.60 GB | 6–8 GB with offload | **Ready — default** | Practical first SDXL checkpoint |
| Image | SDXL Base 1.0 | Installed | CreativeML Open RAIL++-M | ~6.46 GB | 6 GB with low-VRAM + tiled VAE | **Ready** | Stock SDXL comparison |
| Image | Blue Pencil XL v7 | Installed | CreativeML Open RAIL++-M (verify) | 6.46 GB | 6–8 GB with offload | **Ready** | Line-art/illustration candidate |
| Image | Juggernaut XL Ragnarok | Installed | CreativeML Open RAIL++-M (verify) | 6.62 GB | 8 GB preferred | **Ready** | Comparison only; less flat-cartoon |
| Image edit | Qwen-Image-Edit | Qwen/Qwen-Image-Edit | Apache 2.0 (verify) | Large 20B-class | High; quantised/offload needed | Nodes only | Strong identity-edit candidate; not practical on 6 GB |
| Image edit | FLUX.1 Kontext dev | black-forest-labs/FLUX.1-Kontext-dev | FLUX.1 [dev] Non-Commercial | ~12B-class | High | Nodes only | Do not use commercially without a license |
| Consistency | IP-Adapter SDXL | Installed | Apache 2.0 code; verify weights | 0.79 GB (+2.35 GB encoder) | +1–2 GB | **Ready — smoke-tested** | Plus preset pairs with CLIP ViT-H-14 |
| Consistency | ControlNet SDXL OpenPose | Installed | Apache 2.0 | 2.33 GB | +1–2 GB | **Ready — smoke-tested** | Pose control |
| Upscale | 4x-UltraSharp | Installed | Verify model card | 64 MB | 2–4 GB | **Ready — default** | Preserves line art; test identity drift |
| Upscale | Real-ESRGAN x4plus | Installed | BSD-3-Clause code | ~64 MB | 2–4 GB | **Ready** | Good alternative; verify weights |
| Upscale | SUPIR | Fanghua-Yu/SUPIR | Apache 2.0 code (verify) | Several GB | 6 GB+ | Not installed | Restoration; may alter linework |
| Video | Wan 2.2 TI2V-5B | Installed | Apache 2.0 (verify) | 9.3 + 6.3 + 1.3 GB | 6 GB with offload; slow | **Ready** | Use for short low-res shots |
| Video | LTX-Video | Lightricks/LTX-Video | OpenRAIL-M-style (verify) | 4–12 GB | 6–12 GB | Nodes only | Best next 6 GB video candidate |
| Video | HunyuanVideo | tencent/HunyuanVideo | Tencent Community License | 15–30 GB | 24 GB+ | Nodes only | Experimental; not practical on 6 GB |
| Video | CogVideoX-2B/5B | THUDM/CogVideoX-2b | Apache 2.0 (verify) | 5–12 GB | 8–16 GB | Not installed | Constrained-hardware experiment |
| Voice | Kokoro-82M | Installed | Apache 2.0 | 310 MB + voices | CPU | **Ready — production** | Current production voice |
| Voice | Qwen3-TTS | Qwen official release | Apache 2.0 (verify) | Varies | CPU/GPU | Not installed | Multilingual candidate |
| Voice | Chatterbox | resemble-ai/chatterbox | MIT (verify) | Varies | CPU/GPU | Not installed | Expressive TTS candidate |
| Voice | CosyVoice | FunAudioLLM/CosyVoice | Apache 2.0 (verify) | Varies | CPU/GPU | Not installed | More setup than Kokoro |
| ASR | faster-whisper small | Installed | MIT | 461 MB | CPU int8 | **Ready — verified** | Subtitles/lip-sync alignment |
| SFX | AudioGen | facebookresearch/audiocraft | CC-BY-NC 4.0 weights (verify) | 1–3 GB | 4–8 GB | Not installed | Research only; verify commercial terms |
| Music | MusicGen | facebookresearch/audiocraft | CC-BY-NC 4.0 weights (verify) | 1–6 GB | 4–8 GB | Not installed | Research only; verify commercial terms |
| Music | ACE-Step | ace-step/ACE-Step | Apache 2.0 (verify) | Several GB | 6 GB+ | Nodes only | Longer music beds |
| Music | Stable Audio Open | stabilityai/stable-audio-open-1.0 | Stability AI Community License | 2–4 GB | 4–8 GB | Not installed | Verify commercial thresholds |
| LLM | Qwen3 8B | Ollama | Apache 2.0 (verify) | 5.2 GB | CPU/GPU | **Ready** | Story/script generation |
| VLM | Qwen2.5-VL 7B/3B | Ollama | Apache 2.0 (verify) | 6.0/3.2 GB | CPU/GPU | **Ready** | Visual QC |
| Lip-sync | Wav2Lip / SadTalker / Rhubarb | Official repos | Varies; often research/non-commercial | Varies | 2–8 GB | Not installed | Cue layer exists; rendering blocked |

Installed LoRAs not listed above: `sdxl_lightning_8step_lora.safetensors` and
`sdxl_lightning_4step_lora.safetensors` (fast mode) and `bramble_sdxl.safetensors`
(locally trained character LoRA, SDXL rank 16, 81.5 MB).

## Compatibility notes

- ComfyUI 0.44.2 includes core nodes for Wan, LTX, Hunyuan, Qwen Image Edit, FLUX Kontext, ACE-Step, Stable Audio and audio latents. Node presence does **not** mean weights are installed.
- The Model Studio distinguishes `nodes_available`, `weights_installed`, and department `status`.
- SDXL workflows are runnable with DreamShaper XL 1.0 as the configured default; SD 1.5 remains a selectable fallback.
- Wan is the only installed video family with weights.
- `ComfyUI_IPAdapter_plus` is installed (commit `a0f451a`), so IP-Adapter is available; other custom-node candidates still need an operator installation step.
- The IP-Adapter Plus preset requires the 1280-dim CLIP ViT-H-14 encoder. The 1664-dim ViT-bigG-14 file only works with the VIT-G preset; mixing them fails at `Resampler.proj_in`.
- Some ComfyUI API nodes (e.g., `HunyuanImageEditApi`, `QwenImageEditApi`, `FluxKontextProImageNode`) are cloud/API-backed and require separate credentials; they are not local weights.

## Licensing caution

Licenses change. Do not rely on this table as legal advice. Check the exact checkpoint revision, model card, and commercial-use terms before production. In particular:

- FLUX.1 Kontext dev is non-commercial without a separate license/API.
- AudioGen/MusicGen weights may be non-commercial.
- HunyuanVideo and Stable Audio have community-license restrictions.
- Community Civitai checkpoints/LoRAs vary; verify each model card.

## Current production set

Installed and live-verified:

1. **SDXL character model**: DreamShaper XL 1.0 (default), with SDXL Base/Blue Pencil/Juggernaut as alternatives.
2. **SDXL VAE**: checkpoint-embedded VAE, tiled decode on 6 GB.
3. **Fast mode**: SDXL-Lightning 8-step (default) or 4-step LoRA, CFG 1.
4. **Character consistency**: IP-Adapter Plus SDXL (ViT-H) + CLIP ViT-H-14, and ControlNet OpenPose SDXL.
5. **Character LoRA**: `bramble_sdxl` trained locally for the pilot.
6. **Upscaling**: 4x-UltraSharp (default) and Real-ESRGAN x4plus.
7. **Video**: Wan 2.2 TI2V-5B for short low-res shots.
8. **Voice**: Kokoro-82M; Windows SAPI fallback.
9. **ASR**: faster-whisper small on CPU int8.
10. **LLM/VLM**: Ollama Qwen3 8B and Qwen2.5-VL 7B/3B.

Still optional / not practical on this hardware: Qwen-Image-Edit, FLUX Kontext, LTX-Video, HunyuanVideo, CogVideoX, Qwen3-TTS/Chatterbox/CosyVoice, AudioGen/MusicGen/Stable Audio Open, and lip-sync rendering (Wav2Lip/SadTalker/Rhubarb). Downloading “all” would add tens of GB of unused or experimental weight and require manual license review.

Do not install everything at once. Test one family at a time and measure VRAM/time with the resource manager.
