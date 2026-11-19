"""Reshoot Bramble's shots with the trained LoRA, then rebuild and re-export."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8010"
STATE = Path(__file__).resolve().parents[1] / "data" / "pilot_test_01.json"
LORA = "bramble_sdxl.safetensors"

# Shots where Bramble is prominent enough to need the trained design.
RESHOOT = ["s03", "s06", "s08", "s10", "s11", "s13", "s18", "s22", "s25", "s27", "s32", "s38", "s40"]

EXTRA = (
    "bramble, small storybook cartoon girl, curly ash-grey hair, mustard knitted scarf, olive pinafore, "
    "brown boots, wide cinematic scene, location clearly visible, head and feet in frame"
)
NEGATIVE = (
    "character sheet, reference sheet, multiple views, plain background, studio backdrop, "
    "cropped head, cropped body, text, watermark, extra limbs, deformed"
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
    with httpx.Client(base_url=BASE, timeout=180) as c:
        # Apply the LoRA globally for this pass (scenes do not read per-character LoRAs).
        c.put("/api/v1/models/config", json={"models": {"lora": {
            "name": LORA, "strength": 0.85, "architecture": "sdxl",
        }}})
        print("lora applied:", c.get("/api/v1/models/config").json()["lora"])
        character_id = data["characters"]["bramble"]
        c.patch(f"/api/characters/{character_id}/model", json={
            "lora_name": LORA, "lora_strength": 0.85,
        })
        for index, sid in enumerate(RESHOOT):
            scene_id = data["scenes"][sid]
            c.patch(f"/api/scenes/{scene_id}", json={"settings": {
                "seed": 9000 + index,
                "width": 1024,
                "height": 576,
                "steps": 28,
                "cfg": 6.0,
            }})
            response = c.post(f"/api/scenes/{scene_id}/generate", json={
                "kind": "keyframe",
                "prompt": EXTRA,
                "negative_prompt": NEGATIVE,
            })
            if response.status_code != 202:
                print(sid, "request failed", response.status_code, response.text[:160])
                continue
            job = wait(c, response.json()["job"]["id"])
            if job["status"] != "completed":
                print(sid, "failed", job.get("error"))
                continue
            data["keyframes"][sid] = job["outputs"][0]["asset_id"]
            STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(sid, "->", data["keyframes"][sid])
        # Do not leave a character LoRA global.
        c.put("/api/v1/models/config", json={"models": {"lora": {
            "name": "", "strength": 0.8, "architecture": "",
        }}})
        print("global lora cleared")


if __name__ == "__main__":
    main()
