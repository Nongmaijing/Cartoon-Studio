"""Create draft scenes and dialogue from the existing pilot script.

Usage:
    python scripts/create_pilot_storyboard.py --project-id ... --episode-id ... --dry-run
    python scripts/create_pilot_storyboard.py --project-id ... --episode-id ...

Refuses to run when the project already has scenes, so existing work is never
duplicated or overwritten. Does not approve the script or any scene.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.db import execute, now, query, query_one  # noqa: E402
from app.services import dialogue_service, scene_service  # noqa: E402

BACKGROUND_BY_TITLE = {
    "the old oak gathering": "Old Oak Clearing v2",
    "watering wishes": "Garden Patch v2",
    "the waiting game": "Garden Patch v2",
    "a tiny miracle": "Garden Patch v2",
}
SCENE_SECONDS = 90.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    episode = query_one("SELECT * FROM episodes WHERE id = ? AND project_id = ?", (args.episode_id, args.project_id))
    if not episode:
        raise SystemExit("Episode not found in this project.")
    script = json.loads(episode.get("script_json") or "{}")
    scenes = (script.get("story") or {}).get("scenes") or script.get("scenes") or []
    if not scenes:
        raise SystemExit("No script scenes found.")

    existing = query("SELECT id, name FROM scenes WHERE project_id = ?", (args.project_id,))
    if existing:
        raise SystemExit(f"Refusing to run: project already has {len(existing)} scene(s).")

    characters = {
        row["name"].strip().lower(): row
        for row in query("SELECT id, name FROM characters WHERE project_id = ?", (args.project_id,))
    }
    backgrounds = {
        row["name"].strip().lower(): row
        for row in query("SELECT id, name FROM backgrounds WHERE project_id = ?", (args.project_id,))
    }

    plan = []
    for index, item in enumerate(scenes, start=1):
        title = str(item.get("title") or f"Scene {index}").strip()
        background_name = BACKGROUND_BY_TITLE.get(title.strip().lower())
        background = backgrounds.get(background_name.strip().lower()) if background_name else None
        cast_names = list(item.get("characters") or [])
        for line in item.get("dialogue") or []:
            speaker = str(line.get("speaker") or "").strip()
            if speaker and speaker.lower() != "narrator" and speaker not in cast_names:
                cast_names.append(speaker)
        cast_ids = [characters[name.strip().lower()]["id"] for name in cast_names if name.strip().lower() in characters]
        plan.append(
            {
                "number": index,
                "title": title,
                "background": background["name"] if background else None,
                "background_id": background["id"] if background else None,
                "character_ids": cast_ids,
                "dialogue_lines": len(item.get("dialogue") or []),
                "duration_seconds": SCENE_SECONDS,
            }
        )

    if args.dry_run:
        print(json.dumps({"project_id": args.project_id, "episode_id": args.episode_id, "plan": plan}, indent=2))
        return

    backup = Path("pilot_script_backup.json")
    backup.write_text(json.dumps(script, indent=2), encoding="utf-8")
    storyboard = []
    for item, entry in zip(scenes, plan):
        dialogue_text = "\n".join(
            f"{line.get('speaker', 'Narrator')}: {line.get('text', '')}"
            for line in (item.get("dialogue") or [])
            if line.get("text")
        )
        scene = scene_service.create_scene(
            args.project_id,
            name=entry["title"],
            description=str(item.get("summary") or ""),
            dialogue_text=dialogue_text,
            action=str(item.get("action") or ""),
            camera=str(item.get("camera") or ""),
            duration=SCENE_SECONDS,
            background_id=entry["background_id"],
            character_ids=entry["character_ids"],
            settings={},
            actor="pilot-setup",
        )
        for line_index, line in enumerate(item.get("dialogue") or []):
            text = str(line.get("text") or "").strip()
            if not text:
                continue
            speaker = str(line.get("speaker") or "Narrator").strip()
            character = characters.get(speaker.lower())
            asyncio.run(
                dialogue_service.create_line(
                    scene["id"],
                    character_id=character["id"] if character else None,
                    text=text,
                    emotion=str(line.get("emotion") or "neutral"),
                    start_ms=line_index * 2500,
                    actor="pilot-setup",
                )
            )
        storyboard.append(
            {
                "scene_id": scene["id"],
                "number": entry["number"],
                "title": entry["title"],
                "background_id": entry["background_id"],
                "character_ids": entry["character_ids"],
                "duration_seconds": SCENE_SECONDS,
            }
        )

    production = json.loads(episode.get("production_json") or "{}")
    production["storyboard"] = storyboard
    execute(
        "UPDATE episodes SET storyboard_json = ?, production_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(storyboard), json.dumps(production), now(), args.episode_id),
    )
    print(json.dumps({"created_scenes": storyboard}, indent=2))


if __name__ == "__main__":
    main()
