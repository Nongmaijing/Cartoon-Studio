# Character LoRA (character cloning)

For a 2D series, the strongest way to keep a character identical is a small
SDXL LoRA trained on that character. It locks the face, hair and wardrobe far
better than prompt text, IP-Adapter or a canonical image alone.

This is the **cartoon** answer to character cloning. Face-swap models such as
InstantID are built for photographs and behave poorly on stylised characters.

## Prerequisites

The existing kohya_ss stack is reused; nothing needs to be installed:

```
D:\bro\train\
    .venv\                 torch 2.11 + CUDA, accelerate
    sd-scripts\            sdxl_train_network.py
    train_bramble.ps1      the proven 6 GB recipe
```

The recipe: SDXL LoRA, rank 16, 640 px, bf16, AdamW8bit, gradient
checkpointing, cached latents, 24 epochs. On the RTX 4050 it takes roughly
**2 hours for 20 images**.

## Dataset requirements

- **10–30 images** of the character.
- Full-body front, side, three-quarter and back references.
- Several poses (standing, walking, sitting, pointing) and a few expressions.
- Plain backgrounds; the cutout pipeline can also supply poses.
- Fill the character's `appearance` and `clothing` fields first. Captions are
  built from them, and empty fields mean a weak LoRA.

The trainer pulls every `reference` and `pose` image attached to the character.

## Train

```powershell
cd D:\bro\CartoonStudio

# inspect what will be used
backend\.venv\Scripts\python.exe scripts\train_character_lora.py `
  --project-id <project_id> --character Kokoro --dry-run

# build the dataset and captions only
backend\.venv\Scripts\python.exe scripts\train_character_lora.py `
  --project-id <project_id> --character Kokoro --prepare-only

# train, install into ComfyUI, and assign to the character
backend\.venv\Scripts\python.exe scripts\train_character_lora.py `
  --project-id <project_id> --character Kokoro
```

Options: `--trigger`, `--epochs`, `--resolution`, `--trainer-root`,
`--no-assign`, `--allow-few`.

Output:

```
D:\bro\CartoonStudio\training\<slug>\dataset\
D:\bro\CartoonStudio\training\<slug>\output\<slug>_sdxl.safetensors
D:\bro\ComfyUI\Models\loras\<slug>_sdxl.safetensors
```

The script assigns the LoRA to the character at strength **0.8** unless
`--no-assign` is passed.

## Caption and trigger

Each image gets a caption of the form:

```
<trigger>, <name>, <description>, <appearance>, wearing <clothing>, <view/pose>, full body, plain light background
```

The trigger defaults to the character slug (`kokoro`). Scene prompts already
include the character name, so the same token activates the LoRA in shots.

## Use it

- Character Studio → model override: `lora_name = <slug>_sdxl.safetensors`,
  strength 0.7–0.85.
- Scene/keyframe generation uses the character override automatically.
- Keep the LoRA and the canonical image together: the LoRA supplies identity,
  the canonical image still supplies framing and reference control.

## Limits

- A LoRA trained mostly on standing references biases toward standing poses.
  Include varied poses in the dataset.
- Too many near-duplicate images overfit the background or one outfit. Curate.
- Retrain after a wardrobe change; do not stack two character LoRAs.
- A LoRA is not a face swap. It reproduces the design it was trained on, which
  is exactly what a series needs.
