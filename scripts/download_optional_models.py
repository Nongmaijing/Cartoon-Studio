"""Download optional vetted ComfyUI models with resume and verification.

Usage:
    python scripts/download_optional_models.py --dry-run
    python scripts/download_optional_models.py --accept-licenses

Hashes must be the official HuggingFace LFS SHA-256 (from
``https://huggingface.co/api/models/<repo>?blobs=true`` -> ``siblings[].lfs.sha256``),
never the CDN ``ETag`` header. ETags are opaque and will falsely quarantine
good files.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import shutil
import time
from pathlib import Path

import httpx

MODEL_ROOT = Path(r"D:\bro\ComfyUI\Models")
SOURCES = [
    {
        "name": "ControlNet SDXL OpenPose",
        "url": "https://huggingface.co/xinsir/controlnet-openpose-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors",
        "target": MODEL_ROOT / "controlnet" / "controlnet-openpose-sdxl-1.0.safetensors",
        "size": 2502139104,
        # Official HuggingFace LFS SHA-256, not the CDN ETag.
        "sha256": "b8524e557a7df60d081f5d4a0eb109967d107df217943bf88c2d99b9ebcc06c5",
        "license": "Apache-2.0",
    },
    {
        "name": "IP-Adapter Plus SDXL (ViT-H)",
        "url": "https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors",
        "target": MODEL_ROOT / "ipadapter" / "ip-adapter-plus_sdxl_vit-h.safetensors",
        "size": 847517512,
        # Official HuggingFace LFS SHA-256, not the CDN ETag.
        "sha256": "3f5062b8400c94b7159665b21ba5c62acdcd7682262743d7f2aefedef00e6581",
        "license": "Apache-2.0",
    },
    {
        "name": "CLIP ViT-H-14 image encoder",
        # ViT-H (hidden 1280, projection 1024). Required by the -vit-h IP-Adapter
        # presets. Do NOT use sdxl_models/image_encoder here: that file is ViT-bigG.
        "url": "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors",
        "target": MODEL_ROOT / "clip_vision" / "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
        "size": 2528373448,
        # Official HuggingFace LFS SHA-256, not the CDN ETag.
        "sha256": "6ca9667da1ca9e0b0f75e46bb030f7e011f44f86cbfb8d5a36590fcd7507b030",
        "license": "Apache-2.0",
    },
    {
        "name": "CLIP ViT-bigG-14 image encoder (VIT-G preset)",
        # ViT-bigG (hidden 1664, projection 1280). Only used by the VIT-G / bigG
        # IP-Adapter presets; kept for future use and hash-verified.
        "url": "https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/image_encoder/model.safetensors",
        "target": MODEL_ROOT / "clip_vision" / "CLIP-ViT-bigG-14-laion2B-39B-b160k.safetensors",
        "size": 3689912664,
        # Official HuggingFace LFS SHA-256, not the CDN ETag.
        "sha256": "657723e09f46a7c3957df651601029f66b1748afb12b419816330f16ed45d64d",
        "license": "Apache-2.0",
    },
    {
        "name": "Real-ESRGAN x4plus",
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "target": MODEL_ROOT / "upscale_models" / "RealESRGAN_x4plus.pth",
        "size": 67040989,
        "sha256": None,
        "license": "BSD-3-Clause (verify weights)",
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def download(source: dict) -> bool:
    target: Path = source["target"]
    target.parent.mkdir(parents=True, exist_ok=True)
    expected = int(source["size"])
    free = shutil.disk_usage(target.parent).free
    if free < expected + 2 * 1024**3:
        print(f"FAIL {source['name']}: not enough disk ({free / 1024**3:.1f} GB free)")
        return False
    if target.exists() and target.stat().st_size == expected:
        print(f"SKIP {source['name']}: already complete at {target}")
        return True
    part = target.with_suffix(target.suffix + ".part")
    start = part.stat().st_size if part.exists() else 0
    if start > expected:
        part.unlink()
        start = 0
    headers = {"User-Agent": "CartoonStudio-Utility/1.0"}
    if start:
        headers["Range"] = f"bytes={start}-"
    print(f"{source['name']}: {expected / 1024**3:.2f} GB -> {target}", flush=True)
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=120.0), follow_redirects=True) as client:
        async with client.stream("GET", source["url"], headers=headers) as response:
            if response.status_code not in (200, 206):
                print(f"FAIL {source['name']}: HTTP {response.status_code}")
                return False
            if response.status_code == 200 and start:
                start = 0
            mode = "ab" if start else "wb"
            written = start
            last = time.time()
            with part.open(mode) as handle:
                async for chunk in response.aiter_bytes(1024 * 1024):
                    handle.write(chunk)
                    written += len(chunk)
                    now = time.time()
                    if now - last >= 2:
                        pct = written / expected * 100 if expected else 0
                        print(f"  {pct:6.2f}% {written / 1024**3:6.2f} GB", flush=True)
                        last = now
                handle.flush()
                os.fsync(handle.fileno())
    actual = part.stat().st_size
    if actual != expected:
        print(f"FAIL {source['name']}: size {actual} != {expected}")
        return False
    if source.get("sha256"):
        print(f"  verifying SHA256 {source['name']}...", flush=True)
        actual_sha = await asyncio.to_thread(sha256_file, part)
        if actual_sha.lower() != str(source["sha256"]).lower():
            bad = part.with_suffix(part.suffix + ".bad")
            part.replace(bad)
            print(f"FAIL {source['name']}: SHA256 mismatch, quarantined {bad}")
            return False
    else:
        print(f"  SHA256 {await asyncio.to_thread(sha256_file, part)} (no published hash)", flush=True)
    os.replace(part, target)
    print(f"DONE {source['name']}: {target}", flush=True)
    return True


async def verify(source: dict) -> bool:
    target: Path = source["target"]
    if not target.exists():
        print(f"FAIL {source['name']}: missing {target}")
        return False
    expected_size = int(source["size"])
    actual_size = target.stat().st_size
    if actual_size != expected_size:
        print(f"FAIL {source['name']}: size {actual_size} != {expected_size}")
        return False
    actual_sha = await asyncio.to_thread(sha256_file, target)
    expected_sha = source.get("sha256")
    if expected_sha and actual_sha.lower() != str(expected_sha).lower():
        print(f"FAIL {source['name']}: SHA256 {actual_sha} != {expected_sha}")
        return False
    print(f"OK   {source['name']}: {actual_size} bytes {actual_sha}")
    return True


async def main_async(args) -> int:
    failures = 0
    for source in SOURCES:
        if args.verify:
            if not await verify(source):
                failures += 1
            continue
        if args.dry_run:
            print(
                f"{source['name']}: {source['size'] / 1024**3:.2f} GB -> {source['target']} "
                f"licence={source['license']}"
            )
            continue
        if not await download(source):
            failures += 1
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true", help="re-hash installed files only")
    parser.add_argument("--accept-licenses", action="store_true")
    args = parser.parse_args()
    if not (args.dry_run or args.verify) and not args.accept_licenses:
        raise SystemExit("Pass --accept-licenses after reviewing the listed licences.")
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
