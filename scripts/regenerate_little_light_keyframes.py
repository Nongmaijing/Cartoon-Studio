from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8010"
STATE_PATH = Path(r"D:\bro\CartoonStudio\projects\little_light_state.json")

STYLE_EXTRA = (
    "flat 2D western TV cartoon, bold clean black outlines, solid flat colors, simple shapes, "
    "children's animation, no 3D, no Pixar, no Disney 3D, no humans, no text, no watermark, "
    "no signature, no logo"
)
NEGATIVE = (
    "3d render, Pixar, Disney 3D, photorealistic, human, human child, boy, girl, person, crowd, "
    "extra characters, lantern, egg, campfire, depth of field, blurry, text, watermark, signature, "
    "logo, extra limbs, extra tails, duplicate body parts, malformed paws"
)


def wait_job(client: httpx.Client, job_id: str, label: str, timeout: float = 600) -> dict:
    start = time.perf_counter()
    last = None
    while time.perf_counter() - start < timeout:
        time.sleep(1.5)
        job = client.get(f"{BASE}/api/jobs/{job_id}", timeout=60).json()
        if job["status"] != last:
            print(f"  [{label}] {job['status']} {job['progress']:.0f}%", flush=True)
            last = job["status"]
        if job["status"] in ("completed", "failed", "cancelled", "interrupted"):
            if job["status"] != "completed":
                raise RuntimeError(f"{label} failed: {job.get('error')}")
            return job
    raise TimeoutError(f"{label} timed out")


def main() -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    client = httpx.Client(timeout=120)

    milo = state["characters"]["Milo the Fox"]
    lumi = state["characters"]["Lumi the Firefly"]
    client.patch(
        f"{BASE}/api/characters/{milo['id']}",
        json={
            "description": "a small orange cartoon fox with a white muzzle, black-tipped ears and a bushy tail; he is an animal, not a human",
            "appearance": "orange fur, white muzzle, black-tipped ears, bushy tail, red scarf; quadruped fox",
            "style": "flat 2D western TV cartoon, bold clean black outlines, solid flat colors, no 3D",
        },
    )
    client.patch(
        f"{BASE}/api/characters/{lumi['id']}",
        json={
            "description": "a tiny glowing firefly: a small golden insect with two translucent wings and a warm light; not a human, not a lantern, not an egg",
            "appearance": "small golden insect body, two translucent wings, warm glow, tiny smiling face",
            "style": "flat 2D western TV cartoon, bold clean black outlines, solid flat colors, no 3D",
        },
    )

    actions = {
        "Milo Hears a Sparkle": (
            "Milo the fox walks alone on the dusk forest path, seen from the side, ears perked. "
            "A tiny golden firefly sparkle glows far between the trees. Only one fox; no humans; no campfire."
        ),
        "A Tiny Glow": (
            "Milo the fox kneels beside a big green leaf. Lumi the tiny glowing firefly is caught under the leaf, "
            "glowing faintly. Only one fox and one tiny firefly; no humans; no lantern; no egg."
        ),
        "The Rescue": (
            "Milo the fox gently lifts the big leaf with his paw. Lumi the tiny glowing firefly floats up, "
            "glowing brighter. Only one fox and one tiny firefly; no humans."
        ),
        "Friends in the Light": (
            "Milo the fox and Lumi the tiny glowing firefly walk together on a moonlit forest path. "
            "Lumi glows warmly beside Milo. Fireflies twinkle in the trees. Only one fox and one tiny firefly; "
            "no humans; no other characters."
        ),
    }
    seeds = {
        "Milo Hears a Sparkle": 9001,
        "A Tiny Glow": 9002,
        "The Rescue": 9003,
        "Friends in the Light": 9004,
    }

    updated = []
    for scene in state["scenes"]:
        name = scene["name"]
        if name in actions:
            scene["action"] = actions[name]
            client.patch(f"{BASE}/api/scenes/{scene['id']}", json={"action": actions[name]})
        print("SCENE", name, scene["id"], flush=True)
        job = client.post(
            f"{BASE}/api/scenes/{scene['id']}/generate",
            json={
                "kind": "keyframe",
                "width": 1024,
                "height": 576,
                "steps": 28,
                "cfg": 6.5,
                "seed": seeds.get(name, 9000),
                "prompt": STYLE_EXTRA,
                "negative_prompt": NEGATIVE,
            },
        ).json()["job"]
        finished = wait_job(client, job["id"], name)
        output = finished["outputs"][0]
        scene.setdefault("keyframe_history", []).append(scene.get("keyframe_asset_id"))
        scene["keyframe_asset_id"] = output["asset_id"]
        print(f"  NEW KEYFRAME {output['asset_id']} {output['filename']}", flush=True)
        updated.append(scene)

    state["scenes"] = updated
    state["style_extra"] = STYLE_EXTRA
    state["negative"] = NEGATIVE
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("STATE UPDATED", STATE_PATH, flush=True)


if __name__ == "__main__":
    main()
