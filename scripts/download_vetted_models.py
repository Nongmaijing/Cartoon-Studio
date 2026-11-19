"""Download vetted Cartoon Studio model sources through the app service.

Usage:
    python scripts/download_vetted_models.py --dry-run
    python scripts/download_vetted_models.py --wait
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
load_dotenv(ROOT / ".env")

from app.config import load_config  # noqa: E402
from app.services import model_download_service as downloads  # noqa: E402

DEFAULT_MODELS = ["SDXL Base 1.0", "Blue Pencil XL", "Juggernaut XL"]
INSTALLED_EQUIVALENT = {"DreamShaper XL"}


def target_path(filename: str) -> Path:
    config = load_config()
    dirs = [Path(value) for value in (config.get("comfyui", {}).get("models_dirs") or []) if value]
    if not dirs:
        raise SystemExit("No ComfyUI model directories configured.")
    return dirs[0] / "checkpoints" / filename


async def wait_for(download_id: str) -> dict:
    while True:
        state = downloads.get_download(download_id)
        if not state:
            raise SystemExit(f"Download {download_id} disappeared")
        print(
            f"  {state['status']:10s} {state['percent']:6.2f}% "
            f"{state['speed_mbps']:7.2f} MB/s {state['message']}",
            flush=True,
        )
        if state["status"] in ("completed", "failed", "cancelled"):
            return state
        await asyncio.sleep(5)


async def main_async(args) -> int:
    failures = 0
    for name in args.models:
        info = downloads.describe(name)
        if not info.get("available"):
            print(f"SKIP {name}: no vetted direct download")
            continue
        if name in INSTALLED_EQUIVALENT:
            print(f"SKIP {name}: already installed under the configured checkpoint name")
            continue
        target = target_path(info["filename"])
        free = shutil.disk_usage(target.parent if target.parent.exists() else target.parent.parent).free
        print(
            f"{name}: {info['size_gb']} GB -> {target} | free {free / 1024**3:.2f} GB",
            flush=True,
        )
        if target.exists():
            print(f"SKIP {name}: target already exists")
            continue
        if args.dry_run:
            continue
        try:
            state = await downloads.start_download(name, accept_license=True, actor="local")
        except ValueError as exc:
            print(f"FAIL {name}: {exc}")
            failures += 1
            continue
        result = await wait_for(state["id"])
        if result["status"] != "completed":
            print(f"FAIL {name}: {result['error'] or result['status']}")
            failures += 1
        else:
            print(f"DONE {name}: {result['path']}", flush=True)
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--wait", action="store_true", help="wait for each download (default)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
