"""Build a Bramble LoRA dataset from the character's own sheet generation."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8010"
STATE = Path(__file__).resolve().parents[1] / "data" / "pilot_test_01.json"
DATASET = Path(r"D:\bro\train\dataset\10_bramble")
CAPTION = (
    "bramble, small storybook cartoon girl, curly ash-grey hair, round dark eyes, freckles, "
    "mustard knitted scarf, olive pinafore dress, cream shirt, brown boots"
)


def wait(c: httpx.Client, job_id: str) -> dict:
    for _ in range(400):
        job = c.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(3)
    raise TimeoutError(job_id)


def main() -> None:
    data = json.loads(STATE.read_text(encoding="utf-8"))
    char_id = data["characters"]["bramble"]
    canonical = data["art"]["bramble"]["canonical"]
    DATASET.mkdir(parents=True, exist_ok=True)

    assets: list[str] = [canonical]
    with httpx.Client(base_url=BASE, timeout=180) as c:
        for kind, seed in (("turnaround", 6101), ("expressions", 6102), ("poses", 6103)):
            response = c.post(f"/api/characters/{char_id}/sheet/{kind}", json={
                "reference_asset_id": canonical,
                "allow_unapproved_reference": True,
                "seed": seed,
                "width": 768,
                "height": 1152,
                "denoise": 0.45,
            })
            if response.status_code != 202:
                print(kind, "request failed", response.status_code, response.text[:200])
                continue
            payload = response.json()
            jobs = payload.get("jobs") or []
            print(kind, "jobs:", [item.get("id") if isinstance(item, dict) else item for item in jobs])
            for item in jobs:
                job_id = item.get("id") if isinstance(item, dict) else item
                if not job_id:
                    continue
                job = wait(c, str(job_id))
                if job["status"] != "completed":
                    print("  job failed", job_id, job.get("error"))
                    continue
                for output in job.get("outputs") or []:
                    assets.append(output["asset_id"])

    assets = list(dict.fromkeys(assets))
    index = 0
    with httpx.Client(base_url=BASE, timeout=120) as c:
        for asset_id in assets:
            response = c.get(f"/api/assets/{asset_id}/file")
            if response.status_code != 200:
                continue
            index += 1
            stem = f"{index:03d}"
            (DATASET / f"{stem}.png").write_bytes(response.content)
            (DATASET / f"{stem}.txt").write_text(CAPTION, encoding="utf-8")
    print(f"dataset images: {index}")
    print(f"dataset dir: {DATASET}")


if __name__ == "__main__":
    main()
