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
    lumi = state["characters"].get("Lumi the Little Light") or state["characters"].get("Lumi the Firefly")
    patched = client.patch(
        f"{BASE}/api/characters/{lumi['id']}",
        json={
            "name": "Lumi the Little Fox",
            "description": "a small orange fox with a red bandana, a brave little friend and a little light in Milo's life",
            "appearance": "small orange fox, white muzzle, red bandana, bright friendly eyes",
            "style": "flat 2D western TV cartoon, bold clean black outlines, solid flat colors, no 3D",
        },
    ).json()
    state["characters"].pop("Lumi the Little Light", None)
    state["characters"].pop("Lumi the Firefly", None)
    state["characters"]["Lumi the Little Fox"] = patched

    scene = next(item for item in state["scenes"] if item["name"] == "A Tiny Glow")
    print("SCENE", scene["name"], scene["id"], flush=True)
    job = client.post(
        f"{BASE}/api/scenes/{scene['id']}/generate",
        json={
            "kind": "keyframe",
            "width": 1024,
            "height": 576,
            "steps": 28,
            "cfg": 6.5,
            "seed": 9202,
            "prompt": (
                "exactly two orange cartoon foxes in a mossy forest clearing: Milo, a larger orange fox with a white muzzle "
                "and a red scarf, kneeling beside a big green leaf; Lumi, a much smaller orange fox with a white muzzle and "
                "a red bandana, caught under the leaf looking worried. Both foxes are orange. Flat 2D western TV cartoon, "
                "bold clean black outlines, solid flat colors, no humans, no green fox, no extra characters, no text, no watermark"
            ),
            "negative_prompt": (
                "green fox, two large foxes, human, child, lantern, egg, 3d, Pixar, photorealistic, extra characters, "
                "text, watermark, signature, logo, extra limbs, extra tails"
            ),
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
