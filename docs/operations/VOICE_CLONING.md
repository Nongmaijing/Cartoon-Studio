# Voice Cloning with Chatterbox

Chatterbox is a local, MIT-licensed TTS family by Resemble AI. It does zero-shot
voice cloning from a 10–20 second reference clip, which is what Kokoro cannot do.

| Model | Size | Notes |
|---|---:|---|
| Chatterbox (original) | 500M | Exaggeration and CFG controls; best for expressive narration |
| Chatterbox Turbo | 350M | Faster, lower VRAM; supports `[laugh]`, `[sigh]` tags |

Both run on this 6 GB machine. The default is the **original** model for expressive
control.

## Install

```powershell
cd D:\bro\CartoonStudio
.\scripts\install_chatterbox.ps1          # CUDA 12.4 build
.\scripts\install_chatterbox.ps1 -Cpu     # CPU-only build
```

This creates an isolated venv at `tools\chatterbox\.venv`. It does **not** modify
the main backend venv, and it keeps pip/HuggingFace caches and model weights on
D: (`tools\pip-cache`, `models\huggingface`).

## Add a voice

Put a clean 10–20 second clip in `tools\chatterbox\voices` as WAV, MP3 or FLAC.
The file stem becomes the voice id.

```powershell
# Example: extract 12 s from the imported narration
ffmpeg -y -i "G:\old desktop\my stories\Project1\voices\Narration2_Zamindar.mp3" `
  -ss 0 -t 12 -ar 24000 -ac 1 "tools\chatterbox\voices\narrator_gura.wav"
```

Guidelines:

- One speaker only, no music, no room echo.
- 10–20 seconds is enough; longer is not automatically better.
- Match the language of the lines you will generate.
- Only clone a voice you have the right to use. Chatterbox embeds a Perth
  watermark in every output.

## Use it

Restart the backend, then open **Voice & Dialogue**. The engine list now includes
**Chatterbox (voice cloning)** with one voice per reference file.

API:

```powershell
# assign to a character
PATCH /api/characters/{id}/voice
{ "engine": "chatterbox", "voice": "narrator_gura", "rate": 0, "pitch": 0, "volume": 100 }

# or render a preview
POST /api/voice/preview
{ "text": "The rain does not answer power.", "engine": "chatterbox", "voice": "narrator_gura" }
```

`rate` and `pitch` are intentionally ignored for cloned voices: shifting them
would break the identity you cloned. Use a different reference clip, or
Chatterbox's exaggeration control via emotion, instead.

Emotion maps to exaggeration:

| Emotion | Exaggeration |
|---|---:|
| calm | 0.30 |
| sad | 0.35 |
| neutral | 0.50 |
| happy | 0.65 |
| angry | 0.70 |
| surprised | 0.70 |
| scared | 0.75 |
| excited | 0.80 |
| whisper | 0.25 |

## Runtime

Measured on the RTX 4050 (GPU, 24 kHz mono output):

| Test | Result |
|---|---|
| First call incl. model load | **17.7 s** |
| Warm 4.12 s line | **3.7 s** |
| Output loudness | **−15.3 LUFS** |
| Transcript check | exact match |

- The model downloads ~3 GB once into `models\huggingface` (D:).
- The model loads once into a persistent worker; later lines run faster than
  real time.
- GPU is used when available. If VRAM is too tight, the worker automatically
  falls back to CPU for that session.
- Logs: `logs/chatterbox.log`.

## When to use which engine

| Need | Engine |
|---|---|
| Fast drafts, many characters, 29 built-in voices | Kokoro |
| Humanlike narration, clone a specific voice | Chatterbox |
| Child voices | A child reference clip in Chatterbox, or Kokoro pitch presets |
| Fully offline, CPU only | Kokoro or Chatterbox CPU |
