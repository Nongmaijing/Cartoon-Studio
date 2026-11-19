"""Generate the recurring Little Wonder Village backgrounds as drafts.

Usage:
    python scripts/generate_pilot_backgrounds.py --project-id 16556b67d331 --dry-run
    python scripts/generate_pilot_backgrounds.py --project-id 16556b67d331

The script never overwrites an existing background image. It creates missing
background records, generates one 16:9 draft per location, and writes a summary
plus contact sheet to the chosen output directory.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

BASE = "http://127.0.0.1:8010"

BACKGROUNDS = [
    {
        "name": "Old Oak Clearing",
        "description": (
            "Wide friendly oak tree with a broad shady canopy and a low root seat, "
            "grassy village clearing, soft winding path, distant cosy cottages, "
            "warm late-afternoon light, inviting preschool storybook staging"
        ),
        "seed": 20262001,
    },
    {
        "name": "Garden Patch",
        "description": (
            "Small sunny garden bed beside the old oak, soft dark soil, low wooden "
            "edging, young green seedlings, a little watering can, warm daylight, "
            "clear uncluttered staging"
        ),
        "seed": 20262002,
    },
    {
        "name": "Village Path",
        "description": (
            "Winding village path through green hedges and cosy cottages, distant "
            "gentle stream, bright friendly sky, warm inviting preschool palette"
        ),
        "seed": 20262003,
    },
    {
        "name": "Stream Bank",
        "description": (
            "Gentle shallow stream with smooth stones, reeds and soft grassy banks, "
            "dappled sunlight, calm safe preschool environment"
        ),
        "seed": 20262004,
    },
]


def wait_job(client: httpx.Client, job_id: str, timeout: float = 1200) -> dict:
    deadline = time.time() + timeout
    status = None
    while time.time() < deadline:
        status = client.get(f"{BASE}/api/jobs/{job_id}").json()
        if status.get("status") in ("completed", "failed", "cancelled"):
            return status
        time.sleep(4)
    return status or {"status": "timeout", "outputs": []}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--output", default="background_drafts")
    parser.add_argument("--steps", type=int, default=24)
    parser.add_argument("--cfg", type=float, default=6.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.output)
    client = httpx.Client(timeout=httpx.Timeout(120.0, read=300.0))
    existing = client.get(f"{BASE}/api/backgrounds", params={"project_id": args.project_id}).json()
    names = {row["name"].strip().lower(): row for row in existing}

    plan = []
    for spec in BACKGROUNDS:
        plan.append(
            {
                "name": spec["name"],
                "exists": spec["name"].strip().lower() in names,
                "background_id": names.get(spec["name"].strip().lower(), {}).get("id"),
                "seed": spec["seed"],
            }
        )
    if args.dry_run:
        print(json.dumps({"project_id": args.project_id, "plan": plan}, indent=2))
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for spec, item in zip(BACKGROUNDS, plan):
        background_id = item["background_id"]
        if not background_id:
            response = client.post(
                f"{BASE}/api/backgrounds",
                json={
                    "project_id": args.project_id,
                    "name": spec["name"],
                    "description": spec["description"],
                    "aspect_ratio": "16:9",
                    "width": 1024,
                    "height": 576,
                },
            )
            response.raise_for_status()
            background_id = response.json()["id"]
            print("CREATED", spec["name"], background_id, flush=True)
        else:
            print("REUSED", spec["name"], background_id, flush=True)

        response = client.post(
            f"{BASE}/api/backgrounds/{background_id}/generate",
            json={
                "width": 1024,
                "height": 576,
                "steps": args.steps,
                "cfg": args.cfg,
                "seed": spec["seed"],
                "workflow_id": "sdxl_background",
                "use_preset": False,
            },
        )
        response.raise_for_status()
        job = response.json().get("job") or {}
        job_id = job.get("id")
        print("  job", job_id, flush=True)
        status = wait_job(client, job_id)
        outputs = []
        for output in status.get("outputs") or []:
            asset_id = output.get("asset_id")
            if not asset_id:
                continue
            image = client.get(f"{BASE}/api/assets/{asset_id}/file")
            if image.status_code != 200:
                continue
            path = out_dir / f"{asset_id}.png"
            path.write_bytes(image.content)
            outputs.append({"asset_id": asset_id, "path": str(path)})
        results.append(
            {
                "name": spec["name"],
                "background_id": background_id,
                "job_id": job_id,
                "status": status.get("status"),
                "seconds": status.get("execution_seconds"),
                "peak_vram_mb": status.get("peak_vram_mb"),
                "outputs": outputs,
            }
        )

    summary = out_dir / "backgrounds.json"
    summary.write_text(json.dumps(results, indent=2), encoding="utf-8")

    thumbnails = []
    for item in results:
        for output in item["outputs"]:
            path = Path(output["path"])
            if path.exists():
                image = Image.open(path).convert("RGB")
                image.thumbnail((512, 288))
                thumbnails.append((item["name"], image))
    if thumbnails:
        sheet = Image.new("RGB", (2 * 522, ((len(thumbnails) + 1) // 2) * 330), (18, 18, 22))
        draw = ImageDraw.Draw(sheet)
        for index, (label, image) in enumerate(thumbnails):
            x = (index % 2) * 522 + 5
            y = (index // 2) * 330 + 5
            sheet.paste(image, (x, y + 20))
            draw.text((x + 2, y + 3), label, fill=(255, 255, 255))
        sheet_path = out_dir / "contact_sheet.png"
        sheet.save(sheet_path)
        print("SHEET", sheet_path, flush=True)
    print("SUMMARY", summary, flush=True)


if __name__ == "__main__":
    main()
