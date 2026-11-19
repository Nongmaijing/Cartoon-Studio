"""Regenerate the four Pilot Test 01 characters with explicit mascot prompts."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8010"
STATE = Path(__file__).resolve().parents[1] / "data" / "pilot_test_01.json"

FIXES = {
    "bramble": {
        "prompt": (
            "anthropomorphic hedgehog child character standing upright, small round hedgehog girl with soft "
            "russet spines, cream muzzle and belly, mustard knitted scarf, olive canvas satchel, small brown boots, "
            "2D flat vector cartoon mascot, thick clean outlines, simple rounded shapes, cel shading, not human"
        ),
        "negative": (
            "human, human girl, child, realistic hedgehog, hamster, pet animal, 3d render, painterly, "
            "detailed fur, photorealistic, text, watermark"
        ),
        "seed": 5101,
    },
    "tock": {
        "prompt": (
            "tiny palm-sized brass clockwork toy mouse, riveted metal seams, one droopy ear, glowing amber eyes, "
            "small wheel feet, bottle-cap hat, key in his back, 2D flat vector cartoon mascot, thick clean outlines, "
            "simple rounded shapes, cel shading"
        ),
        "negative": (
            "top hat, gentleman, coat, waistcoat, living mouse, realistic mouse, human hands, 3d render, "
            "painterly, photorealistic, text, watermark"
        ),
        "seed": 5102,
    },
    "moss": {
        "prompt": (
            "ancient tortoise with a mossy shell covered in tiny mushrooms, twig spectacles, kind wrinkled face, "
            "2D flat vector cartoon mascot, thick clean outlines, simple rounded shapes, cel shading"
        ),
        "negative": "realistic, 3d render, photorealistic, human, text, watermark",
        "seed": 5103,
    },
    "grumble": {
        "prompt": (
            "a small floating cartoon storm cloud with two sleepy eyes, soft rounded violet-grey cloud body, "
            "tiny lightning freckles, a few small raindrops, no arms, no legs, 2D flat vector cartoon mascot, "
            "thick clean outlines"
        ),
        "negative": (
            "human, boy, girl, person, coat, body, arms, legs, realistic cloud photograph, 3d render, "
            "text, watermark"
        ),
        "seed": 5104,
    },
}

BACKGROUND_FIXES = {
    "meadow": {
        "prompt": "wide open night meadow, tall silver grass, many glowing fireflies, distant hills, no buildings",
        "negative": "house, cabin, building, people, text",
        "seed": 5201,
    },
    "village": {
        "prompt": "crooked storybook cottages, small brass bells hanging under every roof edge, warm window light, dusk",
        "negative": "people, text, modern buildings",
        "seed": 5202,
    },
}


def wait(c: httpx.Client, job_id: str) -> dict:
    for _ in range(400):
        job = c.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(3)
    raise TimeoutError(job_id)


def main() -> None:
    data = json.loads(STATE.read_text(encoding="utf-8"))
    with httpx.Client(base_url=BASE, timeout=180) as c:
        for key, fix in FIXES.items():
            char_id = data["characters"][key]
            result = c.post(f"/api/characters/{char_id}/generate", json={
                "kind": "reference", "label": "front",
                "width": 768, "height": 1152, "steps": 24, "cfg": 6.0, "seed": fix["seed"],
                "prompt": fix["prompt"], "negative_prompt": fix["negative"],
                "use_reference": False,
            }).json()
            job = wait(c, result["job"]["id"])
            if job["status"] != "completed":
                print(key, "FAILED", job.get("error"))
                continue
            asset = job["outputs"][0]["asset_id"]
            c.post(f"/api/characters/{char_id}/canonical", json={"asset_id": asset})
            data.setdefault("art", {})[key] = {"canonical": asset}
            STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(key, "->", asset)

        for key, fix in BACKGROUND_FIXES.items():
            bg_id = data["backgrounds"][key]
            result = c.post(f"/api/backgrounds/{bg_id}/generate", json={
                "width": 1024, "height": 576, "seed": fix["seed"],
                "prompt": fix["prompt"], "negative_prompt": fix["negative"],
            }).json()
            job = wait(c, result["job"]["id"])
            if job["status"] != "completed":
                print(key, "FAILED", job.get("error"))
                continue
            asset = job["outputs"][0]["asset_id"]
            data.setdefault("background_assets", {})[key] = asset
            STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print("bg", key, "->", asset)


if __name__ == "__main__":
    main()
