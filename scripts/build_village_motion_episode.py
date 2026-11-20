"""Build a short village-life motion proof with Wan 2.2 image-to-video.

Uses the proven 832x480 / 97-frame / 20-step recipe. Each shot takes roughly
five minutes on the RTX 4050; the script reuses a scene's latest video when
``--reuse`` is passed, so it can resume without regenerating.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import load_config  # noqa: E402
from app.services.assets import store_asset_from_path  # noqa: E402
from app.services.audio_synth import synthesize_ambience, synthesize_ambient_music  # noqa: E402

API = "http://127.0.0.1:8010"
PROJECT_ID = "b1ff88aadcf3"
PROJECT_NAME = "Village Life - Morning"
EPISODE_NAME = "Village Life - Motion Proof"
FPS = 24
LENGTH = 97
SEGMENT_MS = 4042
NEGATIVE = (
    "camera movement, pan, zoom, warping, morphing, flicker, distorted geometry, "
    "extra objects, text, watermark"
)

BEATS = [
    {
        "scene": "05 Simmering pot",
        "scene_id": "84a730649507",
        "image": "92fcaec2e9d6",
        "prompt": (
            "steam rises gently from the copper pot, hanging herbs sway slightly, warm "
            "window light, static camera, locked composition, consistent cozy kitchen"
        ),
    },
    {
        "scene": "07 Laundry breeze",
        "scene_id": "6ac6be3a3280",
        "image": "4967b4777f0a",
        "prompt": (
            "white sheets lift and settle in the breeze, soft clouds drift, village roofs "
            "steady, static camera, consistent scene, gentle natural motion"
        ),
    },
    {
        "scene": "08 Rain and tea",
        "scene_id": "e60f18198b9f",
        "image": "d287effdc085",
        "prompt": (
            "rain slides slowly down the window glass, tea steam rises, warm lamp glow steady, "
            "static camera, consistent cozy interior, minimal motion"
        ),
    },
]


def _api(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, path, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text[:500]}")
    return response.json() if response.content else {}


def _wait_job(client: httpx.Client, job_id: str, timeout: float = 900) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = _api(client, "GET", f"/api/jobs/{job_id}")
        if job.get("status") in {"completed", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(4)
    raise TimeoutError(job_id)


def _find(items: list[dict], name: str) -> dict | None:
    return next((item for item in items if item.get("name") == name), None)


def _latest_video(client: httpx.Client, scene_id: str) -> str | None:
    media = _api(client, "GET", f"/api/scenes/{scene_id}/media")
    videos = [item for item in media if str(item.get("mime") or "").startswith("video/")]
    # Prefer the proven 832x480 class; never reuse the corrupted low-res tests.
    good = [
        item
        for item in videos
        if int((item.get("meta") or {}).get("width") or 0) >= 800
        and int((item.get("meta") or {}).get("height") or 0) >= 450
    ]
    videos = good or videos
    return videos[-1]["id"] if videos else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reuse", action="store_true", help="Reuse an existing scene video")
    parser.add_argument("--episode-name", default=EPISODE_NAME)
    args = parser.parse_args()

    with httpx.Client(base_url=API, timeout=120) as client:
        if _api(client, "GET", "/api/health").get("status") != "ok":
            raise SystemExit("Backend is not healthy.")
        projects = _api(client, "GET", "/api/projects")
        project = _find(projects, PROJECT_NAME)
        if not project:
            raise SystemExit(f"Project '{PROJECT_NAME}' not found. Run the still village builder first.")
        project_id = project["id"]

        timeline_segments = []
        total_ms = 0
        for index, beat in enumerate(BEATS):
            print(f"[{index + 1}/{len(BEATS)}] {beat['scene']}")
            if args.dry_run:
                print(f"  prompt: {beat['prompt'][:100]}...")
                timeline_segments.append(
                    {
                        "scene_id": beat["scene_id"],
                        "asset_id": "DRY",
                        "kind": "video",
                        "duration_ms": SEGMENT_MS,
                        "transition": "fade" if index in (0, len(BEATS) - 1) else "cut",
                        "label": beat["scene"],
                    }
                )
                total_ms += SEGMENT_MS
                continue

            video_id = _latest_video(client, beat["scene_id"]) if args.reuse else None
            if not video_id:
                body = {
                    "project_id": project_id,
                    "scene_id": beat["scene_id"],
                    "start_image": beat["image"],
                    "workflow_id": "wan22_i2v",
                    "prompt": beat["prompt"],
                    "negative_prompt": NEGATIVE,
                    "width": 832,
                    "height": 480,
                    "length": LENGTH,
                    "fps": FPS,
                    "steps": 20,
                    "cfg": 5.0,
                    "seed": 5000 + index,
                }
                generated = _api(client, "POST", "/api/animation/generate", json=body)
                job = _wait_job(client, generated["job"]["id"])
                if job.get("status") != "completed" or not job.get("outputs"):
                    raise RuntimeError(f"Wan failed for {beat['scene']}: {job.get('error')}")
                video_id = job["outputs"][0]["asset_id"]
                print(f"  generated {video_id} in {job.get('execution_seconds')}s")
            else:
                print(f"  reusing {video_id}")
            duration_ms = SEGMENT_MS
            timeline_segments.append(
                {
                    "scene_id": beat["scene_id"],
                    "asset_id": video_id,
                    "kind": "video",
                    "duration_ms": duration_ms,
                    "transition": "fade" if index in (0, len(BEATS) - 1) else "cut",
                    "label": beat["scene"],
                }
            )
            total_ms += duration_ms

        total_seconds = total_ms / 1000
        print(f"\ntimeline: {len(timeline_segments)} clips, {total_seconds:.1f}s")
        if args.dry_run:
            print("dry run complete.")
            return

        audio_assets = []
        incoming = ROOT / "outputs" / project_id / "audio" / "_incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        for kind, generator, volume in (
            ("music", lambda p: synthesize_ambient_music(p, total_seconds, 24000), 0.30),
            ("birds", lambda p: synthesize_ambience(p, "birds", total_seconds, 24000), 0.34),
            ("wind", lambda p: synthesize_ambience(p, "wind", total_seconds, 24000), 0.18),
        ):
            target = incoming / f"village_motion_{kind}.wav"
            generator(target)
            stored = store_asset_from_path(
                project_id=project_id,
                subdir="audio",
                filename=f"village_motion_{kind}.wav",
                source_path=target,
                kind="audio",
                mime="audio/wav",
                meta={
                    "kind": "music" if kind == "music" else "sfx",
                    "effect": kind,
                    "duration_ms": int(total_seconds * 1000),
                    "generator": "local procedural",
                },
            )
            audio_assets.append((stored, kind, volume))

        episodes = _api(client, "GET", f"/api/episodes?project_id={project_id}")
        episode = _find(episodes, args.episode_name)
        if not episode:
            episode = _api(
                client,
                "POST",
                "/api/episodes",
                json={
                    "project_id": project_id,
                    "name": args.episode_name,
                    "description": "Wan image-to-video village proof.",
                },
            )
            print(f"created episode {episode['id']}")
        else:
            print(f"reusing episode {episode['id']}")

        timeline = {
            "segments": timeline_segments,
            "audio": [
                {
                    "asset_id": asset["id"],
                    "start_ms": 0,
                    "volume": volume,
                    "kind": "music" if kind == "music" else "sfx",
                    "label": kind,
                }
                for asset, kind, volume in audio_assets
            ],
            "settings": {
                "width": 1280,
                "height": 720,
                "fps": 24,
                "subtitles": "none",
                "fade_duration_ms": 400,
            },
        }
        _api(client, "PUT", f"/api/episodes/{episode['id']}/timeline", json=timeline)
        _api(client, "POST", f"/api/episodes/{episode['id']}/export", json={})
        deadline = time.time() + 900
        status = {}
        while time.time() < deadline:
            status = _api(client, "GET", f"/api/episodes/{episode['id']}/export")
            print(f"  export: {status.get('status')} {status.get('progress')}%")
            if status.get("status") in {"completed", "failed", "cancelled"}:
                break
            time.sleep(3)
        if status.get("status") != "completed":
            raise SystemExit(f"Export failed: {status}")
        print(json.dumps(status, indent=2)[:1000])
        print(f"\nepisode file: /api/episodes/{episode['id']}/file")


if __name__ == "__main__":
    main()
