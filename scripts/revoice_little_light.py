from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8010"
STATE_PATH = Path(r"D:\bro\CartoonStudio\projects\little_light_state.json")


def wait_episode(client: httpx.Client, episode_id: str, timeout: float = 900) -> dict:
    start = time.perf_counter()
    last = None
    while time.perf_counter() - start < timeout:
        time.sleep(1.0)
        episode = client.get(f"{BASE}/api/episodes/{episode_id}", timeout=60).json()
        if episode["status"] != last:
            print(f"  [export] {episode['status']} {episode['progress']:.0f}%", flush=True)
            last = episode["status"]
        if episode["status"] in ("completed", "failed", "cancelled", "interrupted"):
            return episode
    raise TimeoutError("episode export timed out")


def main() -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    client = httpx.Client(timeout=240)
    project_id = state["project_id"]
    milo = state["characters"]["Milo the Fox"]
    lumi = state["characters"]["Lumi the Little Fox"]

    client.patch(
        f"{BASE}/api/characters/{milo['id']}/voice",
        json={"engine": "kokoro", "voice": "am_michael", "rate": 0, "pitch": 0, "volume": 100},
    )
    client.patch(
        f"{BASE}/api/characters/{lumi['id']}/voice",
        json={"engine": "kokoro", "voice": "af_bella", "rate": 2, "pitch": 0, "volume": 95},
    )

    voice_map = {}
    for scene in state["scenes"]:
        print("SCENE", scene["name"], flush=True)
        lines = client.get(f"{BASE}/api/scenes/{scene['id']}/dialogue", timeout=60).json()
        for line in lines:
            speaker = line.get("character_name") or "Narrator"
            if speaker == "Milo the Fox":
                engine, voice, rate, volume = "kokoro", "am_michael", 0, 100
            elif speaker == "Lumi the Little Fox":
                engine, voice, rate, volume = "kokoro", "af_bella", 2, 95
            else:
                engine, voice, rate, volume = "kokoro", "af_heart", -1, 100
            old_asset = line.get("audio_asset_id")
            client.patch(
                f"{BASE}/api/dialogue/{line['id']}",
                json={
                    "voice_engine": engine,
                    "voice_name": voice,
                    "rate": rate,
                    "pitch": 0,
                    "volume": volume,
                },
            )
            generated = client.post(f"{BASE}/api/dialogue/{line['id']}/generate", timeout=240).json()
            new_asset = generated.get("audio_asset_id")
            if old_asset and new_asset:
                voice_map[old_asset] = new_asset
            print(
                f"  {speaker}: {generated.get('duration_ms')}ms {old_asset} -> {new_asset}",
                flush=True,
            )

    episode_id = state["final_episode_id"]
    episode = client.get(f"{BASE}/api/episodes/{episode_id}", timeout=60).json()
    timeline = episode["timeline"]
    replaced = 0
    for item in timeline.get("audio") or []:
        new_asset = voice_map.get(item.get("asset_id"))
        if new_asset:
            item["asset_id"] = new_asset
            replaced += 1
    print("TIMELINE AUDIO REPLACED", replaced, "of", len(voice_map), flush=True)
    saved = client.put(f"{BASE}/api/episodes/{episode_id}/timeline", json=timeline, timeout=120)
    print("TIMELINE SAVE", saved.status_code, flush=True)
    if saved.status_code >= 400:
        print(saved.text, flush=True)
        raise SystemExit(1)
    client.post(f"{BASE}/api/episodes/{episode_id}/export", json={}, timeout=120)
    final = wait_episode(client, episode_id)
    print(
        f"EXPORT {final['status']} {final.get('output_url')} duration={final.get('duration_ms')}ms",
        flush=True,
    )
    print("ERROR", (final.get("error") or "")[:1500], flush=True)
    print("LOG", (final.get("log") or "")[-2500:], flush=True)
    state["voiceover"] = "kokoro"
    state["final_output_url"] = final.get("output_url")
    state["final_output_path"] = final.get("output_path")
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
