"""Lock the best pilot art, rewrite profiles to match, and retry the Grumble."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8010"
STATE = Path(__file__).resolve().parents[1] / "data" / "pilot_test_01.json"

PICKS = {
    "bramble": "46a26558b26f",
    "tock": "72e10b8dfdb4",
    "moss": "7015e5b769fc",
}
PICK_BG = {"village": "0394cca4ea09", "meadow": "300066fb4dd6"}

PROFILES = {
    "bramble": {
        "description": (
            "Bramble is a small girl, eight years old, brave in her head and nervous in her tummy. She talks to "
            "herself when she is scared and narrates her own courage. Two tiny hedgehogs follow her everywhere."
        ),
        "style": "soft storybook cartoon, warm russet and mustard palette",
        "clothing": "mustard knitted scarf, olive pinafore dress, brown boots, small leather satchel",
        "appearance": "small girl with curly ash-grey hair, round dark eyes, freckles, cream shirt",
    },
    "tock": {
        "description": (
            "Tock is a small mouse who counts everything: steps, raindrops, scary moments. He is precise, anxious "
            "and fiercely loyal, and checks his pocket watch when he is nervous."
        ),
        "style": "storybook animal character, cream and brass palette",
        "clothing": "cream coat and waistcoat, top hat, pocket watch on a chain",
        "appearance": "small cream-grey mouse, large round ears, dark eyes, long whiskers",
    },
    "moss": {
        "description": (
            "Grandmother Moss is an ancient tortoise who speaks in short proverbs and moves like the weather. "
            "She is warm, unhurried and knows more than she says."
        ),
        "style": "storybook elder, mossy textures, deep green palette",
        "clothing": "a shawl of soft green moss",
        "appearance": "enormous ancient tortoise, moss-covered shell, wrinkled kind face",
    },
}

GRUMBLE_PROMPT = (
    "a small round grey-violet rain cloud character floating in the air, two simple sleepy eyes, "
    "tiny lightning bolt freckles, three raindrops falling, simple flat shapes, children's picture book illustration"
)
GRUMBLE_NEG = (
    "human, person, boy, girl, body, arms, legs, clothes, hoodie, monster, realistic photo, 3d render, text"
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
        for key, asset in PICKS.items():
            char_id = data["characters"][key]
            c.post(f"/api/characters/{char_id}/canonical", json={"asset_id": asset})
            c.patch(f"/api/characters/{char_id}", json=PROFILES[key])
            data.setdefault("art", {})[key] = {"canonical": asset}
            print("locked", key, asset)
        for key, asset in PICK_BG.items():
            data.setdefault("background_assets", {})[key] = asset
            print("bg", key, asset)

        grumble = data["characters"]["grumble"]
        result = c.post(f"/api/characters/{grumble}/generate", json={
            "kind": "reference", "label": "front", "width": 768, "height": 1152,
            "steps": 24, "cfg": 6.0, "seed": 5301,
            "prompt": GRUMBLE_PROMPT, "negative_prompt": GRUMBLE_NEG,
            "use_reference": False,
        }).json()
        job = wait(c, result["job"]["id"])
        if job["status"] == "completed":
            asset = job["outputs"][0]["asset_id"]
            data["art"]["grumble"] = {"canonical": asset}
            c.post(f"/api/characters/{grumble}/canonical", json={"asset_id": asset})
            print("grumble ->", asset)
        else:
            print("grumble failed", job.get("error"))
        STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
