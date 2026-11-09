from __future__ import annotations

import json
import math
import struct
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.config import load_config
from app.services.assets import asset_file, store_asset_from_path

BASE = "http://127.0.0.1:8010"
STATE_PATH = Path(r"D:\bro\CartoonStudio\projects\little_light_state.json")
FONT = r"C\:/Windows/Fonts/comicbd.ttf"


def wait_job(client: httpx.Client, job_id: str, label: str, timeout: float = 900) -> dict:
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


def synth_music(path: Path, duration: float = 30.0, sr: int = 22050) -> None:
    n = int(duration * sr)
    buf = [0.0] * n
    chords = [
        (261.63, 329.63, 392.00),
        (196.00, 246.94, 293.66),
        (220.00, 261.63, 329.63),
        (174.61, 220.00, 261.63),
    ]
    chord_seconds = 4.0
    chord_samples = int(chord_seconds * sr)
    for block in range(0, n, chord_samples):
        chord = chords[(block // chord_samples) % len(chords)]
        end = min(n, block + chord_samples)
        for i in range(block, end):
            t = (i - block) / sr
            env = min(1.0, t / 0.25, (chord_seconds - t) / 0.25)
            pad = sum(math.sin(2 * math.pi * f * t) * 0.050 for f in chord)
            pad += math.sin(2 * math.pi * (chord[0] / 2) * t) * 0.035
            pad *= 0.85 + 0.15 * math.sin(2 * math.pi * 0.25 * t)
            buf[i] += pad * max(0.0, env)
    melody = [523.25, 659.25, 783.99, 659.25, 880.00, 783.99, 659.25, 587.33,
              523.25, 659.25, 783.99, 880.00, 783.99, 659.25, 587.33, 523.25]
    note_seconds = 0.5
    note_samples = int(note_seconds * sr)
    for index in range(int(duration / note_seconds) + 1):
        freq = melody[index % len(melody)]
        start = index * note_samples
        end = min(n, start + note_samples)
        for i in range(start, end):
            t = (i - start) / sr
            env = math.exp(-4.2 * t) * min(1.0, t / 0.012)
            value = math.sin(2 * math.pi * freq * t) * 0.070
            value += math.sin(2 * math.pi * freq * 2 * t) * 0.018
            buf[i] += value * env
    peak = max(abs(value) for value in buf) or 1.0
    scale = 0.78 / peak
    frames = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, value * scale)) * 32767)) for value in buf)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes(frames)


def synth_sparkle(path: Path, duration: float = 1.2, sr: int = 22050) -> None:
    n = int(duration * sr)
    buf = [0.0] * n
    for freq in (1200.0, 1800.0, 2400.0, 3200.0):
        for i in range(n):
            t = i / sr
            env = math.exp(-5.5 * t) * min(1.0, t / 0.01)
            buf[i] += math.sin(2 * math.pi * freq * t) * 0.16 * env
    peak = max(abs(value) for value in buf) or 1.0
    scale = 0.72 / peak
    frames = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, value * scale)) * 32767)) for value in buf)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes(frames)


def make_title_card(source: Path, output: Path) -> None:
    vf = (
        "scale=1280:720,"
        "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.30:t=fill,"
        f"drawtext=fontfile='{FONT}':text='Milo and the Little Light':"
        "fontcolor=white:fontsize=64:borderw=5:bordercolor=black@0.85:"
        "x=(w-text_w)/2:y=h*0.30,"
        f"drawtext=fontfile='{FONT}':text='A story about kindness and friendship':"
        "fontcolor=0xFFE9A8:fontsize=30:borderw=3:bordercolor=black@0.85:"
        "x=(w-text_w)/2:y=h*0.46"
    )
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-vf", vf, "-frames:v", "1", str(output)],
        check=True,
    )


def main() -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    project_id = state["project_id"]
    client = httpx.Client(timeout=180)
    milo = state["characters"]["Milo the Fox"]
    lumi = state["characters"]["Lumi the Little Fox"]

    def scene_by_name(name: str) -> dict:
        return next(item for item in state["scenes"] if item["name"] == name)

    # Final story beats, adjusted to the generated visuals.
    final_scenes = {
        "Milo Hears a Sparkle": {
            "name": "Milo Hears a Sparkle",
            "description": "Milo follows a tiny sparkle through the dusk forest.",
            "action": "Milo the fox walks through the dusk forest and notices tiny golden sparkles between the trees.",
        },
        "A Tiny Glow": {
            "name": "A New Friend",
            "description": "Milo meets a little lost fox named Lumi.",
            "action": "Milo and Lumi meet in a leafy clearing. Lumi looks worried; Milo smiles warmly.",
        },
        "The Rescue": {
            "name": "Helping a Friend",
            "description": "Milo promises to help Lumi find her way home.",
            "action": "Milo and Lumi talk among the leaves; Milo points the way home.",
        },
        "Friends in the Light": {
            "name": "Friends in the Light",
            "description": "Milo and Lumi walk home together under the fireflies.",
            "action": "Lumi walks beside Milo as they head home under a moonlit sky full of fireflies.",
        },
    }
    for original, final in final_scenes.items():
        scene = scene_by_name(original)
        client.patch(
            f"{BASE}/api/scenes/{scene['id']}",
            json={"name": final["name"], "description": final["description"], "action": final["action"]},
        )
        scene["name"] = final["name"]
        scene["description"] = final["description"]
        scene["action"] = final["action"]
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")

    scene1 = scene_by_name("Milo Hears a Sparkle")
    scene2 = scene_by_name("A New Friend")
    scene3 = scene_by_name("Helping a Friend")
    scene4 = scene_by_name("Friends in the Light")

    # Dialogue.
    line_specs = [
        (scene1, None, "In the heart of the forest, Milo the fox followed a tiny sparkle.", "calm", 300),
        (scene2, milo["id"], "Hello! Who are you?", "surprised", 300),
        (scene2, lumi["id"], "I'm Lumi. I'm lost.", "sad", 2000),
        (scene3, milo["id"], "Don't worry. I'll help you find your way.", "calm", 300),
        (scene3, None, "Milo knew every path in the forest.", "calm", 3000),
        (scene4, lumi["id"], "Thank you, Milo! Let's go home together!", "happy", 300),
        (scene4, None, "Even the smallest friend can light up your day.", "calm", 3000),
    ]
    dialogue_items = []
    for scene, character_id, text, emotion, start_ms in line_specs:
        line = client.post(
            f"{BASE}/api/scenes/{scene['id']}/dialogue",
            json={"character_id": character_id, "text": text, "emotion": emotion, "start_ms": start_ms},
        ).json()
        generated = client.post(f"{BASE}/api/dialogue/{line['id']}/generate", timeout=180).json()
        print(
            f"DIALOGUE {scene['name']} {generated.get('character_name') or 'Narrator'}: "
            f"{generated['duration_ms']}ms {generated['audio_asset_id']}",
            flush=True,
        )
        dialogue_items.append(
            {
                "scene_name": scene["name"],
                "scene_id": scene["id"],
                "asset_id": generated["audio_asset_id"],
                "start_ms": start_ms,
                "duration_ms": generated["duration_ms"],
                "text": text,
                "character_name": generated.get("character_name") or "Narrator",
                "kind": "dialogue",
            }
        )

    # Music and SFX.
    config = load_config()
    temp_dir = Path(tempfile.mkdtemp(prefix="little_light_audio_"))
    music_path = temp_dir / "little_light_music.wav"
    sparkle_path = temp_dir / "little_light_sparkle.wav"
    synth_music(music_path, 30.0)
    synth_sparkle(sparkle_path)
    music_asset = store_asset_from_path(
        project_id=project_id,
        subdir="audio",
        filename="little_light_music.wav",
        source_path=music_path,
        kind="audio",
        mime="audio/wav",
        meta={"kind": "music", "duration_ms": 30000, "source": "original synthesis"},
    )
    sparkle_asset = store_asset_from_path(
        project_id=project_id,
        subdir="audio",
        filename="little_light_sparkle.wav",
        source_path=sparkle_path,
        kind="audio",
        mime="audio/wav",
        meta={"kind": "sfx", "duration_ms": 1200, "source": "original synthesis"},
    )
    print("MUSIC", music_asset["id"], "SPARKLE", sparkle_asset["id"], flush=True)

    # Upscale each scene keyframe 4x.
    for scene in (scene1, scene2, scene3, scene4):
        print("UPSCALE", scene["name"], scene["keyframe_asset_id"], flush=True)
        response = client.post(
            f"{BASE}/api/assets/{scene['keyframe_asset_id']}/upscale",
            json={"owner_type": "scene", "owner_id": scene["id"], "role": "keyframe", "label": "production-upscale"},
        ).json()
        finished = wait_job(client, response["job"]["id"], f"upscale {scene['name']}")
        asset = finished["outputs"][0]
        scene["upscaled_asset_id"] = asset["asset_id"]
        print(f"  UPSCALED {asset['asset_id']} {asset['filename']}", flush=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # Title card from the upscaled scene 1 image.
    resolved = asset_file(scene1["upscaled_asset_id"])
    if not resolved:
        raise RuntimeError("Scene 1 upscaled image is missing.")
    title_png = temp_dir / "little_light_title.png"
    make_title_card(resolved[0], title_png)
    title_asset = store_asset_from_path(
        project_id=project_id,
        subdir="story",
        filename="little_light_title.png",
        source_path=title_png,
        kind="image",
        mime="image/png",
        meta={"kind": "image", "width": 1280, "height": 720, "title_card": True},
    )
    title_scene = client.post(
        f"{BASE}/api/scenes",
        json={
            "project_id": project_id,
            "name": "Title Card",
            "description": "Opening title card",
            "duration": 2.5,
            "settings": {},
        },
    ).json()
    client.post(
        f"{BASE}/api/scenes/{title_scene['id']}/media",
        json={"asset_id": title_asset["id"], "role": "keyframe", "label": "title"},
    )
    print("TITLE", title_asset["id"], title_scene["id"], flush=True)

    # Episode timeline.
    episode = client.post(
        f"{BASE}/api/episodes",
        json={
            "project_id": project_id,
            "name": "Milo and the Little Light — 30s",
            "description": "A 30-second children's story about kindness and friendship.",
        },
    ).json()
    starts = {
        "Title Card": 0,
        "Milo Hears a Sparkle": 2500,
        "A New Friend": 9375,
        "Helping a Friend": 16250,
        "Friends in the Light": 23125,
    }
    segments = [
        {"scene_id": title_scene["id"], "asset_id": title_asset["id"], "kind": "image", "duration_ms": 2500,
         "transition": "fade", "motion": "zoom_in", "label": "Title card"},
        {"scene_id": scene1["id"], "asset_id": scene1["upscaled_asset_id"], "kind": "image", "duration_ms": 6875,
         "transition": "fade", "motion": "zoom_in", "label": "Milo Hears a Sparkle"},
        {"scene_id": scene2["id"], "asset_id": scene2["upscaled_asset_id"], "kind": "image", "duration_ms": 6875,
         "transition": "fade", "motion": "pan_right", "label": "A New Friend"},
        {"scene_id": scene3["id"], "asset_id": scene3["upscaled_asset_id"], "kind": "image", "duration_ms": 6875,
         "transition": "fade", "motion": "zoom_out", "label": "Helping a Friend"},
        {"scene_id": scene4["id"], "asset_id": scene4["upscaled_asset_id"], "kind": "image", "duration_ms": 6875,
         "transition": "fade", "motion": "pan_left", "label": "Friends in the Light"},
    ]
    audio_items = []
    for item in dialogue_items:
        audio_items.append(
            {
                "id": f"aud_{len(audio_items)}",
                "asset_id": item["asset_id"],
                "start_ms": starts[item["scene_name"]] + item["start_ms"],
                "volume": 1.0,
                "loop": False,
                "label": f"{item['character_name']} · {item['text'][:44]}",
                "kind": "dialogue",
            }
        )
    for index, start in enumerate((2500, 16250, 23125)):
        audio_items.append(
            {
                "id": f"sfx_{index}",
                "asset_id": sparkle_asset["id"],
                "start_ms": start,
                "volume": 0.55,
                "loop": False,
                "label": "Sparkle chime",
                "kind": "sfx",
            }
        )
    timeline = {
        "segments": segments,
        "audio": audio_items,
        "settings": {
            "width": 1280,
            "height": 720,
            "fps": 24,
            "subtitles": "soft",
            "background_music_asset_id": music_asset["id"],
            "background_music_volume": 0.22,
            "fade_duration_ms": 400,
        },
    }
    saved = client.put(f"{BASE}/api/episodes/{episode['id']}/timeline", json=timeline, timeout=120)
    print("TIMELINE", saved.status_code, flush=True)
    if saved.status_code >= 400:
        print(saved.text, flush=True)
        raise SystemExit(1)
    client.post(f"{BASE}/api/episodes/{episode['id']}/export", json={}, timeout=120)
    start = time.perf_counter()
    while True:
        time.sleep(1.0)
        current = client.get(f"{BASE}/api/episodes/{episode['id']}", timeout=60).json()
        if current["status"] in ("completed", "failed", "cancelled", "interrupted"):
            print(
                f"EXPORT {current['status']} {time.perf_counter() - start:.2f}s "
                f"{current.get('output_url')}",
                flush=True,
            )
            print("ERROR", (current.get("error") or "")[:2000], flush=True)
            print("LOG", (current.get("log") or "")[-3000:], flush=True)
            break
    state["final_episode_id"] = episode["id"]
    state["final_output_url"] = current.get("output_url")
    state["final_output_path"] = current.get("output_path")
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("EPISODE", episode["id"], flush=True)


if __name__ == "__main__":
    main()
