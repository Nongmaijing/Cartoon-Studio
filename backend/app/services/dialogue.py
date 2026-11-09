from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any

from ..config import load_config
from ..db import execute, now, query, query_one
from ..logging_setup import logger
from . import tts
from .assets import store_asset_from_path
from .media import cover_asset_id, link_asset


def _scene(scene_id: str) -> dict[str, Any]:
    row = query_one("SELECT * FROM scenes WHERE id = ?", (scene_id,))
    if not row:
        raise ValueError("Scene not found.")
    return row


def _character(character_id: str | None, project_id: str | None) -> dict[str, Any] | None:
    if not character_id:
        return None
    row = query_one("SELECT * FROM characters WHERE id = ?", (character_id,))
    if not row:
        raise ValueError("Character not found.")
    if row.get("project_id") and project_id and row["project_id"] != project_id:
        raise ValueError("Character belongs to a different project.")
    return row


def _decorate(row: dict[str, Any]) -> dict[str, Any]:
    row["audio_url"] = f"/api/assets/{row['audio_asset_id']}/file" if row.get("audio_asset_id") else None
    row["duration_seconds"] = round(int(row.get("duration_ms") or 0) / 1000, 3)
    character_id = row.get("character_id")
    row["character_cover_url"] = (
        f"/api/assets/{cover}/file"
        if character_id and (cover := cover_asset_id("character", character_id))
        else None
    )
    row["voice_label"] = " / ".join(part for part in (row.get("voice_engine"), row.get("voice_name")) if part)
    return row


def list_lines(scene_id: str) -> list[dict[str, Any]]:
    rows = query(
        """SELECT d.*, c.name AS character_name
           FROM dialogue_lines d
           LEFT JOIN characters c ON c.id = d.character_id
           WHERE d.scene_id = ?
           ORDER BY d.order_index ASC, d.created_at ASC""",
        (scene_id,),
    )
    return [_decorate(row) for row in rows]


def get_line(line_id: str) -> dict[str, Any] | None:
    row = query_one(
        """SELECT d.*, c.name AS character_name
           FROM dialogue_lines d
           LEFT JOIN characters c ON c.id = d.character_id
           WHERE d.id = ?""",
        (line_id,),
    )
    return _decorate(row) if row else None


def _next_order(scene_id: str) -> int:
    row = query_one(
        "SELECT COALESCE(MAX(order_index), -1) + 1 AS next FROM dialogue_lines WHERE scene_id = ?",
        (scene_id,),
    )
    return int(row["next"]) if row else 0


async def default_voice(
    character: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or load_config()
    character = character or {}
    engine = str(character.get("voice_engine") or "").strip()
    voice = str(character.get("voice_name") or "").strip()
    base = {
        "voice_engine": engine,
        "voice_name": voice,
        "rate": int(character.get("voice_rate") or 0),
        "pitch": int(character.get("voice_pitch") or 0),
        "volume": int(character.get("voice_volume") if character.get("voice_volume") is not None else 100),
    }
    try:
        engine_id, voice_id = await tts.resolve_voice(config, engine or None, voice or None)
    except tts.TTSError:
        # Dialogue can still be written when no speech engine is installed.
        return base
    return {
        **base,
        "voice_engine": engine_id,
        "voice_name": voice_id,
    }


async def create_line(
    scene_id: str,
    *,
    character_id: str | None,
    text: str,
    emotion: str = "neutral",
    voice_engine: str | None = None,
    voice_name: str | None = None,
    rate: int | None = None,
    pitch: int | None = None,
    volume: int | None = None,
    start_ms: int = 0,
) -> dict[str, Any]:
    scene = _scene(scene_id)
    project_id = scene.get("project_id")
    character = _character(character_id, project_id)
    resolved = await default_voice(character)
    line_id = uuid.uuid4().hex[:12]
    timestamp = now()
    execute(
        """INSERT INTO dialogue_lines
           (id, project_id, scene_id, character_id, order_index, text, emotion,
            voice_engine, voice_name, rate, pitch, volume, start_ms, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            line_id,
            project_id,
            scene_id,
            character_id,
            _next_order(scene_id),
            text.strip(),
            emotion.strip() or "neutral",
            voice_engine if voice_engine is not None else resolved["voice_engine"],
            voice_name if voice_name is not None else resolved["voice_name"],
            rate if rate is not None else resolved["rate"],
            pitch if pitch is not None else resolved["pitch"],
            volume if volume is not None else resolved["volume"],
            start_ms,
            timestamp,
            timestamp,
        ),
    )
    execute("UPDATE scenes SET updated_at = ? WHERE id = ?", (now(), scene_id))
    return get_line(line_id) or {}


def update_line(line_id: str, payload: Any) -> dict[str, Any]:
    line = get_line(line_id)
    if not line:
        raise ValueError("Dialogue line not found.")
    fields = payload.model_fields_set
    updates: list[str] = []
    params: list[Any] = []

    if "character_id" in fields:
        character = _character(payload.character_id, line.get("project_id"))
        updates.append("character_id = ?")
        params.append(character["id"] if character else None)

    for field in ("text", "emotion", "voice_engine", "voice_name", "rate", "pitch", "volume", "start_ms", "order_index"):
        if field not in fields:
            continue
        value = getattr(payload, field)
        if field == "text" and value is not None:
            value = value.strip()
        if field == "emotion" and value is not None:
            value = value.strip() or "neutral"
        updates.append(f"{field} = ?")
        params.append(value)

    if updates:
        updates.append("updated_at = ?")
        params.extend([now(), line_id])
        execute(f"UPDATE dialogue_lines SET {', '.join(updates)} WHERE id = ?", params)
        execute("UPDATE scenes SET updated_at = ? WHERE id = ?", (now(), line["scene_id"]))
    return get_line(line_id) or {}


def delete_line(line_id: str) -> None:
    line = get_line(line_id)
    if not line:
        raise ValueError("Dialogue line not found.")
    execute("DELETE FROM dialogue_lines WHERE id = ?", (line_id,))
    # Keep the generated audio file and asset row, but remove its scene link.
    if line.get("audio_asset_id"):
        execute(
            "DELETE FROM media_links WHERE owner_type = 'scene' AND owner_id = ? AND asset_id = ? AND role = 'dialogue'",
            (line["scene_id"], line["audio_asset_id"]),
        )
    # Close the ordering gap so the script stays sequential.
    remaining = query(
        "SELECT id FROM dialogue_lines WHERE scene_id = ? ORDER BY order_index ASC, created_at ASC",
        (line["scene_id"],),
    )
    for index, row in enumerate(remaining):
        execute("UPDATE dialogue_lines SET order_index = ? WHERE id = ?", (index, row["id"]))
    execute("UPDATE scenes SET updated_at = ? WHERE id = ?", (now(), line["scene_id"]))


async def import_scene_dialogue(scene_id: str, replace: bool = False) -> list[dict[str, Any]]:
    scene = _scene(scene_id)
    project_id = scene.get("project_id")
    script = str(scene.get("dialogue") or "").replace("\r\n", "\n").strip()
    if not script:
        raise ValueError("This scene has no dialogue text to import.")

    cast = query(
        """SELECT c.* FROM scene_cast sc JOIN characters c ON c.id = sc.character_id
           WHERE sc.scene_id = ? ORDER BY sc.created_at ASC""",
        (scene_id,),
    )
    by_name = {str(member["name"]).strip().lower(): member for member in cast}

    if replace:
        old = list_lines(scene_id)
        for line in old:
            execute("DELETE FROM dialogue_lines WHERE id = ?", (line["id"],))
        for line in old:
            if line.get("audio_asset_id"):
                execute(
                    "DELETE FROM media_links WHERE owner_type = 'scene' AND owner_id = ? AND asset_id = ? AND role = 'dialogue'",
                    (scene_id, line["audio_asset_id"]),
                )

    created: list[dict[str, Any]] = []
    config = load_config()
    fallback = await default_voice(None, config)
    for raw in script.split("\n"):
        text = raw.strip()
        if not text:
            continue
        character = None
        body = text
        if ":" in text:
            possible, remainder = text.split(":", 1)
            possible = possible.strip()
            if possible.lower() in by_name:
                character = by_name[possible.lower()]
                body = remainder.strip()
            elif possible.lower() in ("narrator", "narrator (v.o.)", "voiceover", "voice over", "v.o."):
                body = remainder.strip()
        if not body:
            continue
        voice = await default_voice(character, config) if character else fallback
        line_id = uuid.uuid4().hex[:12]
        timestamp = now()
        execute(
            """INSERT INTO dialogue_lines
               (id, project_id, scene_id, character_id, order_index, text, emotion,
                voice_engine, voice_name, rate, pitch, volume, start_ms, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'neutral', ?, ?, ?, ?, ?, 0, ?, ?)""",
            (
                line_id,
                project_id,
                scene_id,
                character["id"] if character else None,
                _next_order(scene_id),
                body,
                voice["voice_engine"],
                voice["voice_name"],
                voice["rate"],
                voice["pitch"],
                voice["volume"],
                timestamp,
                timestamp,
            ),
        )
        created.append(get_line(line_id) or {})
    execute("UPDATE scenes SET updated_at = ? WHERE id = ?", (now(), scene_id))
    logger.info("Imported %d dialogue line(s) into scene %s", len(created), scene_id)
    return created


async def generate_line(line_id: str) -> dict[str, Any]:
    line = get_line(line_id)
    if not line:
        raise ValueError("Dialogue line not found.")
    scene = _scene(line["scene_id"])
    project_id = scene.get("project_id")
    if not project_id:
        raise ValueError("Scene is not attached to a project.")
    character = _character(line.get("character_id"), project_id)
    config = load_config()

    engine = str(line.get("voice_engine") or "").strip()
    voice = str(line.get("voice_name") or "").strip()
    if not engine and character:
        engine = str(character.get("voice_engine") or "").strip()
    if not voice and character:
        voice = str(character.get("voice_name") or "").strip()

    with tempfile.TemporaryDirectory(prefix="cartoon_studio_dialogue_") as tmp:
        out_path = Path(tmp) / "line.wav"
        settings = await tts.synthesize(
            text=str(line["text"]),
            out_path=out_path,
            engine=engine or None,
            voice=voice or None,
            rate=int(line.get("rate") or 0),
            pitch=int(line.get("pitch") or 0),
            volume=int(line.get("volume") if line.get("volume") is not None else 100),
            emotion=str(line.get("emotion") or "neutral"),
            config=config,
        )
        duration_ms = tts.wav_duration_ms(out_path)
        label = (line.get("character_name") or "Narrator").strip()
        asset = store_asset_from_path(
            project_id=project_id,
            subdir="voice",
            filename=f"dialogue_{line_id}.wav",
            source_path=out_path,
            kind="audio",
            mime="audio/wav",
            meta={
                "line_id": line_id,
                "scene_id": line["scene_id"],
                "character_id": line.get("character_id"),
                "character_name": line.get("character_name"),
                "text": line["text"],
                "emotion": line.get("emotion"),
                "engine": settings["engine"],
                "voice": settings["voice"],
                "rate": settings["rate"],
                "pitch": settings["pitch"],
                "volume": settings["volume"],
                "duration_ms": duration_ms,
            },
        )
    link_asset("scene", line["scene_id"], asset["id"], role="dialogue", label=label)
    execute(
        """UPDATE dialogue_lines
           SET audio_asset_id = ?, duration_ms = ?, voice_engine = ?, voice_name = ?,
               rate = ?, pitch = ?, volume = ?, updated_at = ?
           WHERE id = ?""",
        (
            asset["id"],
            duration_ms,
            settings["engine"],
            settings["voice"],
            settings["base_rate"],
            settings["base_pitch"],
            settings["base_volume"],
            now(),
            line_id,
        ),
    )
    execute("UPDATE scenes SET updated_at = ? WHERE id = ?", (now(), line["scene_id"]))
    return get_line(line_id) or {}


async def generate_scene(scene_id: str) -> dict[str, Any]:
    lines = list_lines(scene_id)
    generated: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for line in lines:
        try:
            generated.append(await generate_line(line["id"]))
        except Exception as exc:  # noqa: BLE001 - report one line without stopping the rest
            logger.exception("Dialogue line %s failed", line["id"])
            errors.append({"line_id": line["id"], "error": str(exc)})
    return {
        "lines": list_lines(scene_id),
        "generated": len(generated),
        "errors": errors,
    }
