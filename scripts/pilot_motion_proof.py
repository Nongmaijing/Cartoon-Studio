"""Motion proof: three Wan i2v clips with real dialogue, exported as a short reel."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8010"
STATE = Path(__file__).resolve().parents[1] / "data" / "pilot_test_01.json"
EPISODE_NAME = "Motion Proof 01"

# shot -> (dialogue key or None)
CLIPS = [
    ("s08", "s08_0"),
    ("s13", "s13_0"),
    ("s26", None),
]

FPS = 24
FRAMES = 97          # 4.04 s
DURATION_MS = int(FRAMES / FPS * 1000)

MOTION_PROMPT = (
    "subtle natural character motion, blinks and shifts weight, scarf and fur move in a light breeze, "
    "slow cinematic camera push, consistent character design, no text"
)
NEGATIVE = "text, watermark, deformed, extra limbs, morphing, flicker, duplicate character"


def wait(c: httpx.Client, job_id: str, label: str, timeout: float = 3600) -> dict:
    started = time.monotonic()
    last = -10
    while time.monotonic() - started < timeout:
        job = c.get(f"/api/jobs/{job_id}").json()
        progress = int(float(job.get("progress") or 0))
        if progress >= last + 10:
            last = progress
            print(f"  {label}: {progress}% {job.get('status')}", flush=True)
        if job["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(6)
    raise TimeoutError(job_id)


def main() -> None:
    data = json.loads(STATE.read_text(encoding="utf-8"))
    project_id = data["project_id"]
    with httpx.Client(base_url=BASE, timeout=240) as c:
        c.post("/api/v1/resources/free")
        assets = {}
        for sid, _ in CLIPS:
            scene_id = data["scenes"][sid]
            keyframe = data["keyframes"][sid]
            print(f"{sid}: animating from {keyframe}", flush=True)
            response = c.post(f"/api/scenes/{scene_id}/generate", json={
                "kind": "video",
                "start_image": keyframe,
                "width": 832,
                "height": 480,
                "length": FRAMES,
                "fps": FPS,
                "steps": 20,
                "cfg": 5.0,
                "seed": 4242,
                "prompt": MOTION_PROMPT,
                "negative_prompt": NEGATIVE,
            })
            if response.status_code != 202:
                raise RuntimeError(f"{sid} request failed: {response.status_code} {response.text[:200]}")
            job = wait(c, response.json()["job"]["id"], sid)
            if job["status"] != "completed":
                raise RuntimeError(f"{sid} failed: {job.get('error')}")
            assets[sid] = job["outputs"][0]["asset_id"]
            print(f"{sid}: {assets[sid]}", flush=True)
            data.setdefault("motion_proof", {})[sid] = assets[sid]
            STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")

        episode = c.post("/api/episodes", json={
            "project_id": project_id,
            "name": EPISODE_NAME,
            "description": "Three animated beats from Bramble and the Last Lantern.",
        }).json()
        episode_id = episode["id"]

        segments, audio = [], []
        cursor = 0
        for sid, line_key in CLIPS:
            segments.append({
                "scene_id": data["scenes"][sid],
                "asset_id": assets[sid],
                "kind": "video",
                "duration_ms": DURATION_MS,
                "trim_start_ms": 0,
                "transition": "fade" if sid == "s08" else "cut",
                "motion": "none",
                "label": sid,
            })
            if line_key:
                line = data["dialogue"].get(line_key)
                if line and line.get("audio_asset_id"):
                    audio.append({
                        "asset_id": line["audio_asset_id"],
                        "start_ms": cursor + 350,
                        "volume": 1.0,
                        "loop": False,
                        "label": line_key,
                        "kind": "dialogue",
                    })
            cursor += DURATION_MS

        timeline = {
            "segments": segments,
            "audio": audio,
            "settings": {
                "width": 960,
                "height": 540,
                "fps": 24,
                "subtitles": "soft",
                "background_music_asset_id": data.get("music_asset_id"),
                "background_music_volume": 0.25,
                "fade_duration_ms": 350,
            },
        }
        c.put(f"/api/episodes/{episode_id}/timeline", json=timeline)
        c.post(f"/api/episodes/{episode_id}/export")
        for _ in range(600):
            ep = c.get(f"/api/episodes/{episode_id}").json()
            if ep.get("status") in {"completed", "failed", "cancelled"}:
                print(json.dumps({k: ep.get(k) for k in ("status", "output_url", "output_path", "error")}, indent=1))
                data["motion_proof_episode"] = episode_id
                STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")
                return
            time.sleep(5)
        raise TimeoutError("export")


if __name__ == "__main__":
    main()
