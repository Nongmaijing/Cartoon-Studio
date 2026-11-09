# ComfyUI Integration

## Existing integration

- Server: `http://127.0.0.1:8188`.
- Client: `backend/app/comfy/client.py`.
- Workflows: `workflows/*.json` + `*.mapping.json`.
- Queue: existing `jobs` table and single-worker `JobRunner`.
- Progress: ComfyUI WebSocket.
- Outputs: downloaded via `/view` into `outputs/<project>/<job>/`.

## Production workflows

| ID | Kind | Engine |
|---|---|---|
| `sd15_txt2img` | image | DreamShaper 8 |
| `sd15_img2img` | image | DreamShaper 8 |
| `sd15_controlnet_pose` | image | DreamShaper 8 + ControlNet OpenPose (when installed) |
| `upscale_4x` | image | 4x-UltraSharp |
| `wan22_t2v` | video | Wan 2.2 TI2V-5B |
| `wan22_i2v` | video | Wan 2.2 TI2V-5B |
| `animatediff_t2v` | video | AnimateDiff Evolved + VideoHelperSuite (when installed) |

## Readiness

`GET /api/workflows` and `POST /api/workflows/{id}/validate` check:

- mapped roles/nodes/inputs,
- every node class used by the graph,
- model files referenced by the mapping.

A workflow is `runnable` only when all checks pass. The provider registry reports ComfyUI live connection separately.

## Model locations

- DreamShaper 8: shared checkpoints folder.
- 4x-UltraSharp: shared `upscale_models`.
- Wan: diffusion_models/text_encoders/vae.
- Kokoro: `tools/kokoro/`.

## Direct server start

If ComfyUI Desktop is not used, the install can be started directly:

```powershell
& "C:\Users\pagau\AppData\Local\Comfy-Desktop\ComfyUI-Installs\Waikhom Studio\ComfyUI\.venv\Scripts\python.exe" `
  main.py --listen 127.0.0.1 --port 8188 `
  --extra-model-paths-config D:\bro\CartoonStudio\config\comfyui_extra_model_paths.yaml `
  --input-directory "C:\Users\pagau\AppData\Local\Comfy-Desktop\ComfyUI-Shared\input" `
  --output-directory "D:\bro\ComfyUI\Output" --enable-manager
```

## Hardware

- RTX 4050 Laptop, 6 GB VRAM.
- One heavy local image/video job at a time.
- Wan video is slow; use short/low-resolution clips for tests.
- The provider registry exposes ComfyUI connection and GPU/device status through `/api/v1/providers/status`.
