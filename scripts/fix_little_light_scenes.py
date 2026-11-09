from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8010"
STATE_PATH = Path(r"D:\bro\CartoonStudio\projects\little_light_state.json")


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
    lumi = state["characters"]["Lumi the Firefly"]
    patched = client.patch(
        f"{BASE}/api/characters/{lumi['id']}",
        json={
            "name": "Lumi the Little Light",
            "description": "a tiny glowing round creature with a warm golden light and tiny wings; a little light friend, not a human, not a lantern",
            "appearance": "small round glowing golden body, tiny wings, warm light, tiny smiling face",
            "style": "flat 2D western TV cartoon, bold clean black outlines, solid flat colors, no 3D",
        },
    ).json()
    state["characters"]["Lumi the Little Light"] = patched
    state["characters"].pop("Lumi the Firefly", None)

    scene_specs = {
        "Milo Hears a Sparkle": {
            "seed": 9101,
            "prompt": (
                "single small orange cartoon fox with a red scarf walking on a dusk forest path, "
                "full body visible in the foreground, centered, side view, the fox is the main subject, "
                "tiny golden sparkle in the distance, flat 2D western TV cartoon, bold clean black outlines, "
                "solid flat colors, no humans, no other characters, no text, no watermark"
            ),
            "negative_prompt": (
                "empty path, no characters, human, child, two foxes, extra fox, 3d, Pixar, photorealistic, "
                "text, watermark, signature, logo"
            ),
        },
        "A Tiny Glow": {
            "seed": 9102,
            "prompt": (
                "exactly two characters: Milo the small orange cartoon fox with a red scarf kneeling beside a big green leaf, "
                "and Lumi a tiny glowing round golden creature with tiny wings caught under the leaf; "
                "flat 2D western TV cartoon, bold clean black outlines, solid flat colors, no humans, "
                "no second fox, no lantern, no egg, no text, no watermark"
            ),
            "negative_prompt": (
                "two foxes, extra fox, human, child, lantern, egg, 3d, Pixar, photorealistic, text, watermark, "
                "signature, logo, extra characters"
            ),
        },
    }

    for scene in state["scenes"]:
        spec = scene_specs.get(scene["name"])
        if not spec:
            continue
        print("SCENE", scene["name"], scene["id"], flush=True)
        job = client.post(
            f"{BASE}/api/scenes/{scene['id']}/generate",
            json={
                "kind": "keyframe",
                "width": 1024,
                "height": 576,
                "steps": 28,
                "cfg": 6.5,
                "seed": spec["seed"],
                "prompt": spec["prompt"],
                "negative_prompt": spec["negative_prompt"],
            },
        ).json()["job"]
        finished = wait_job(client, job["id"], scene["name"])
        output = finished["outputs"][0]
        scene.setdefault("keyframe_history", []).append(scene.get("keyframe_asset_id"))
        scene["keyframe_asset_id"] = output["asset_id"]
        print(f"  NEW KEYFRAME {output['asset_id']} {output['filename']}", flush=True)

    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("STATE UPDATED", STATE_PATH, flush=True)


if __name__ == "__main__":
    main()
