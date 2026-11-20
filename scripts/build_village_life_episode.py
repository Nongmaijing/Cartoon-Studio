"""Build a relaxing 'village life' style episode from original art.

Format target: 8 slow domestic vignettes, 16:9, music and ambience only, no
dialogue or subtitles. Inspired by the pacing of hand-painted lifestyle
montages, but with original prompts and generated art.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
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
DEFAULT_PROJECT = "Village Life - Morning"
DEFAULT_EPISODE = "Village Life - Morning Proof"
SEGMENT_MS = 8000
STYLE = (
    "ghibli-inspired hand-painted 2D animation, painterly gouache, rich saturated "
    "colors, soft morning light, detailed background, cinematic still"
)
NEGATIVE = (
    "photo, photorealistic, 3d render, cgi, blurry, low quality, deformed, "
    "extra limbs, extra fingers, text, watermark, signature, logo, cropped"
)

BEATS = [
    {
        "name": "01 Morning dough",
        "prompt": (
            "close-up of hands kneading bread dough on a floured wooden table, "
            "linen sleeves, steam from a kettle, warm cottage kitchen, morning sunlight"
        ),
        "motion": "zoom_in",
    },
    {
        "name": "02 Tomatoes and basil",
        "prompt": (
            "close-up of hands slicing ripe red tomatoes and basil on a wooden board, "
            "blue ceramic bowl, sunlit kitchen, rich color"
        ),
        "motion": "pan_right",
    },
    {
        "name": "03 Harvest basket",
        "prompt": (
            "woven basket of freshly picked tomatoes, basil and marigolds on a wooden "
            "veranda, morning dew, lush green garden behind"
        ),
        "motion": "zoom_out",
    },
    {
        "name": "04 Cat on the veranda",
        "prompt": (
            "grey cat sleeping on a sunlit wooden veranda, potted plants, soft laundry "
            "in the breeze, village rooftops and green hills beyond"
        ),
        "motion": "none",
    },
    {
        "name": "05 Simmering pot",
        "prompt": (
            "copper pot simmering on a wood stove, steam rising, hanging herbs, warm "
            "cottage kitchen, soft window light"
        ),
        "motion": "zoom_in",
    },
    {
        "name": "06 Village path",
        "prompt": (
            "narrow village path with wildflowers, bicycles leaning against a stone wall, "
            "green hills and morning mist"
        ),
        "motion": "pan_left",
    },
    {
        "name": "07 Laundry breeze",
        "prompt": (
            "white sheets drying on a line between wooden houses, breeze, village roofs, "
            "blue sky with soft clouds"
        ),
        "motion": "pan_right",
    },
    {
        "name": "08 Rain and tea",
        "prompt": (
            "rain on a cottage window, warm lamp and a cup of tea on the sill, blurred "
            "green village outside, cozy interior"
        ),
        "motion": "zoom_out",
    },
]


def _api(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, path, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text[:500]}")
    return response.json() if response.content else {}


def _wait_job(client: httpx.Client, job_id: str, timeout: float = 300) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = _api(client, "GET", f"/api/jobs/{job_id}")
        if job.get("status") in {"completed", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(2)
    raise TimeoutError(job_id)


def _find(items: list[dict], name: str) -> dict | None:
    return next((item for item in items if item.get("name") == name), None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-name", default=DEFAULT_PROJECT)
    parser.add_argument("--episode-name", default=DEFAULT_EPISODE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with httpx.Client(base_url=API, timeout=120) as client:
        if _api(client, "GET", "/api/health").get("status") != "ok":
            raise SystemExit("Backend is not healthy.")

        projects = _api(client, "GET", "/api/projects")
        project = _find(projects, args.project_name)
        if args.dry_run:
            print(f"project: {project['id'] if project else '(new)'}")
        elif project:
            print(f"reusing project {project['id']}")
        else:
            project = _api(
                client,
                "POST",
                "/api/projects",
                json={"name": args.project_name, "description": "Relaxing village-life vignettes."},
            )
            print(f"created project {project['id']}")
        project_id = project["id"] if project else "DRY"

        scenes = _api(client, "GET", f"/api/scenes?project_id={project_id}") if project else []
        episodes = _api(client, "GET", f"/api/episodes?project_id={project_id}") if project else []

        timeline_segments = []
        for index, beat in enumerate(BEATS):
            print(f"\n[{index + 1}/{len(BEATS)}] {beat['name']}")
            if args.dry_run:
                print(f"  prompt: {beat['prompt'][:100]}...")
                scene = {"id": "DRY"}
                asset = {"id": "DRY_IMG"}
            else:
                scene = _find(scenes, beat["name"])
                if not scene:
                    scene = _api(
                        client,
                        "POST",
                        "/api/scenes",
                        json={
                            "project_id": project_id,
                            "name": beat["name"],
                            "description": beat["prompt"],
                            "duration": SEGMENT_MS / 1000,
                        },
                    )
                    scenes.append(scene)
                job = _api(
                    client,
                    "POST",
                    "/api/generate",
                    json={
                        "project_id": project_id,
                        "workflow_id": "sdxl_txt2img",
                        "prompt": f"{beat['prompt']}, {STYLE}",
                        "negative_prompt": NEGATIVE,
                        "width": 1280,
                        "height": 720,
                        "steps": 20,
                        "cfg": 6,
                        "seed": 3100 + index,
                    },
                )
                done = _wait_job(client, job["id"])
                if done.get("status") != "completed" or not done.get("outputs"):
                    raise RuntimeError(f"Plate failed for {beat['name']}: {done.get('error')}")
                asset = done["outputs"][0]
                print(f"  plate {asset['asset_id']}  scene {scene['id']}")

            timeline_segments.append(
                {
                    "scene_id": scene["id"],
                    "asset_id": asset.get("asset_id") if not args.dry_run else "DRY_IMG",
                    "kind": "image",
                    "duration_ms": SEGMENT_MS,
                    "transition": "fade" if index in (0, len(BEATS) - 1) else "cut",
                    "motion": beat["motion"],
                    "label": beat["name"],
                }
            )

        total_seconds = len(BEATS) * SEGMENT_MS / 1000
        print(f"\ntimeline: {len(BEATS)} segments, {total_seconds:.0f}s")
        if args.dry_run:
            print("dry run complete; no files or records were written.")
            return

        audio_assets = []
        incoming = ROOT / "outputs" / project_id / "audio" / "_incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        for kind, generator, volume in (
            ("music", lambda p: synthesize_ambient_music(p, total_seconds, 24000), 0.30),
            ("birds", lambda p: synthesize_ambience(p, "birds", total_seconds, 24000), 0.34),
            ("wind", lambda p: synthesize_ambience(p, "wind", total_seconds, 24000), 0.18),
        ):
            target = incoming / f"village_{kind}.wav"
            generator(target)
            stored = store_asset_from_path(
                project_id=project_id,
                subdir="audio",
                filename=f"village_{kind}.wav",
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
            print(f"audio {kind}: {stored['id']}")

        episode = _find(episodes, args.episode_name)
        if not episode:
            episode = _api(
                client,
                "POST",
                "/api/episodes",
                json={
                    "project_id": project_id,
                    "name": args.episode_name,
                    "description": "Relaxing village-life vignettes with an original ambient score.",
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
                "fade_duration_ms": 500,
            },
        }
        _api(client, "PUT", f"/api/episodes/{episode['id']}/timeline", json=timeline)
        print("timeline saved")
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
        print(json.dumps(status, indent=2)[:1200])
        print(f"\nepisode file: /api/episodes/{episode['id']}/file")


if __name__ == "__main__":
    main()
