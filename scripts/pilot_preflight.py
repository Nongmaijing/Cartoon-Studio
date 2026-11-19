"""Read-only production preflight for the pilot.

Usage:
    python scripts/pilot_preflight.py --project-id ... --episode-id ...
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.db import query, query_one  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--episode-id", required=True)
    args = parser.parse_args()

    project = query_one("SELECT id, name FROM projects WHERE id = ?", (args.project_id,))
    episode = query_one("SELECT * FROM episodes WHERE id = ? AND project_id = ?", (args.episode_id, args.project_id))
    if not project or not episode:
        raise SystemExit("Project or episode not found.")

    production = json.loads(episode.get("production_json") or "{}")
    characters = query(
        """SELECT c.id, c.name, c.approval_status, c.canonical_asset_id,
                  (SELECT COUNT(*) FROM media_links m
                   WHERE m.owner_type='character' AND m.owner_id=c.id
                     AND m.role IN ('reference','pose')) AS reference_count
           FROM characters c WHERE c.project_id = ? ORDER BY c.name""",
        (args.project_id,),
    )
    scenes = query(
        """SELECT s.id, s.name, s.duration,
                  (SELECT COUNT(*) FROM dialogue_lines d WHERE d.scene_id=s.id) AS dialogue_lines,
                  (SELECT COUNT(*) FROM media_links m
                   WHERE m.owner_type='scene' AND m.owner_id=s.id AND m.role='keyframe') AS keyframes,
                  (SELECT COUNT(*) FROM scene_cast sc WHERE sc.scene_id=s.id) AS cast_count
           FROM scenes s WHERE s.project_id = ? ORDER BY s.name""",
        (args.project_id,),
    )
    backgrounds = query("SELECT id, name FROM backgrounds WHERE project_id = ? ORDER BY name", (args.project_id,))
    audio = query_one(
        "SELECT COUNT(*) c FROM assets WHERE project_id = ? AND kind = 'audio'", (args.project_id,)
    )["c"]
    video = query_one(
        "SELECT COUNT(*) c FROM assets WHERE project_id = ? AND kind = 'video'", (args.project_id,)
    )["c"]

    character_ready = all(
        row["approval_status"] == "approved" and row["canonical_asset_id"] for row in characters
    )
    any_canonical = any(row["canonical_asset_id"] for row in characters)
    location_ready = bool(backgrounds)
    script_ready = bool(production.get("script_approved"))
    scenes_ready = bool(scenes) and all(row["keyframes"] > 0 for row in scenes)

    report = {
        "project": project,
        "episode": {"id": episode["id"], "name": episode["name"], "status": episode["status"]},
        "script_approved": script_ready,
        "characters": characters,
        "scenes": scenes,
        "backgrounds": backgrounds,
        "counts": {
            "scenes": len(scenes),
            "backgrounds": len(backgrounds),
            "audio_assets": audio,
            "video_assets": video,
            "canonical_characters": sum(1 for row in characters if row["canonical_asset_id"]),
            "approved_characters": sum(1 for row in characters if row["approval_status"] == "approved"),
        },
        "gates": {
            "character_gate": (
                "pass" if character_ready else ("partial" if any_canonical else "blocked")
            ),
            "location_gate": "pass" if location_ready else "blocked",
            "script_gate": "pass" if script_ready else "blocked",
            "keyframe_gate": "pass" if scenes_ready else "blocked",
        },
        "note": (
            "Character gate requires every character to be approved with a canonical reference. "
            "Keyframe gate requires every scene to have at least one keyframe."
        ),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
