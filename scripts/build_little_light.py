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
    client = httpx.Client(timeout=120)
    project = client.post(
        f"{BASE}/api/projects",
        json={
            "name": "Milo and the Little Light",
            "description": "A 30-second children's story about kindness, made for school children.",
        },
    ).json()
    project_id = project["id"]
    print("PROJECT", project_id, flush=True)

    characters = {}
    for payload in (
        {
            "name": "Milo the Fox",
            "description": "a curious young fox who loves exploring the forest",
            "style": "soft rounded shapes, warm colors, friendly expression",
            "clothing": "",
            "appearance": "orange fur, white muzzle, bushy tail, red scarf",
            "voice_engine": "sapi",
            "voice_name": "Microsoft Zira Desktop",
            "voice_rate": 0,
            "voice_pitch": 8,
            "voice_volume": 95,
        },
        {
            "name": "Lumi the Firefly",
            "description": "a tiny glowing firefly with a warm golden light and a brave little heart",
            "style": "soft glowing cartoon, cute and friendly",
            "clothing": "",
            "appearance": "small round golden body, tiny translucent wings, warm glow, tiny smiling face",
            "voice_engine": "sapi",
            "voice_name": "Microsoft Zira Desktop",
            "voice_rate": 2,
            "voice_pitch": 30,
            "voice_volume": 90,
        },
    ):
        character = client.post(
            f"{BASE}/api/characters",
            json={"project_id": project_id, **payload},
        ).json()
        characters[character["name"]] = character
        print("CHARACTER", character["id"], character["name"], flush=True)

    backgrounds = {}
    for name, description in (
        (
            "Dusk Forest Path",
            "a cozy forest path at dusk, tall friendly trees, soft purple and orange sky, glowing fireflies, warm and inviting, western 2D cartoon background, no characters",
        ),
        (
            "Mossy Clearing",
            "a mossy forest clearing with a big green leaf, soft moonlight, tiny glowing flowers, western 2D cartoon background, no characters",
        ),
        (
            "Moonlit Path Home",
            "a moonlit forest path with fireflies and warm light in the distance, cozy and safe, western 2D cartoon background, no characters",
        ),
    ):
        background = client.post(
            f"{BASE}/api/backgrounds",
            json={
                "project_id": project_id,
                "name": name,
                "description": description,
                "aspect_ratio": "16:9",
                "width": 1280,
                "height": 720,
            },
        ).json()
        backgrounds[name] = background
        print("BACKGROUND", background["id"], background["name"], flush=True)

    milo = characters["Milo the Fox"]["id"]
    lumi = characters["Lumi the Firefly"]["id"]

    scene_specs = [
        {
            "name": "Milo Hears a Sparkle",
            "description": "Milo walks through the dusk forest and hears a tiny sparkle.",
            "action": "Milo walks along the path, ears perked, looking around curiously. A tiny golden sparkle glows between the trees.",
            "camera": "wide shot, slow push in, eye level",
            "background": "Dusk Forest Path",
            "cast": [milo],
            "seed": 777,
        },
        {
            "name": "A Tiny Glow",
            "description": "Milo finds Lumi caught under a big leaf.",
            "action": "Milo kneels beside a big green leaf. Lumi the firefly is caught underneath, glowing faintly and looking worried.",
            "camera": "close-up, warm firefly light, gentle angle",
            "background": "Mossy Clearing",
            "cast": [milo, lumi],
            "seed": 778,
        },
        {
            "name": "The Rescue",
            "description": "Milo gently frees Lumi.",
            "action": "Milo gently lifts the big leaf. Lumi floats up, glowing brighter, smiling with relief.",
            "camera": "medium shot, warm golden light",
            "background": "Mossy Clearing",
            "cast": [milo, lumi],
            "seed": 779,
        },
        {
            "name": "Friends in the Light",
            "description": "Lumi lights the way home for Milo.",
            "action": "Lumi circles Milo happily as they walk home under a moonlit sky full of fireflies.",
            "camera": "wide shot, slow pull back, warm and cozy",
            "background": "Moonlit Path Home",
            "cast": [milo, lumi],
            "seed": 780,
        },
    ]

    scenes = []
    for spec in scene_specs:
        background = backgrounds[spec["background"]]
        scene = client.post(
            f"{BASE}/api/scenes",
            json={
                "project_id": project_id,
                "name": spec["name"],
                "description": spec["description"],
                "action": spec["action"],
                "camera": spec["camera"],
                "dialogue": "",
                "duration": 6.875,
                "background_id": background["id"],
                "character_ids": spec["cast"],
                "settings": {"width": 1024, "height": 576},
            },
        ).json()
        print("SCENE", scene["id"], scene["name"], flush=True)
        job = client.post(
            f"{BASE}/api/scenes/{scene['id']}/generate",
            json={
                "kind": "keyframe",
                "width": 1024,
                "height": 576,
                "steps": 28,
                "cfg": 6.5,
                "seed": spec["seed"],
                "prompt": "children's storybook animation keyframe, warm friendly lighting, cinematic composition, clean bold outlines, flat colors, no text, no watermark",
            },
        ).json()["job"]
        finished = wait_job(client, job["id"], scene["name"])
        output = finished["outputs"][0]
        scene["keyframe_asset_id"] = output["asset_id"]
        print(f"  KEYFRAME {output['asset_id']} {output['filename']}", flush=True)
        scenes.append(scene)

    state = {
        "project_id": project_id,
        "project_name": project["name"],
        "characters": characters,
        "backgrounds": backgrounds,
        "scenes": scenes,
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("STATE", STATE_PATH, flush=True)


if __name__ == "__main__":
    main()
