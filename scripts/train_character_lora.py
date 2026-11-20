"""Train a per-character SDXL LoRA from a character's approved media.

This is the character-cloning path for 2D characters: a small LoRA locks the
face, hair and wardrobe far better than prompt text or IP-Adapter alone.

It reuses the existing kohya_ss stack at D:\\bro\\train (torch 2.11 + CUDA, the
same recipe used for bramble_sdxl).

Examples:
    python scripts/train_character_lora.py --project-id <id> --character Kokoro --dry-run
    python scripts/train_character_lora.py --project-id <id> --character Kokoro
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import load_config  # noqa: E402

API = "http://127.0.0.1:8010"
TRAINER_ROOT = Path(r"D:\bro\train")
COMFY_LORAS = Path(r"D:\bro\ComfyUI\Models\loras")


def _api(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, path, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text[:400]}")
    return response.json() if response.content else {}


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "character"


def _checkpoint(name: str) -> Path:
    config = load_config()
    for root in (config.get("comfyui") or {}).get("models_dirs") or []:
        candidate = Path(root) / "checkpoints" / name
        if candidate.exists():
            return candidate
    fallback = Path(r"D:\bro\ComfyUI\Models\checkpoints") / name
    if fallback.exists():
        return fallback
    raise SystemExit(f"Checkpoint not found: {name}")


def _caption(character: dict, label: str, trigger: str) -> str:
    parts = [trigger, character.get("name") or "", character.get("description") or ""]
    parts.append(character.get("appearance") or "")
    clothing = character.get("clothing") or ""
    if clothing:
        parts.append(f"wearing {clothing}")
    if label:
        parts.append(label)
    parts.append("full body, plain light background")
    text = ", ".join(part.strip() for part in parts if part and part.strip())
    return " ".join(text.split())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--character", required=True, help="Character id or name")
    parser.add_argument("--trigger", default="", help="LoRA trigger token (default: character slug)")
    parser.add_argument("--epochs", type=int, default=24)
    parser.add_argument("--resolution", type=int, default=640)
    parser.add_argument("--trainer-root", default=str(TRAINER_ROOT))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--no-assign", action="store_true", help="Do not set the LoRA on the character")
    parser.add_argument("--allow-few", action="store_true", help="Train with fewer than 8 images")
    args = parser.parse_args()

    trainer = Path(args.trainer_root)
    accelerate = trainer / ".venv" / "Scripts" / "accelerate.exe"
    train_script = trainer / "sd-scripts" / "sdxl_train_network.py"
    trainer_python = trainer / ".venv" / "Scripts" / "python.exe"
    for path in (accelerate, train_script, trainer_python):
        if not path.exists():
            raise SystemExit(f"Training stack is incomplete; missing {path}")

    with httpx.Client(base_url=API, timeout=120) as client:
        characters = _api(client, "GET", f"/api/characters?project_id={args.project_id}")
        character = next(
            (item for item in characters if item["id"] == args.character or item["name"] == args.character),
            None,
        )
        if not character:
            raise SystemExit(f"Character '{args.character}' not found in project {args.project_id}.")
        media = _api(client, "GET", f"/api/characters/{character['id']}/media")
        usable = [
            item
            for item in media
            if item.get("role") in {"reference", "pose"}
            and str(item.get("mime") or "").startswith("image/")
        ]
        if len(usable) < 8 and not args.allow_few:
            raise SystemExit(
                f"Only {len(usable)} reference/pose images. Generate a turnaround and a few poses, "
                "or pass --allow-few."
            )

        trigger = (args.trigger or _slug(character["name"])).strip()
        if not character.get("appearance") or not character.get("clothing"):
            print(
                "WARNING: appearance/clothing are empty. Captions will be weak and the LoRA "
                "will learn the outfit poorly. Fill both fields first."
            )
        slug = _slug(character["name"])
        work = ROOT / "training" / slug
        dataset = work / "dataset"
        output = work / "output"
        print(f"character : {character['name']} ({character['id']})")
        print(f"trigger   : {trigger}")
        print(f"images    : {len(usable)}")
        print(f"dataset   : {dataset}")
        print(f"output    : {output}")
        if args.dry_run:
            for item in usable:
                print(f"  {item['id']}  {item.get('role'):9}  {item.get('label')}")
            return

        dataset.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        for item in usable:
            suffix = Path(item.get("filename") or "image.png").suffix or ".png"
            target = dataset / f"{item['id']}{suffix}"
            data = client.get(f"/api/assets/{item['id']}/file").content
            target.write_bytes(data)
            caption = _caption(character, str(item.get("label") or ""), trigger)
            target.with_suffix(".txt").write_text(caption, encoding="utf-8")
        print(f"prepared {len(usable)} images and captions")

        if args.prepare_only:
            return

        checkpoint_name = ((load_config().get("models") or {}).get("checkpoints") or {}).get("sdxl") or ""
        checkpoint = _checkpoint(checkpoint_name or "DreamShaperXL_1.0.safetensors")
        output_name = f"{slug}_sdxl"
        command = [
            str(accelerate),
            "launch",
            "--num_cpu_threads_per_process",
            "2",
            "--mixed_precision",
            "bf16",
            str(train_script),
            "--pretrained_model_name_or_path",
            str(checkpoint),
            "--train_data_dir",
            str(dataset),
            "--output_dir",
            str(output),
            "--output_name",
            output_name,
            "--resolution",
            str(args.resolution),
            "--network_module",
            "networks.lora",
            "--network_dim",
            "16",
            "--network_alpha",
            "16",
            "--network_train_unet_only",
            "--caption_extension",
            ".txt",
            "--train_batch_size",
            "1",
            "--max_train_epochs",
            str(args.epochs),
            "--learning_rate",
            "1e-4",
            "--unet_lr",
            "1e-4",
            "--lr_scheduler",
            "cosine",
            "--lr_warmup_steps",
            "40",
            "--optimizer_type",
            "AdamW8bit",
            "--mixed_precision",
            "bf16",
            "--save_precision",
            "bf16",
            "--gradient_checkpointing",
            "--cache_latents",
            "--cache_text_encoder_outputs",
            "--sdpa",
            "--lowram",
            "--max_data_loader_n_workers",
            "1",
            "--save_every_n_epochs",
            str(max(1, args.epochs // 2)),
            "--min_snr_gamma",
            "5",
            "--noise_offset",
            "0.02",
            "--bucket_no_upscale",
            "--seed",
            "20261120",
        ]
        print("running:", " ".join(command[:4]), "...")
        result = subprocess.run(command, cwd=str(trainer))
        if result.returncode != 0:
            raise SystemExit(f"Training failed with exit code {result.returncode}")

        candidates = sorted(output.glob(f"{output_name}*.safetensors"), key=lambda p: p.stat().st_mtime)
        if not candidates:
            raise SystemExit("Training finished but produced no LoRA file.")
        model = candidates[-1]
        COMFY_LORAS.mkdir(parents=True, exist_ok=True)
        installed = COMFY_LORAS / f"{output_name}.safetensors"
        installed.write_bytes(model.read_bytes())
        print(f"\nLoRA trained: {model}")
        print(f"Installed  : {installed}")

        if not args.no_assign:
            _api(
                client,
                "PATCH",
                f"/api/characters/{character['id']}/model",
                json={"lora_name": installed.name, "lora_strength": 0.8},
            )
            print(f"Assigned '{installed.name}' to {character['name']} at strength 0.8")


if __name__ == "__main__":
    main()
