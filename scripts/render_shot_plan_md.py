"""Render S01E01_SHOT_PLAN_V1.md from the validated JSON plan."""
from __future__ import annotations

import json
from pathlib import Path

SRC = Path(r"D:\bro\CartoonStudio\docs\operations\S01E01_SHOT_PLAN_V1.json")
OUT = Path(r"D:\bro\CartoonStudio\docs\operations\S01E01_SHOT_PLAN_V1.md")


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    shots = data["shots"]
    by_scene: dict[int, list[dict]] = {}
    for shot in shots:
        by_scene.setdefault(shot["scene"], []).append(shot)

    total = sum(int(shot["duration_seconds"]) for shot in shots)
    lines = [
        "# S01E01 - The Little Seed - 16-Shot Production Plan V1",
        "",
        f"- Plan version: `{data['version']}`",
        f"- Script revision: `{data['script_revision']}`",
        f"- Script source: `{data['script_path']}`",
        f"- Total runtime: **{total} seconds** (6:50), plus 10 seconds of titles/transitions to 7:00",
        "- All character designs remain **draft**. Leo, Mira, Toby and Bruno have draft canonical refs; Pip and Ollie do not.",
        "- No keyframes, audio or video have been generated from this plan.",
        "",
        "## Gate status",
        "",
        "| Item | State |",
        "|---|---|",
        "| Character designs | Draft; Leo/Mira/Toby/Bruno canonical draft refs; Pip/Ollie blocked |",
        "| Locations | 6 draft backgrounds; Old Oak v2 and Garden Patch v2 used here |",
        "| Script | v3 draft validated at 6.89 min; episode record still holds v1 |",
        "| Shot plan | 16 shots / 410s validated |",
        "| Keyframes/audio/video | Not generated |",
        "",
        "## Summary",
        "",
        "| Shot | Scene | Sec | Framing | Background | On-screen cast | Draft dependency | Status |",
        "|---|---:|---:|---|---|---|---|---|",
    ]
    for shot in shots:
        cast = ", ".join(shot["characters_on_screen"])
        lines.append(
            f"| {shot['number']} | {shot['scene']} | {shot['duration_seconds']} | "
            f"{shot['framing']} | {shot['background_name']} | {cast} | "
            f"{shot['draft_dependency']} | {'BLOCKED' if shot['status'].startswith('blocked') else 'READY'} |"
        )

    lines += ["", "### Scene subtotals", ""]
    for scene in sorted(by_scene):
        subtotal = sum(int(shot["duration_seconds"]) for shot in by_scene[scene])
        lines.append(f"- Scene {scene}: {subtotal}s")
    lines.append(f"- Total: **{total}s**")
    lines += ["", "## Detailed shots", ""]

    for shot in shots:
        lines += [
            f"### Shot {shot['number']} — {shot['scene_title']} ({shot['duration_seconds']}s)",
            "",
            f"- **Camera / framing:** {shot['camera']} ({shot['framing']})",
            f"- **Action:** {shot['action']}",
            f"- **Staging:** {shot['staging']}",
            f"- **Background:** {shot['background_name']} (`{shot['background_id']}`)",
            f"- **On-screen cast:** {', '.join(shot['characters_on_screen'])}",
            f"- **Dialogue lines:** {shot['dialogue_range'][0]}–{shot['dialogue_range'][1]}",
            f"- **Audio:** {shot['audio']}",
            f"- **SFX:** {', '.join(shot['sfx'])}",
            f"- **Draft dependency:** {shot['draft_dependency']}",
            f"- **Status:** {'BLOCKED - Pip/Ollie design needed' if shot['status'].startswith('blocked') else 'READY with canonical drafts'}",
        ]
        if shot.get("requires_pip_only"):
            lines.append("- **Flag:** Pip-only shot")
        if shot.get("requires_ollie_only"):
            lines.append("- **Flag:** Ollie-only shot")
        lines.append("")

    ready = [shot["number"] for shot in shots if shot["status"] == "ready_with_canonical_drafts"]
    blocked = [shot["number"] for shot in shots if shot["status"] == "blocked_pending_pip_ollie"]
    lines += [
        "## Production readiness",
        "",
        f"- Ready with canonical drafts: {', '.join(f'Shot {n}' for n in ready) or 'none'}",
        f"- Blocked pending Pip/Ollie designs: {', '.join(f'Shot {n}' for n in blocked) or 'none'}",
        "- Pip-only shot: Shot 6",
        "- Ollie-only shot: Shot 9",
        "",
        "## Do not generate yet",
        "",
        "Do not generate keyframes, animation or audio until Pip and Ollie pass the character gate and the script v3 is approved. Shots 3 and 12 can be used later as early camera/composition tests with the existing canonical drafts, but they are not a request to start downstream generation.",
    ]

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("WROTE", OUT, OUT.stat().st_size)


if __name__ == "__main__":
    main()
