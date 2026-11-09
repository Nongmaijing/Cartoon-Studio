from __future__ import annotations

from typing import Any

CARTOON_STYLE = (
    "production-quality western 2D television cartoon style, clean bold outlines, flat colors, "
    "appealing shapes, expressive character design, consistent proportions"
)

NEGATIVE_DEFAULT = (
    "photo, photorealistic, 3d render, blurry, low quality, deformed, extra limbs, "
    "extra fingers, extra tails, duplicate body parts, floating limbs, malformed paws, "
    "bad anatomy, watermark, text, signature, artist signature, logo, initials, monogram, "
    "cropped, jpeg artifacts"
)

BACKGROUND_NEGATIVE = (
    "characters, people, person, animals, text, watermark, signature, photo, photorealistic, "
    "3d render, blurry, low quality, deformed"
)

VIDEO_NEGATIVE = (
    "blurry, low quality, watermark, text, extra limbs, extra tails, duplicate body parts, "
    "deformed, flicker, morphing, inconsistent character, jitter, duplicate frames"
)


def _clean(value: str | None) -> str:
    return (value or "").strip()


def character_prompt(character: dict[str, Any], kind: str, label: str, extra: str | None = None) -> str:
    """Compose a repeatable prompt from the saved character identity fields."""
    parts: list[str] = [_clean(character.get("name"))]
    description = _clean(character.get("description"))
    appearance = _clean(character.get("appearance"))
    clothing = _clean(character.get("clothing"))
    style = _clean(character.get("style"))

    if description:
        parts.append(description)
    if appearance:
        parts.append(f"appearance: {appearance}")
    if clothing:
        parts.append(f"wearing {clothing}")
    if style:
        parts.append(style)
    parts.append(CARTOON_STYLE)

    label = _clean(label)
    if kind == "expression":
        parts.append(
            f"single head and shoulders portrait showing {label or 'a neutral expression'}, "
            "one expression only, plain light background, no multiple views"
        )
    elif kind == "pose":
        parts.append(
            f"single full body character in a {label or 'standing naturally'} pose, "
            "one character only, plain light background, clear silhouette, no multiple views"
        )
    else:
        view = label or "front"
        parts.append(
            f"single full body cartoon animal character, {view} view, neutral A-pose, "
            "plain light background, one character only, production keyframe"
        )

    if extra:
        parts.append(extra.strip())
    return ", ".join(part for part in parts if part)


def background_prompt(background: dict[str, Any], extra: str | None = None) -> str:
    parts: list[str] = [_clean(background.get("name"))]
    description = _clean(background.get("description"))
    if description:
        parts.append(description)
    parts.append(CARTOON_STYLE)
    parts.append("environment background art, establishing shot, no characters, no people, no text")
    if extra:
        parts.append(extra.strip())
    return ", ".join(part for part in parts if part)


def scene_prompt(
    scene: dict[str, Any],
    background: dict[str, Any] | None,
    characters: list[dict[str, Any]],
    kind: str,
    extra: str | None = None,
) -> str:
    """Compose a shot prompt from the scene, its location and its cast."""
    parts: list[str] = []
    for value in (
        scene.get("name"),
        scene.get("description"),
        scene.get("action"),
        scene.get("camera"),
    ):
        cleaned = _clean(value)
        if cleaned:
            parts.append(cleaned)

    if background:
        location = _clean(background.get("name"))
        description = _clean(background.get("description"))
        parts.append(f"setting: {location}" + (f", {description}" if description else ""))

    for character in characters:
        bits: list[str] = [_clean(character.get("name"))]
        appearance = _clean(character.get("appearance"))
        clothing = _clean(character.get("clothing"))
        style = _clean(character.get("style"))
        if appearance:
            bits.append(appearance)
        if clothing:
            bits.append(f"wearing {clothing}")
        if style:
            bits.append(style)
        parts.append(", ".join(bit for bit in bits if bit))

    parts.append(CARTOON_STYLE)
    if kind == "video":
        parts.append(
            "animated cartoon shot, natural character motion, consistent character design, "
            "smooth camera movement, clear readable action"
        )
    else:
        parts.append(
            "single animation keyframe, cinematic composition, expressive pose, "
            "clear silhouette, no text"
        )
    if extra:
        parts.append(extra.strip())
    return ", ".join(part for part in parts if part)
