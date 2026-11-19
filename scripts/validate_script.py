"""Validate a pilot script JSON without mutating the episode.

Usage:
    python scripts/validate_script.py --path docs/operations/S01E01_SCRIPT_V2.json ^
      --project-id 16556b67d331 --target-minutes 7
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.db import query  # noqa: E402

FORBIDDEN = {
    "villain", "scary", "terrify", "terrified", "danger", "dangerous", "kill",
    "hate", "stupid", "idiot", "die", "dead", "blood", "weapon", "monster",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--target-minutes", type=float, default=7.0)
    args = parser.parse_args()

    data = json.loads(Path(args.path).read_text(encoding="utf-8"))
    story = data.get("story") or data
    scenes = story.get("scenes") or []
    errors: list[str] = []
    warnings: list[str] = []

    characters = {
        row["name"].strip().lower(): row["name"]
        for row in query("SELECT name FROM characters WHERE project_id = ?", (args.project_id,))
    }
    backgrounds = {
        row["name"].strip().lower(): row["name"]
        for row in query("SELECT name FROM backgrounds WHERE project_id = ?", (args.project_id,))
    }

    if len(scenes) != 4:
        errors.append(f"Expected 4 scenes, found {len(scenes)}")

    total_words = 0
    total_lines = 0
    duration_total = 0.0
    seen_cast: set[str] = set()
    speaker_stats: dict[str, dict[str, int]] = {}
    scene_word_counts: dict[str, int] = {}

    for index, scene in enumerate(scenes, start=1):
        label = f"scene {index}"
        for field in ("title", "summary", "action", "camera", "background", "duration_seconds", "characters", "dialogue"):
            if not scene.get(field):
                errors.append(f"{label}: missing {field}")
        background = str(scene.get("background") or "")
        if background and background.strip().lower() not in backgrounds:
            errors.append(f"{label}: background not found: {background}")
        duration_total += float(scene.get("duration_seconds") or 0)
        for name in scene.get("characters") or []:
            key = str(name).strip().lower()
            if key not in characters:
                errors.append(f"{label}: unknown character: {name}")
            else:
                seen_cast.add(characters[key])
        for line_index, line in enumerate(scene.get("dialogue") or [], start=1):
            text = str(line.get("text") or "").strip()
            speaker = str(line.get("speaker") or "").strip()
            if not text:
                errors.append(f"{label} line {line_index}: empty text")
                continue
            if not speaker:
                errors.append(f"{label} line {line_index}: missing speaker")
            elif speaker.lower() not in characters and speaker.lower() != "narrator":
                errors.append(f"{label} line {line_index}: unknown speaker: {speaker}")
            words = len(text.split())
            total_words += words
            total_lines += 1
            speaker_key = speaker.lower()
            speaker_stats.setdefault(speaker_key, {"lines": 0, "words": 0})
            speaker_stats[speaker_key]["lines"] += 1
            speaker_stats[speaker_key]["words"] += words
            scene_word_counts[label] = scene_word_counts.get(label, 0) + words

    missing_cast = sorted(set(characters.values()) - seen_cast)
    if missing_cast:
        errors.append("Characters never appear in a scene cast: " + ", ".join(missing_cast))

    for key, display in characters.items():
        stats = speaker_stats.get(key) or {"lines": 0, "words": 0}
        if stats["lines"] < 3 or stats["words"] < 20:
            warnings.append(
                f"{display}: limited contribution ({stats['lines']} lines, {stats['words']} words)"
            )

    if scene_word_counts:
        low = min(scene_word_counts.values())
        high = max(scene_word_counts.values())
        if low and high / low > 1.5:
            warnings.append(
                f"Scene word counts are unbalanced: {scene_word_counts} (max/min {high / low:.2f})"
            )

    words_text = " ".join(
        str(line.get("text") or "")
        for scene in scenes
        for line in scene.get("dialogue") or []
    ).lower()

    FORMAL = (
        "it is", "let us", "i will", "that is", "there is", "we are", "they are",
        "did not", "cannot",
    )
    found_formal = [phrase for phrase in FORMAL if re.search(rf"\b{re.escape(phrase)}\b", words_text)]
    if found_formal:
        warnings.append("Formal phrasing remains: " + ", ".join(found_formal))

    found_forbidden = sorted({word for word in FORBIDDEN if re.search(rf"\b{re.escape(word)}\b", words_text)})
    if found_forbidden:
        errors.append("Forbidden preschool words: " + ", ".join(found_forbidden))

    runtime_estimates = {
        str(wpm): round(total_words / wpm * 60.0 + total_lines * 1.2 + len(scenes) * 5.0, 1)
        for wpm in (90, 100, 110)
    }
    estimated_seconds = runtime_estimates["110"]
    target_seconds = args.target_minutes * 60.0
    if abs(estimated_seconds - target_seconds) > target_seconds * 0.15:
        warnings.append(
            f"Estimated runtime {estimated_seconds:.0f}s differs from target {target_seconds:.0f}s by more than 15%"
        )
    if abs(runtime_estimates["100"] - target_seconds) > target_seconds * 0.15:
        warnings.append(
            f"100 wpm runtime {runtime_estimates['100']:.0f}s differs from target {target_seconds:.0f}s by more than 15%"
        )
    if abs(duration_total - target_seconds) > target_seconds * 0.15:
        warnings.append(
            f"Scene durations total {duration_total:.0f}s differs from target {target_seconds:.0f}s by more than 15%"
        )

    report = {
        "path": str(args.path),
        "revision": data.get("revision"),
        "scenes": len(scenes),
        "dialogue_lines": total_lines,
        "dialogue_words": total_words,
        "scene_word_counts": scene_word_counts,
        "character_lines": {characters.get(key, key): value["lines"] for key, value in speaker_stats.items() if key in characters},
        "character_words": {characters.get(key, key): value["words"] for key, value in speaker_stats.items() if key in characters},
        "scene_duration_seconds": duration_total,
        "runtime_estimates_seconds": runtime_estimates,
        "estimated_runtime_seconds": round(estimated_seconds, 1),
        "estimated_runtime_minutes": round(estimated_seconds / 60.0, 2),
        "cast": sorted(seen_cast),
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }
    print(json.dumps(report, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
