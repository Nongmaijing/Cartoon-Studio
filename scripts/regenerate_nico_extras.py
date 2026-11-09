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
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    client = httpx.Client(timeout=180)
    character_id = state["character_id"]
    specs = [
        ("expression", "happy", 8801, 0.70, "big joyful smile, sparkling happy eyes, cheerful expression, flat 2D cartoon"),
        ("pose", "waving", 8802, 0.78, "full body, standing, one arm raised waving hello, friendly smile, flat 2D cartoon"),
    ]
    for kind, label, seed, denoise, prompt in specs:
        result = client.post(
            f"{BASE}/api/characters/{character_id}/generate",
            json={
                "kind": kind,
                "label": label,
                "prompt": prompt,
                "width": 768,
                "height": 1152,
                "steps": 28,
                "cfg": 6.5,
                "seed": seed,
                "reference_mode": "identity",
                "denoise": denoise,
            },
        ).json()
        finished = wait_job(client, result["job"]["id"], f"{kind} {label}")
        output = finished["outputs"][0]
        state["extras"][f"{kind}:{label}"] = output["asset_id"]
        print("EXTRA", kind, label, output["asset_id"], output["filename"], flush=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("STATE UPDATED", flush=True)


if __name__ == "__main__":
    main()
