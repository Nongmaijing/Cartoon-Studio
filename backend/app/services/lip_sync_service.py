from __future__ import annotations

import json
import re
from typing import Any

from ..db import execute, now, query_one
from . import dialogue_service
from .audit_service import log
from .errors import NotFoundError, ServiceError

# Coarse viseme groups for 2D mouth-shape animation. This is an editable cue
# layer, not a photoreal lip-sync model. Actual mouth rendering is a separate
# video/model step.
DIGRAPHS = {
    "TH": "TH",
    "SH": "SH",
    "CH": "SH",
    "PH": "FV",
    "WH": "WQ",
    "NG": "NG",
    "OO": "U",
    "EE": "I",
    "EA": "I",
    "AI": "A",
    "AY": "A",
    "OW": "O",
    "OU": "WQ",
    "OI": "O",
    "AR": "A",
    "ER": "E",
    "OR": "O",
}

CHAR_VISEMES = {
    "A": "A",
    "B": "MBP",
    "C": "SH",
    "D": "L",
    "E": "E",
    "F": "FV",
    "G": "L",
    "H": "A",
    "I": "I",
    "J": "SH",
    "K": "L",
    "L": "L",
    "M": "MBP",
    "N": "L",
    "O": "O",
    "P": "MBP",
    "Q": "WQ",
    "R": "E",
    "S": "SH",
    "T": "L",
    "U": "U",
    "V": "FV",
    "W": "WQ",
    "X": "SH",
    "Y": "I",
    "Z": "SH",
    " ": "REST",
}


def text_to_units(text: str) -> list[tuple[str, str]]:
    cleaned = re.sub(r"[^A-Za-z ]+", " ", text or "").upper()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    units: list[tuple[str, str]] = []
    index = 0
    while index < len(cleaned):
        pair = cleaned[index : index + 2]
        if pair in DIGRAPHS:
            units.append((pair, DIGRAPHS[pair]))
            index += 2
            continue
        char = cleaned[index]
        units.append((char, CHAR_VISEMES.get(char, "REST")))
        index += 1
    return units or [(" ", "REST")]


def text_to_cues(text: str, duration_ms: int = 0) -> list[dict[str, Any]]:
    units = text_to_units(text)
    total = int(duration_ms) if duration_ms and duration_ms > 0 else max(400, len(units) * 95)
    step = max(40, int(total / max(1, len(units))))
    cues = []
    cursor = 0
    for index, (unit, viseme) in enumerate(units):
        end = total if index == len(units) - 1 else min(total, cursor + step)
        cues.append(
            {
                "index": index,
                "start_ms": cursor,
                "end_ms": end,
                "viseme": viseme,
                "text": unit,
            }
        )
        cursor = end
    return cues


def _package(cues: list[dict[str, Any]], source: str = "heuristic") -> dict[str, Any]:
    return {
        "version": 1,
        "source": source,
        "editable": True,
        "note": "Viseme cue layer only. Mouth-shape rendering requires a lip-sync renderer or rig animation.",
        "cues": cues,
    }


def _read(line_id: str) -> dict[str, Any]:
    line = dialogue_service.get_line(line_id)
    try:
        payload = json.loads(line.get("lip_sync_json") or "{}")
    except json.JSONDecodeError:
        payload = {}
    return {"line": line, "payload": payload if isinstance(payload, dict) else {}}


def generate_for_line(line_id: str, actor: str = "user") -> dict[str, Any]:
    line = dialogue_service.get_line(line_id)
    duration = int(line.get("duration_ms") or 0)
    if not duration:
        duration = max(400, len(str(line.get("text") or "")) * 95)
    payload = _package(text_to_cues(str(line.get("text") or ""), duration))
    execute(
        "UPDATE dialogue_lines SET lip_sync_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(payload), now(), line_id),
    )
    log(actor, "generate_lip_sync", "dialogue", line_id, {"cues": len(payload["cues"])})
    return {"line_id": line_id, **payload}


def generate_for_scene(scene_id: str, actor: str = "user") -> dict[str, Any]:
    lines = dialogue_service.list_lines(scene_id)
    generated = []
    for line in lines:
        generated.append(generate_for_line(line["id"], actor=actor))
    return {"scene_id": scene_id, "lines": generated, "count": len(generated)}


def get_for_line(line_id: str) -> dict[str, Any]:
    data = _read(line_id)
    return {"line_id": line_id, **(data["payload"] or {"cues": []})}


def update_cues(line_id: str, cues: list[dict[str, Any]], actor: str = "user") -> dict[str, Any]:
    dialogue_service.get_line(line_id)
    if not isinstance(cues, list):
        raise ServiceError("cues must be an array.")
    normalized = []
    for index, cue in enumerate(cues):
        if not isinstance(cue, dict):
            raise ServiceError("Each cue must be an object.")
        start = int(cue.get("start_ms") or 0)
        end = int(cue.get("end_ms") or start + 80)
        if end <= start:
            raise ServiceError("Each cue must have end_ms greater than start_ms.")
        normalized.append(
            {
                "index": index,
                "start_ms": start,
                "end_ms": end,
                "viseme": str(cue.get("viseme") or "REST"),
                "text": str(cue.get("text") or ""),
            }
        )
    payload = _package(normalized, source="manual")
    execute(
        "UPDATE dialogue_lines SET lip_sync_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(payload), now(), line_id),
    )
    log(actor, "update_lip_sync", "dialogue", line_id, {"cues": len(normalized)})
    return {"line_id": line_id, **payload}
