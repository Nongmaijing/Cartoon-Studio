"""Derive S01E01 script v3 from v2 with natural preschool dialogue fixes.

Preserves v1 and v2. Does not touch the episode record.
"""
from __future__ import annotations

import json
from pathlib import Path

SRC = Path(r"D:\bro\CartoonStudio\docs\operations\S01E01_SCRIPT_V2.json")
OUT = Path(r"D:\bro\CartoonStudio\docs\operations\S01E01_SCRIPT_V3.json")

REPLACEMENTS = [
    ("It is", "It's"),
    ("it is", "it's"),
    ("Let us", "Let's"),
    ("I will", "I'll"),
    ("I would", "I'd"),
    ("That is", "That's"),
    ("that is", "that's"),
    ("There is", "There's"),
    ("We are", "We're"),
    ("We will", "We'll"),
    ("They are", "They're"),
    ("did not", "didn't"),
    ("cannot", "can't"),
    ("shivery sound", "rustling sound"),
    ("Is it sleeping forever?", "Is it ever going to wake up?"),
    ("Imagine how big it will be one day.", "Imagine how big it'll be one day. Maybe as tall as the Old Oak!"),
    ("where it's", "where we planted it"),
]


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    data["revision"] = "S01E01-v3-draft-20261111"
    data["source"] = "v2 naturalness/continuity revision; v1 and v2 preserved."
    data["changelog"] = [
        "Replaced formal phrasing with preschool-natural contractions.",
        "Changed 'shivery sound' to 'rustling sound' for clarity and safety.",
        "Replaced the unsupported 'All' speaker with Toby, Pip and Ollie lines.",
        "Strengthened Leo's finale contribution with an imagination beat.",
    ]

    for scene in data["story"]["scenes"]:
        for line in scene["dialogue"]:
            text = line["text"]
            for old, new in REPLACEMENTS:
                text = text.replace(old, new)
            line["text"] = text

        if scene["title"] == "A Tiny Miracle":
            new_lines = []
            for line in scene["dialogue"]:
                if line["speaker"] == "All":
                    new_lines.extend(
                        [
                            {
                                "speaker": "Toby",
                                "text": "Grow, little seed, grow!",
                                "emotion": "joyful",
                            },
                            {
                                "speaker": "Pip",
                                "text": "Grow, grow, grow!",
                                "emotion": "cheerful",
                            },
                            {
                                "speaker": "Ollie",
                                "text": "Grow, little seed, grow!",
                                "emotion": "playful",
                            },
                        ]
                    )
                else:
                    new_lines.append(line)
            scene["dialogue"] = new_lines

    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("WROTE", OUT, OUT.stat().st_size)


if __name__ == "__main__":
    main()
