from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8010"
STATE_PATH = Path(r"D:\bro\CartoonStudio\projects\forest_friends_state.json")


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
    client = httpx.Client(timeout=180)
    project = client.post(
        f"{BASE}/api/projects",
        json={
            "name": "Forest Friends",
            "description": "A new children's story project with a cast of kind, curious animal friends.",
        },
    ).json()
    project_id = project["id"]
    print("PROJECT", project_id, project["name"], flush=True)

    character = client.post(
        f"{BASE}/api/characters",
        json={
            "project_id": project_id,
            "name": "Nico the Raccoon",
            "description": "a curious, kind young raccoon who loves solving little mysteries and helping friends",
            "style": "flat 2D western TV cartoon, bold clean black outlines, solid flat colors, soft rounded shapes, friendly expression",
            "clothing": "teal satchel",
            "appearance": "grey fur, black mask, white muzzle, striped tail, yellow neckerchief, small round ears",
            "voice_engine": "kokoro",
            "voice_name": "am_michael",
            "voice_rate": 1,
            "voice_pitch": 0,
            "voice_volume": 100,
        },
    ).json()
    print("CHARACTER", character["id"], character["name"], flush=True)

    reference = client.post(
        f"{BASE}/api/characters/{character['id']}/generate",
        json={
            "kind": "reference",
            "label": "front",
            "width": 768,
            "height": 1152,
            "steps": 28,
            "cfg": 6.5,
            "seed": 777,
            "reference_mode": "identity",
            "denoise": 0.5,
        },
    ).json()
    job = reference["job"]
    finished = wait_job(client, job["id"], "reference")
    asset = finished["outputs"][0]
    print("REFERENCE", asset["asset_id"], asset["filename"], flush=True)
    client.post(
        f"{BASE}/api/characters/{character['id']}/canonical",
        json={"asset_id": asset["asset_id"]},
    )
    print("CANONICAL SET", asset["asset_id"], flush=True)

    extra = {}
    for kind, label, seed in (
        ("expression", "happy", 778),
        ("pose", "waving", 779),
    ):
        result = client.post(
            f"{BASE}/api/characters/{character['id']}/generate",
            json={
                "kind": kind,
                "label": label,
                "width": 768,
                "height": 1152,
                "steps": 28,
                "cfg": 6.5,
                "seed": seed,
                "reference_mode": "identity",
                "denoise": 0.5,
            },
        ).json()
        finished = wait_job(client, result["job"]["id"], f"{kind} {label}")
        output = finished["outputs"][0]
        extra[f"{kind}:{label}"] = output["asset_id"]
        print("EXTRA", kind, label, output["asset_id"], output["filename"], flush=True)

    state = {
        "project_id": project_id,
        "project_name": project["name"],
        "character_id": character["id"],
        "character_name": character["name"],
        "canonical_asset_id": asset["asset_id"],
        "reference_asset_id": asset["asset_id"],
        "extras": extra,
    }
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("STATE", STATE_PATH, flush=True)


if __name__ == "__main__":
    main()
