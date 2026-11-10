from __future__ import annotations

from typing import Any

CARTOON_STYLE = (
    "premium Western preschool 2D television animation, stylized graphic cartoon design, "
    "clean confident outlines, simplified rounded shapes, flat solid color fills, subtle cel shading, "
    "expressive readable faces, appealing silhouettes, consistent proportions"
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


def _phrase(value: str | None) -> str:
    """Trim trailing punctuation so profile fields join cleanly into a prompt."""
    return _clean(value).rstrip(" .,;:")


def _normalise_view(label: str | None) -> str:
    """Normalise UI/API view labels to one of the four canonical camera angles."""
    value = " ".join(
        _clean(label).lower().replace("/", " ").replace("_", " ").replace("-", " ").split()
    )
    if value.endswith(" view"):
        value = value[:-5].strip()
    aliases = {
        "threequarter": "three quarter",
        "3 4": "three quarter",
        "profile": "side profile",
        "side": "side profile",
        "rear": "back",
    }
    return aliases.get(value, value or "front")


def character_negative_prompt(kind: str, label: str | None = None) -> str:
    """Return a view-aware negative prompt for single-image character references."""
    if kind not in {"reference", "turnaround"}:
        return NEGATIVE_DEFAULT

    view = _normalise_view(label)
    single_view_exclusions = (
        "multiple views, multiple angles, multi-view sheet, turnaround sheet, contact sheet, "
        "character lineup, collage, split panel, diptych, triptych, duplicate character, "
        "extra character, extra head, close-up, headshot, bust portrait, waist-up, upper body only, "
        "cropped legs, cropped feet, cropped shoes, cut off feet, missing feet, missing shoes, "
        "tight portrait framing, complex background, scenery, interior, furniture, props, "
        "inconsistent anatomy, unrequested clothing changes, unrequested accessories, "
        "incorrect viewing angle, anime, manga, semi-realistic illustration"
    )
    opposing_view_exclusions = {
        "front": "back view, rear view, side profile, three-quarter view",
        "three quarter": "front view, side profile, back view, rear view",
        "side profile": "front view, three-quarter view, back view, rear view",
        "back": (
            "front view, front-facing, front-facing pose, face visible, visible face, visible eyes, "
            "visible nose, visible mouth, front-facing eyes, looking at camera, "
            "head turned toward camera"
        ),
    }
    exclusions = opposing_view_exclusions.get(view, "")
    return ", ".join(part for part in (NEGATIVE_DEFAULT, single_view_exclusions, exclusions) if part)


def character_prompt(character: dict[str, Any], kind: str, label: str, extra: str | None = None) -> str:
    """Compose a repeatable prompt from saved identity fields and a single explicit view."""
    parts: list[str] = [_clean(character.get("name"))]
    description = _phrase(character.get("description"))
    appearance = _phrase(character.get("appearance"))
    clothing = _phrase(character.get("clothing"))
    style = _phrase(character.get("style"))

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
        view = _normalise_view(label)
        view_instructions = {
            "front": (
                "front view, body facing directly toward the camera, face fully visible, "
                "both eyes visible, both arms and legs clearly visible (or forelimbs and "
                "hindlimbs where applicable), neutral A-pose"
            ),
            "three quarter": (
                "three-quarter view at approximately 45 degrees, body and face turned slightly "
                "to the character's left, both eyes visible, neutral A-pose"
            ),
            "side profile": (
                "true side profile at exactly 90 degrees, body facing screen right, "
                "only the near eye visible, neutral A-pose"
            ),
            "back": (
                "rear view, body facing directly away from the camera, back of head and back "
                "of clothing visible, face completely hidden, no facial features visible, "
                "no front-facing eyes, neutral A-pose"
            ),
        }
        camera_instruction = view_instructions.get(
            view,
            f"{view} view, body aligned to the requested camera angle, neutral A-pose",
        )
        parts.append(
            "single full-body character, full-length wide shot, standing upright, entire figure visible "
            "from the top of the head to the soles of both shoes, both feet fully visible, "
            "character centered and completely inside the frame, camera pulled back, generous clear "
            "margin around the figure, character occupies about 70 percent of canvas height, "
            f"{camera_instruction}, one isolated image, one camera angle only, "
            "not a portrait, not a headshot, not a waist-up crop, "
            "plain light seamless studio background, no environment or props, consistent character "
            "proportions and exact clothing"
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
