"""Validate the 16-shot production plan against the v3 script and live DB.

Usage:
    python scripts/validate_shot_plan.py --path docs/operations/S01E01_SHOT_PLAN_V1.json ^
      --script docs/operations/S01E01_SCRIPT_V3.json --project-id 16556b67d331
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.db import query  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--script", required=True)
    parser.add_argument("--project-id", required=True)
    args = parser.parse_args()

    plan = json.loads(Path(args.path).read_text(encoding="utf-8"))
    script = json.loads(Path(args.script).read_text(encoding="utf-8"))
    scenes = script["story"]["scenes"]
    shots = plan.get("shots") or []

    backgrounds = {
        row["id"]: row["name"]
        for row in query("SELECT id, name FROM backgrounds WHERE project_id = ?", (args.project_id,))
    }
    characters = {
        row["name"].strip().lower(): row["name"]
        for row in query("SELECT name FROM characters WHERE project_id = ?", (args.project_id,))
    }

    errors: list[str] = []
    warnings: list[str] = []

    if len(shots) != 16:
        errors.append(f"Expected 16 shots, found {len(shots)}")
    if [shot.get("number") for shot in shots] != list(range(1, 17)):
        errors.append("Shot numbers must be 1..16 in order")

    total_duration = sum(int(shot.get("duration_seconds") or 0) for shot in shots)
    if total_duration != 410:
        errors.append(f"Total duration must be 410s, found {total_duration}s")

    by_scene: dict[int, list[dict]] = defaultdict(list)
    for shot in shots:
        by_scene[int(shot.get("scene") or 0)].append(shot)

    for scene_index, scene in enumerate(scenes, start=1):
        scene_shots = by_scene.get(scene_index) or []
        if len(scene_shots) != 4:
            errors.append(f"Scene {scene_index}: expected 4 shots, found {len(scene_shots)}")
        expected = int(scene.get("duration_seconds") or 0)
        actual = sum(int(shot.get("duration_seconds") or 0) for shot in scene_shots)
        if actual != expected:
            errors.append(f"Scene {scene_index}: shot durations total {actual}s, expected {expected}s")

        ranges = sorted(
            (int(shot["dialogue_range"][0]), int(shot["dialogue_range"][1]))
            for shot in scene_shots
            if shot.get("dialogue_range")
        )
        line_count = len(scene.get("dialogue") or [])
        cursor = 1
        for start, end in ranges:
            if start != cursor:
                errors.append(f"Scene {scene_index}: dialogue ranges not contiguous at line {cursor}")
            if end < start:
                errors.append(f"Scene {scene_index}: invalid dialogue range {start}-{end}")
            cursor = end + 1
        if cursor != line_count + 1:
            errors.append(f"Scene {scene_index}: dialogue ranges cover {cursor - 1} of {line_count} lines")

    for shot in shots:
        number = shot.get("number")
        for field in (
            "scene",
            "scene_title",
            "duration_seconds",
            "camera",
            "framing",
            "action",
            "staging",
            "background_id",
            "characters_on_screen",
            "dialogue_range",
            "audio",
            "sfx",
            "draft_dependency",
            "status",
        ):
            if not shot.get(field):
                errors.append(f"Shot {number}: missing {field}")
        background_id = str(shot.get("background_id") or "")
        if background_id and background_id not in backgrounds:
            errors.append(f"Shot {number}: unknown background id {background_id}")
        for name in shot.get("characters_on_screen") or []:
            if str(name).strip().lower() not in characters:
                errors.append(f"Shot {number}: unknown character {name}")
        on_screen = {str(name).strip().lower() for name in shot.get("characters_on_screen") or []}
        if shot.get("requires_pip_only") and on_screen != {"pip"}:
            errors.append(f"Shot {number}: requires_pip_only but on-screen cast is {sorted(on_screen)}")
        if shot.get("requires_ollie_only") and on_screen != {"ollie"}:
            errors.append(f"Shot {number}: requires_ollie_only but on-screen cast is {sorted(on_screen)}")
        blocked = "pip" in on_screen or "ollie" in on_screen
        expected_status = "blocked_pending_pip_ollie" if blocked else "ready_with_canonical_drafts"
        if shot.get("status") != expected_status:
            errors.append(f"Shot {number}: status {shot.get('status')} should be {expected_status}")

    if not any(shot.get("requires_pip_only") for shot in shots):
        warnings.append("No Pip-only shot is flagged")
    if not any(shot.get("requires_ollie_only") for shot in shots):
        warnings.append("No Ollie-only shot is flagged")

    ready = sum(1 for shot in shots if shot.get("status") == "ready_with_canonical_drafts")
    blocked = sum(1 for shot in shots if shot.get("status") == "blocked_pending_pip_ollie")
    report = {
        "version": plan.get("version"),
        "script_revision": plan.get("script_revision"),
        "shots": len(shots),
        "total_duration_seconds": total_duration,
        "scene_subtotals": {
            f"scene_{index}": sum(int(shot.get("duration_seconds") or 0) for shot in by_scene.get(index, []))
            for index in range(1, len(scenes) + 1)
        },
        "ready_shots": ready,
        "blocked_shots": blocked,
        "pip_only_shots": [shot["number"] for shot in shots if shot.get("requires_pip_only")],
        "ollie_only_shots": [shot["number"] for shot in shots if shot.get("requires_ollie_only")],
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }
    print(json.dumps(report, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
