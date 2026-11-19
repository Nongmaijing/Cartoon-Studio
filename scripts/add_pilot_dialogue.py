"""Add missing pilot dialogue lines to existing scenes (idempotent).

Usage:
    python scripts/add_pilot_dialogue.py --project-id ... --episode-id ... --dry-run
    python scripts/add_pilot_dialogue.py --project-id ... --episode-id ...
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.db import query, query_one  # noqa: E402
from app.services import dialogue_service  # noqa: E402


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
    scene_rows = {row["name"].strip().lower(): row for row in query("SELECT id, name FROM scenes WHERE project_id = ?", (args.project_id,))}
    characters = {
        row["name"].strip().lower(): row
        for row in query("SELECT id, name FROM characters WHERE project_id = ?", (args.project_id,))
    }

    plan = []
    for item in scenes:
        title = str(item.get("title") or "").strip()
        scene = scene_rows.get(title.lower())
        if not scene:
            plan.append({"title": title, "status": "scene_missing"})
            continue
        existing = query_one("SELECT COUNT(*) c FROM dialogue_lines WHERE scene_id = ?", (scene["id"],))["c"]
        if existing:
            plan.append({"title": title, "scene_id": scene["id"], "status": "already_has_dialogue", "lines": existing})
            continue
        plan.append({"title": title, "scene_id": scene["id"], "status": "would_add", "lines": len(item.get("dialogue") or [])})

    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return

    added = []
    for item in scenes:
        title = str(item.get("title") or "").strip()
        scene = scene_rows.get(title.lower())
        if not scene:
            continue
        existing = query_one("SELECT COUNT(*) c FROM dialogue_lines WHERE scene_id = ?", (scene["id"],))["c"]
        if existing:
            continue
        count = 0
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
            count += 1
        added.append({"scene_id": scene["id"], "title": title, "lines": count})
    print(json.dumps({"added": added}, indent=2))


if __name__ == "__main__":
    main()
