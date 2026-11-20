"""Build a proof episode from the imported narration in Project1/voices.

Steps:
1. Create (or reuse) a project.
2. Normalize each narration MP3 to -16 LUFS / 48 kHz mono and transcribe it.
3. Register the WAV + transcript cues as a project audio asset.
4. Create six scenes with a generated painterly plate each.
5. Build the timeline: one image segment per narration beat plus the narration
   audio, then export a 720p MP4 with soft subtitles.

Read-only with respect to the source MP3s. Run with ``--dry-run`` first.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import load_config  # noqa: E402
from app.services.assets import store_asset_from_path  # noqa: E402

_WHISPER = None

API = "http://127.0.0.1:8010"
DEFAULT_VOICES = Path(r"G:\old desktop\my stories\Project1\voices")
DEFAULT_PROJECT = "Gura Sen - The Rain's Answer"
DEFAULT_EPISODE = "Gura Sen - Narrated Proof"

BEATS = [
    {
        "voice": "Narration1_Opening.mp3",
        "scene": "01 Opening - The Unbuyable",
        "bg_name": "Drought Village at Dusk",
        "bg_prompt": (
            "a drought-stricken Indian village at dusk, cracked earth, empty wells, "
            "small mud huts, a distant landlord palace with fountains, warm dusty haze"
        ),
        "description": "Cracked fields and an empty well under a heavy dusk sky.",
        "action": "Still landscape; heat haze.",
        "camera": "wide establishing shot",
        "motion": "zoom_in",
        "transition": "fade",
    },
    {
        "voice": "Narration2_Zamindar.mp3",
        "scene": "02 The Zamindar",
        "bg_name": "Zamindar Palace Courtyard",
        "bg_prompt": (
            "a wealthy zamindar palace courtyard with marble fountains and golden gates, "
            "dry cracked fields beyond the walls, harsh afternoon sun, ornate arches"
        ),
        "description": "Marble fountains inside the palace; dust and cracked earth outside.",
        "action": "Water runs in the courtyard while the land outside is dry.",
        "camera": "slow dolly forward",
        "motion": "zoom_in",
        "transition": "cut",
    },
    {
        "voice": "Narration3_Offerings.mp3",
        "scene": "03 The Offerings",
        "bg_name": "Golden Temple on the Hill",
        "bg_prompt": (
            "a golden temple on a bare hill, cloud-shaped golden idols, a herd of cows "
            "wandering below, empty pale sky, no rain, dry grass"
        ),
        "description": "A golden temple and cloud-shaped idols on a bare hill.",
        "action": "Cows wander past the offerings; the sky stays empty.",
        "camera": "low angle looking up the hill",
        "motion": "pan_right",
        "transition": "cut",
    },
    {
        "voice": "Narration4_Beggar.mp3",
        "scene": "04 The Beggar",
        "bg_name": "Banyan Tree and Palace Gate",
        "bg_prompt": (
            "an old banyan tree beside a dusty road, clay pots and a woven mat beneath it, "
            "a palace gate in the distance, late afternoon shadows, quiet and still"
        ),
        "description": "A banyan tree, a mat, and clay pots beside the palace road.",
        "action": "The tree shades an empty mat; golden pots are carried in the distance.",
        "camera": "medium wide, static",
        "motion": "none",
        "transition": "cut",
    },
    {
        "voice": "Narration5_Rain.mp3",
        "scene": "05 The Rain",
        "bg_name": "Storm Over Dry Fields",
        "bg_prompt": (
            "night sky over dry fields, dark storm clouds gathering, first rain falling, "
            "distant village lights, wet earth beginning to shine"
        ),
        "description": "Storm clouds gather over the fields; the first rain falls.",
        "action": "Rain begins; dust turns to mud.",
        "camera": "wide, slow tilt up",
        "motion": "zoom_out",
        "transition": "cut",
    },
    {
        "voice": "Narration6_Closing.mp3",
        "scene": "06 Closing - The Answer",
        "bg_name": "Rain over the Revived Village",
        "bg_prompt": (
            "monsoon rain over a green revived village, a great banyan tree, wet earth, "
            "soft grey light, puddles reflecting the sky, calm and tender"
        ),
        "description": "Green returns; rain falls softly over the village and the banyan.",
        "action": "Rain settles; the land is green again.",
        "camera": "wide, slow pull out",
        "motion": "zoom_out",
        "transition": "fade",
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
    raise TimeoutError(f"Job {job_id} did not finish in {timeout}s")


def _ffmpeg() -> str:
    configured = str((load_config().get("ffmpeg") or {}).get("path") or "").strip()
    if configured and Path(configured).exists():
        return configured
    found = shutil.which("ffmpeg")
    if not found:
        raise RuntimeError("FFmpeg not found.")
    return found


def _normalize(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            _ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(source),
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ar", "48000", "-ac", "1", "-map_metadata", "-1",
            str(target),
        ],
        check=True,
    )


def _transcribe(path: Path) -> dict:
    global _WHISPER
    if _WHISPER is None:
        from faster_whisper import WhisperModel

        _WHISPER = WhisperModel(
            str(ROOT / "models" / "asr" / "faster-whisper-small"),
            device="cpu",
            compute_type="int8",
        )
    segments, info = _WHISPER.transcribe(str(path), beam_size=5, vad_filter=True)
    cues = []
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        cues.append(
            {
                "start_ms": int(segment.start * 1000),
                "end_ms": int(segment.end * 1000),
                "text": text,
            }
        )
    return {
        "language": info.language,
        "duration_ms": int(round(info.duration * 1000)),
        "text": " ".join(cue["text"] for cue in cues),
        "cues": cues,
    }


def _find(items: list[dict], name: str) -> dict | None:
    return next((item for item in items if item.get("name") == name), None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--voices-dir", default=str(DEFAULT_VOICES))
    parser.add_argument("--project-name", default=DEFAULT_PROJECT)
    parser.add_argument("--episode-name", default=DEFAULT_EPISODE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    voices = Path(args.voices_dir)
    missing = [beat["voice"] for beat in BEATS if not (voices / beat["voice"]).exists()]
    if missing:
        raise SystemExit(f"Missing narration files: {missing}")

    with httpx.Client(base_url=API, timeout=120) as client:
        health = _api(client, "GET", "/api/health")
        if health.get("status") != "ok":
            raise SystemExit("Backend is not healthy.")

        projects = _api(client, "GET", "/api/projects")
        project = _find(projects, args.project_name)
        if args.dry_run:
            print(f"project: {project['id'] if project else '(new) ' + args.project_name}")
        elif project:
            print(f"reusing project {project['id']}")
        else:
            project = _api(
                client,
                "POST",
                "/api/projects",
                json={"name": args.project_name, "description": "Narrated fable proof episode."},
            )
            print(f"created project {project['id']}")
        project_id = project["id"] if project else "DRY"

        backgrounds = _api(client, "GET", f"/api/backgrounds?project_id={project_id}") if project else []
        scenes = _api(client, "GET", f"/api/scenes?project_id={project_id}") if project else []
        episodes = _api(client, "GET", f"/api/episodes?project_id={project_id}") if project else []

        narration_assets = []
        timeline_segments = []
        timeline_audio = []
        cursor_ms = 0

        for index, beat in enumerate(BEATS):
            source = voices / beat["voice"]
            print(f"\n[{index + 1}/6] {beat['voice']}")
            normalized = ROOT / "outputs" / project_id / "audio" / "_incoming" / (
                Path(beat["voice"]).stem + "_48k.wav"
            )

            if args.dry_run:
                print(f"  would normalize -> {normalized}")
                transcript = _transcribe(source)
                print(f"  language={transcript['language']} duration={transcript['duration_ms']}ms cues={len(transcript['cues'])}")
                duration_ms = transcript["duration_ms"]
                narration_assets.append({"dry": True})
                bg_asset = {"id": "DRY_BG"}
                scene = {"id": "DRY_SCENE"}
            else:
                _normalize(source, normalized)
                transcript = _transcribe(normalized)
                asset = store_asset_from_path(
                    project_id=project_id,
                    subdir="audio/narration",
                    filename=normalized.name,
                    source_path=normalized,
                    kind="audio",
                    mime="audio/wav",
                    meta={
                        "kind": "voice",
                        "text": transcript["text"],
                        "duration_ms": transcript["duration_ms"],
                        "cues": transcript["cues"],
                        "language": transcript["language"],
                        "source_file": str(source),
                        "normalized_lufs": -16,
                    },
                )
                narration_assets.append(asset)
                duration_ms = transcript["duration_ms"]
                print(f"  audio asset {asset['id']} ({duration_ms/1000:.1f}s, {len(transcript['cues'])} cues)")

                background = _find(backgrounds, beat["bg_name"])
                if not background:
                    background = _api(
                        client,
                        "POST",
                        "/api/backgrounds",
                        json={
                            "project_id": project_id,
                            "name": beat["bg_name"],
                            "description": beat["bg_prompt"],
                            "aspect_ratio": "16:9",
                            "width": 1280,
                            "height": 720,
                        },
                    )
                    backgrounds.append(background)
                media = _api(client, "GET", f"/api/backgrounds/{background['id']}/media")
                if not media:
                    generated = _api(
                        client,
                        "POST",
                        f"/api/backgrounds/{background['id']}/generate",
                        json={"use_preset": False, "width": 1280, "height": 720, "steps": 20, "cfg": 6, "seed": 1000 + index},
                    )
                    job = _wait_job(client, generated["job"]["id"])
                    if job.get("status") != "completed":
                        raise RuntimeError(f"Background job failed: {job.get('error')}")
                    media = _api(client, "GET", f"/api/backgrounds/{background['id']}/media")
                bg_asset = media[-1]
                print(f"  plate {bg_asset['id']} ({bg_asset.get('filename')})")

                scene = _find(scenes, beat["scene"])
                if not scene:
                    scene = _api(
                        client,
                        "POST",
                        "/api/scenes",
                        json={
                            "project_id": project_id,
                            "name": beat["scene"],
                            "description": beat["description"],
                            "action": beat["action"],
                            "camera": beat["camera"],
                            "duration": max(1.0, duration_ms / 1000),
                            "background_id": background["id"],
                        },
                    )
                    scenes.append(scene)
                print(f"  scene {scene['id']}")

            timeline_segments.append(
                {
                    "scene_id": scene["id"],
                    "asset_id": bg_asset["id"],
                    "kind": "image",
                    "duration_ms": duration_ms,
                    "transition": beat["transition"],
                    "motion": beat["motion"],
                    "label": beat["scene"],
                }
            )
            if not args.dry_run:
                timeline_audio.append(
                    {
                        "asset_id": narration_assets[-1]["id"],
                        "start_ms": cursor_ms,
                        "volume": 1.0,
                        "kind": "dialogue",
                        "label": Path(beat["voice"]).stem,
                    }
                )
            cursor_ms += duration_ms

        print(f"\ntimeline: {len(timeline_segments)} segments, {cursor_ms/1000:.1f}s")
        if args.dry_run:
            print("dry run complete; no files or records were written.")
            return

        episode = _find(episodes, args.episode_name)
        if not episode:
            episode = _api(
                client,
                "POST",
                "/api/episodes",
                json={
                    "project_id": project_id,
                    "name": args.episode_name,
                    "description": "Six-beat narration proof with painterly plates.",
                },
            )
            print(f"created episode {episode['id']}")
        else:
            print(f"reusing episode {episode['id']}")

        timeline = {
            "segments": timeline_segments,
            "audio": timeline_audio,
            "settings": {
                "width": 1280,
                "height": 720,
                "fps": 24,
                "subtitles": "soft",
                "fade_duration_ms": 400,
            },
        }
        saved = _api(client, "PUT", f"/api/episodes/{episode['id']}/timeline", json=timeline)
        print(f"saved timeline: {len(saved.get('timeline', {}).get('segments', []))} segments")

        _api(client, "POST", f"/api/episodes/{episode['id']}/export", json={})
        deadline = time.time() + 900
        while time.time() < deadline:
            status = _api(client, "GET", f"/api/episodes/{episode['id']}/export")
            print(f"  export: {status.get('status')} {status.get('progress')}%")
            if status.get("status") in {"completed", "failed", "cancelled"}:
                break
            time.sleep(3)
        if status.get("status") != "completed":
            raise SystemExit(f"Export failed: {status}")
        print(json.dumps(status, indent=2)[:2000])
        print(f"\nepisode file: /api/episodes/{episode['id']}/file")


if __name__ == "__main__":
    main()
