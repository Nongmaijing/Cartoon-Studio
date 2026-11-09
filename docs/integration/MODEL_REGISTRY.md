# Model Compatibility and Candidate Report

This is a current, machine-specific report. **No model is downloaded automatically.** Candidate rows are research recommendations; verify the exact checkpoint, license and current version on the official model page before installation.

## Installed inventory

| Department | Installed | Status |
|---|---|---|
| Image checkpoints | DreamShaper 8 (SD 1.5), SD 1.5 base | Ready |
| SDXL checkpoint | None | Blocked for SDXL |
| VAE | Wan 2.2 VAE, ComfyUI `pixel_space` | SD 1.5/Wan only |
| LoRA | None | Character LoRA unavailable |
| ControlNet | None | Pose conditioning falls back to img2img |
| Upscaler | 4x-UltraSharp | Ready |
| Video | Wan 2.2 TI2V-5B + text encoder + VAE | Ready (slow on 6 GB) |
| TTS | Kokoro-82M, Windows SAPI | Ready |
| LLM | Ollama Qwen3 8B, Qwen2.5 7B | Ready |
| VLM | Ollama Qwen2.5-VL 7B/3B, Qwen3-VL 8B | Ready |
| ASR | None | Blocked |
| SFX/music models | None | Procedural local synthesis is available |
| Image editing | Qwen/FLUX nodes present, weights missing | Partial |
| Custom nodes | None installed | Only ComfyUI core nodes |

Hardware: RTX 4050 Laptop, 6 GB VRAM, 32 GB RAM, ComfyUI 0.44.2, PyTorch 2.12.1+cu130, FFmpeg 8.1.1.

## Candidate comparison

| Department | Candidate | Source | License | Size | VRAM / hardware | Status | Recommendation |
|---|---|---|---|---|---|---|---|
| Image | SDXL Base 1.0 | stabilityai/stable-diffusion-xl-base-1.0 | CreativeML Open RAIL++-M | ~6.9 GB fp16 | 8–10 GB ideal; 6 GB with low-VRAM + tiled VAE | Not installed | Strong base; add a cartoon LoRA |
| Image | DreamShaper XL | Civitai model page | CreativeML Open RAIL++-M (verify) | ~6.5–7 GB | 6–8 GB with offload | Not installed | Practical first SDXL test |
| Image | Blue Pencil XL | Civitai model page | CreativeML Open RAIL++-M (verify) | ~6.5 GB | 6–8 GB with offload | Not installed | Line-art/illustration candidate |
| Image | Juggernaut XL | Civitai model page | CreativeML Open RAIL++-M (verify) | ~6.5–7 GB | 8 GB preferred | Not installed | Comparison only; less flat-cartoon |
| Image edit | Qwen-Image-Edit | Qwen/Qwen-Image-Edit | Apache 2.0 (verify) | Large 20B-class | High; quantised/offload needed | Nodes only | Strong identity-edit candidate |
| Image edit | FLUX.1 Kontext dev | black-forest-labs/FLUX.1-Kontext-dev | FLUX.1 [dev] Non-Commercial | ~12B-class | High | Nodes only | Do not use commercially without a license |
| Consistency | IP-Adapter SDXL | tencent-ailab/IP-Adapter | Apache 2.0 code; verify weights | Hundreds of MB | +1–2 GB | Not installed | Recommended for reference conditioning |
| Consistency | ControlNet SDXL OpenPose | Official ControlNet repositories | Varies | ~1–2.5 GB | +1–2 GB | Nodes only | Pose control candidate |
| Upscale | 4x-UltraSharp | Installed | Verify model card | 64 MB | 2–4 GB | Ready | Preserves line art; test identity drift |
| Upscale | Real-ESRGAN x4plus | xinntao/Real-ESRGAN | BSD-3-Clause code | ~64 MB | 2–4 GB | Not installed | Good alternative |
| Upscale | SUPIR | Fanghua-Yu/SUPIR | Apache 2.0 code (verify) | Several GB | 6 GB+ | Not installed | Restoration; may alter linework |
| Video | Wan 2.2 TI2V-5B | Wan-AI/Wan2.2-TI2V-5B | Apache 2.0 (verify) | 9.3 + 6.3 + 1.3 GB | 6 GB with offload; slow | Installed | Use for short low-res shots |
| Video | LTX-Video | Lightricks/LTX-Video | OpenRAIL-M-style (verify) | 4–12 GB | 6–12 GB | Nodes only | Best next 6 GB video candidate |
| Video | HunyuanVideo | tencent/HunyuanVideo | Tencent Community License | 15–30 GB | 24 GB+ | Nodes only | Experimental; not practical on 6 GB |
| Video | CogVideoX-2B/5B | THUDM/CogVideoX-2b | Apache 2.0 (verify) | 5–12 GB | 8–16 GB | Not installed | Constrained-hardware experiment |
| Voice | Kokoro-82M | Installed | Apache 2.0 | 310 MB + voices | CPU | Ready | Current production voice |
| Voice | Qwen3-TTS | Qwen official release | Apache 2.0 (verify) | Varies | CPU/GPU | Not installed | Multilingual candidate |
| Voice | Chatterbox | resemble-ai/chatterbox | MIT (verify) | Varies | CPU/GPU | Not installed | Expressive TTS candidate |
| Voice | CosyVoice | FunAudioLLM/CosyVoice | Apache 2.0 (verify) | Varies | CPU/GPU | Not installed | More setup than Kokoro |
| ASR | faster-whisper | SYSTRAN/faster-whisper | MIT | 75 MB–1.5 GB | CPU/small GPU | Not installed | Recommended for subtitles/lip-sync |
| SFX | AudioGen | facebookresearch/audiocraft | CC-BY-NC 4.0 weights (verify) | 1–3 GB | 4–8 GB | Not installed | Research only; verify commercial terms |
| Music | MusicGen | facebookresearch/audiocraft | CC-BY-NC 4.0 weights (verify) | 1–6 GB | 4–8 GB | Not installed | Research only; verify commercial terms |
| Music | ACE-Step | ace-step/ACE-Step | Apache 2.0 (verify) | Several GB | 6 GB+ | Nodes only | Longer music beds |
| Music | Stable Audio Open | stabilityai/stable-audio-open-1.0 | Stability AI Community License | 2–4 GB | 4–8 GB | Not installed | Verify commercial thresholds |
| LLM | Qwen3 8B | Ollama | Apache 2.0 (verify) | 5.2 GB | CPU/GPU | Ready | Story/script generation |
| VLM | Qwen2.5-VL 7B/3B | Ollama | Apache 2.0 (verify) | 6.0/3.2 GB | CPU/GPU | Ready | Visual QC |
| Lip-sync | Wav2Lip / SadTalker / Rhubarb | Official repos | Varies; often research/non-commercial | Varies | 2–8 GB | Not installed | Cue layer exists; rendering blocked |

## Compatibility notes

- ComfyUI 0.44.2 includes core nodes for Wan, LTX, Hunyuan, Qwen Image Edit, FLUX Kontext, ACE-Step, Stable Audio and audio latents. Node presence does **not** mean weights are installed.
- The Model Studio distinguishes `nodes_available`, `weights_installed`, and department `status`.
- SDXL workflows are structurally valid but not runnable until an SDXL checkpoint is selected.
- Wan is the only installed video family with weights.
- No custom nodes are installed; any candidate requiring custom nodes needs an operator installation step.
- Some ComfyUI API nodes (e.g., `HunyuanImageEditApi`, `QwenImageEditApi`, `FluxKontextProImageNode`) are cloud/API-backed and require separate credentials; they are not local weights.

## Licensing caution

Licenses change. Do not rely on this table as legal advice. Check the exact checkpoint revision, model card, and commercial-use terms before production. In particular:

- FLUX.1 Kontext dev is non-commercial without a separate license/API.
- AudioGen/MusicGen weights may be non-commercial.
- HunyuanVideo and Stable Audio have community-license restrictions.
- Community Civitai checkpoints/LoRAs vary; verify each model card.

## Recommended smallest practical set

1. **SDXL character model**: SDXL Base or DreamShaper XL.
2. **SDXL VAE**: madebyollin/sdxl-vae-fp16-fix or the checkpoint VAE.
3. **Cartoon style LoRA** with clear commercial terms.
4. **LTX-Video** as the next 6 GB-friendly video candidate.
5. **faster-whisper small/medium** for ASR and lip-sync alignment.
6. **Real-ESRGAN** as an upscaling comparison.
7. Only then consider Qwen-Image-Edit, IP-Adapter and ControlNet weights.

Do not install everything at once. Test one family at a time and measure VRAM/time with the resource manager.
