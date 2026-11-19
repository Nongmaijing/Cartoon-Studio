from __future__ import annotations

import re
from typing import Any

from .art_styles import style_text

CARTOON_STYLE = (
    "premium Western preschool 2D television animation, stylized graphic cartoon design, "
    "clean confident outlines, simplified rounded shapes, flat solid color fills, subtle cel shading, "
    "expressive readable faces, appealing silhouettes, consistent proportions"
)

CARTOON_STYLE_BACK = (
    "premium Western preschool 2D television animation, stylized graphic cartoon design, "
    "clean confident outlines, simplified rounded shapes, flat solid color fills, subtle cel shading, "
    "appealing silhouettes, consistent proportions"
)

REFERENCE_PREAMBLE = (
    "full body cartoon character, plain light grey studio background, no scenery"
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


# Wardrobe accessories that must not appear unless the profile explicitly asks
# for them. Profiles now state "No backpack, straps, shoulder bag...", so simple
# keyword presence is not enough: a negated mention means "exclude", not "include".
_ACCESSORY_TERMS = (
    "backpack",
    "back pack",
    "rucksack",
    "satchel",
    "shoulder bag",
    "crossbody",
    "cross-body",
    "handbag",
    "messenger bag",
    "strap",
    "harness",
    "back-mounted",
)
_NEGATORS = re.compile(
    r"\b(no|without|never|not|none|free of|omit|remove|hidden|bare)\b", re.IGNORECASE
)
_ACCESSORY_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("backpack, back pack, rucksack, satchel", ("backpack", "back pack", "rucksack", "satchel")),
    (
        "shoulder bag, crossbody bag, handbag, messenger bag",
        ("shoulder bag", "crossbody", "cross-body", "handbag", "messenger bag"),
    ),
    (
        "backpack straps, bag straps, sternum strap, dangling strap ends",
        ("strap",),
    ),
    (
        "back-mounted accessory, backpack harness, cape, wings",
        ("back-mounted", "harness", "cape", "wings"),
    ),
)


def _sentences(text: str) -> list[str]:
    return [part for part in re.split(r"(?<=[.;])\s+", _clean(text)) if part.strip()]


def _strip_negated_accessories(text: str) -> str:
    """Remove clauses that negate an accessory, e.g. "No backpack, straps, bag".

    Positive prompts must not contain those words at all: CLIP reads "No backpack"
    as a backpack and SDXL happily draws one. Negation belongs in the negative prompt.
    """
    kept_sentences: list[str] = []
    for sentence in _sentences(text):
        kept_items: list[str] = []
        negated = False
        for item in re.split(r",", sentence):
            lowered = item.lower()
            has_accessory = any(term in lowered for term in _ACCESSORY_TERMS)
            if _NEGATORS.search(lowered):
                negated = True
                if has_accessory:
                    continue
            if negated and has_accessory:
                continue
            if negated and not has_accessory:
                negated = False
            if item.strip():
                kept_items.append(item.strip())
        if kept_items:
            kept_sentences.append(", ".join(kept_items))
    return ". ".join(sentence.strip(" .;") for sentence in kept_sentences if sentence.strip())


def _affirms_accessory(text: str, terms: tuple[str, ...]) -> bool:
    """True only when an accessory is requested outside a negated clause."""
    for sentence in _sentences(text):
        negated = False
        for item in re.split(r",", sentence):
            lowered = item.lower()
            if _NEGATORS.search(lowered):
                negated = True
            if not negated and any(term in lowered for term in terms):
                return True
    return False


def _accessory_exclusions(clothing: str | None) -> list[str]:
    if clothing is None:
        return []
    return [
        phrase for phrase, terms in _ACCESSORY_GROUPS if not _affirms_accessory(clothing, terms)
    ]


def _normalise_view(label: str | None) -> str:
    """Normalise UI/API view labels to one of the four canonical camera angles.

    Labels may carry a version suffix (e.g. "front-no-backpack-20261111-v2"), so a
    recognised view keyword at the start wins over an exact match.
    """
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
    if value in aliases:
        return aliases[value]
    for prefix, view in (
        ("three quarter", "three quarter"),
        ("front", "front"),
        ("back", "back"),
        ("rear", "back"),
        ("side", "side profile"),
        ("profile", "side profile"),
    ):
        if value.startswith(prefix):
            return view
    return value or "front"


def character_negative_prompt(
    kind: str, label: str | None = None, clothing: str | None = None
) -> str:
    """Return a view-aware negative prompt for single-image character references."""
    if kind == "cutout":
        return ", ".join(
            part
            for part in (
                "animal, animals, hedgehog, pet, companion, extra character, crowd, "
                "shadow, drop shadow, cast shadow, floor shadow, contact shadow, "
                "floor, ground, ground plane, mud, sand, gradient background, "
                "sage background, olive background, grey background, muted background, "
                "studio backdrop, scenery, background scenery, "
                "multiple views, multiple angles, turnaround sheet, "
                "cropped head, cropped hair, cut off head, cropped feet, cut off feet, "
                "missing feet, close-up, portrait, headshot, "
                "text, watermark, signature",
                ", ".join(_accessory_exclusions(clothing)) if clothing else "",
                NEGATIVE_DEFAULT,
            )
            if part
        )
    if kind not in {"reference", "turnaround"}:
        return NEGATIVE_DEFAULT

    view = _normalise_view(label)
    single_view_exclusions = (
        "3d render, cgi, photorealistic, realistic skin, semi-realistic illustration, anime, manga, "
        "multiple views, multiple angles, multi-view sheet, turnaround sheet, contact sheet, "
        "character lineup, collage, split panel, diptych, triptych, duplicate character, "
        "extra character, extra head, group, three people, crowd, "
        "close-up, headshot, bust portrait, waist-up, upper body only, "
        "cropped legs, cropped feet, cropped shoes, cut off feet, missing feet, missing shoes, "
        "tight portrait framing, sitting, crouching, squatting, kneeling, action pose, "
        "hands on hips, arms akimbo, "
        "dynamic pose, running, jumping, long trousers, long pants, jeans, leggings, "
        "adult proportions, complex background, scenery, background scenery, outdoors, "
        "landscape, nature, trees, bushes, plants, fence, path, sky, clouds, grass, ground, "
        "interior, furniture, props, hat, cap, headwear, helmet, sunglasses, "
        "wrong colours, colour swap, inconsistent anatomy, unrequested clothing changes, "
        "unrequested accessories, incorrect viewing angle, photo, blurry, low quality, "
        "deformed, extra limbs, extra fingers, watermark, text, signature, logo, jpeg artifacts"
    )
    outfit_exclusions: list[str] = []
    if clothing is not None:
        text = clothing.lower()
        if not any(word in text for word in ("shirt", "top", "sweatshirt")):
            outfit_exclusions.append("shirt, collar")
        if not any(word in text for word in ("trouser", "shorts", "overalls", "dress", "skirt")):
            outfit_exclusions.append("trousers, pants, jeans")
        if "bow" not in text:
            outfit_exclusions.append("bow tie, necktie, cravat")
        outfit_exclusions.extend(_accessory_exclusions(clothing))
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
    return ", ".join(
        part
        for part in (
            single_view_exclusions,
            ", ".join(outfit_exclusions),
            exclusions,
            NEGATIVE_DEFAULT,
        )
        if part
    )


_IDENTITY_TAIL = re.compile(r"\s+and\s+one\s+of\b.*$", re.IGNORECASE)
_IDENTITY_CLAUSE = re.compile(
    r"^(two|three|four|five|six|seven)[- ]year[- ]old\s+human\s+(boy|girl|child)$",
    re.IGNORECASE,
)
_APPEARANCE_META = re.compile(
    r"visual direction|caricature|stereotyp|proportions|silhouette|"
    r"preserve consistent|keep consistent|across poses",
    re.IGNORECASE,
)
_DANGLING_WORDS = {
    "and", "a", "an", "the", "with", "of", "in", "on", "at", "to", "for", "or",
    "but", "slightly", "very", "soft", "rounded", "short", "long", "little",
    "warm", "cute", "young", "expressive", "colourful", "colorful",
}
_FACE_TERMS = re.compile(
    r"\b(eye|eyes|face|facial|muzzle|smile|smiling|expression|expressive)\b",
    re.IGNORECASE,
)


def _back_safe(text: str) -> str:
    """Drop face/eye clauses from back-view appearance and style text."""
    kept: list[str] = []
    for fragment in re.split(r"[;,]\s*|\s+and\s+", text):
        fragment = fragment.strip()
        if fragment and not _FACE_TERMS.search(fragment):
            kept.append(fragment)
    return ", ".join(kept)


def _short_identity(description: str) -> str:
    """Return the compact species/age clause from a profile description."""
    text = _phrase(description)
    text = re.sub(
        r"^draft\s+character\s+profile\s*[:\-—]?\s*", "", text, flags=re.IGNORECASE
    )
    text = _IDENTITY_TAIL.sub("", text)
    return " ".join(text.split(".")[0].split()[:8]).strip()


def _short_appearance(appearance: str, max_words: int = 10) -> str:
    """Return complete leading appearance phrases without dangling modifiers."""
    fragments = re.split(r"[;,.]", _phrase(appearance))
    kept: list[str] = []
    words = 0
    for fragment in fragments:
        parts = fragment.split()
        while parts and parts[-1].lower().strip("()") in _DANGLING_WORDS:
            parts.pop()
        clause = " ".join(parts).strip()
        if not clause or _APPEARANCE_META.search(clause):
            continue
        if _IDENTITY_CLAUSE.match(clause):
            continue
        size = len(parts)
        if words + size > max_words and kept:
            continue
        kept.append(clause)
        words += size
    return ", ".join(kept)


def _core_clothing(clothing: str, max_words: int = 12, include_signature: bool = True) -> str:
    """Return the primary outfit, dropping optional signature-accessory notes."""
    text = re.split(r";", _phrase(clothing))[0]
    text = re.sub(
        r"\s+as\s+signature\s+(clothing|accessory)\b.*$", "", text, flags=re.IGNORECASE
    )
    kept: list[str] = []
    words = 0
    for fragment in text.split(","):
        # Keep signature callouts such as "with a small star patch" in the CLIP
        # core; drop other trailing "with ..." flourishes that seed patterns.
        # Back views omit the front-bib signature detail entirely.
        if not include_signature or not re.search(r"\b(star|patch)\b", fragment, re.IGNORECASE):
            fragment = re.sub(r"\s+with\s+.*$", "", fragment, flags=re.IGNORECASE)
        parts = fragment.split()
        while parts and parts[-1].lower().strip("()") in _DANGLING_WORDS:
            parts.pop()
        if not parts:
            continue
        if words + len(parts) > max_words and kept:
            continue
        kept.append(" ".join(parts))
        words += len(parts)
    return ", ".join(kept)


def character_prompt(character: dict[str, Any], kind: str, label: str, extra: str | None = None):
    """Compose a repeatable prompt from saved identity fields and a single explicit view.

    Critical framing and view instructions come before descriptive text because CLIP
    truncates SDXL prompts at 77 tokens.
    """
    parts: list[str] = []
    if kind in {"reference", "turnaround"}:
        parts.append(REFERENCE_PREAMBLE)
    else:
        parts.append(_clean(character.get("name")))
    description = _phrase(character.get("description"))
    appearance = _phrase(character.get("appearance"))
    clothing = _phrase(character.get("clothing"))
    style = _phrase(character.get("style"))
    appearance_positive = _strip_negated_accessories(appearance)
    clothing_positive = _strip_negated_accessories(clothing)

    label = _clean(label)
    if kind == "cutout":
        parts.append("full body 2D cartoon character, head to toe, entire body visible")
        for value in (description, appearance_positive):
            if value:
                parts.append(value)
        if clothing_positive:
            parts.append(f"wearing {clothing_positive}")
        if style:
            parts.append(style)
        parts.append("one character only, alone, no animals, no props")
        parts.append("(flat solid bright chroma green background:1.5), (no shadow, no floor, no ground:1.4)")
        parts.append(
            "full-length wide framing, lots of headroom above the head, both feet fully visible, "
            f"{label or 'standing naturally'}, no text"
        )
    elif kind == "expression":
        for value in (description, appearance_positive):
            if value:
                parts.append(value)
        if clothing_positive:
            parts.append(f"wearing {clothing_positive}")
        if style:
            parts.append(style)
        parts.append(style_text())
        parts.append(
            f"single head and shoulders portrait showing {label or 'a neutral expression'}, "
            "one expression only, plain light background, no multiple views"
        )
    elif kind == "pose":
        for value in (description, appearance_positive):
            if value:
                parts.append(value)
        if clothing_positive:
            parts.append(f"wearing {clothing_positive}")
        if style:
            parts.append(style)
        parts.append(style_text())
        parts.append(
            f"single full body character in a {label or 'standing naturally'} pose, "
            "one character only, plain light background, clear silhouette, no multiple views"
        )
    else:
        view = _normalise_view(label)
        is_back = view == "back"
        view_instructions = {
            "front": (
                "front view, facing camera, looking at camera, arms at sides, standing, "
                "neutral pose"
            ),
            "three quarter": (
                "three-quarter view at approximately 45 degrees, arms at sides, standing, "
                "neutral pose"
            ),
            "side profile": (
                "true side profile at exactly 90 degrees, body facing screen right, "
                "only the near eye visible, arms at sides, standing, neutral pose"
            ),
            "back": (
                "rear view, body facing directly away from the camera, back of head and back "
                "of clothing visible, face completely hidden, no facial features visible, "
                "no front-facing eyes, standing, neutral pose"
            ),
        }
        camera_instruction = view_instructions.get(
            view,
            f"{view} view, body aligned to the requested camera angle, neutral pose",
        )
        parts.append(camera_instruction)
        parts.append(
            "single full-body character, full-length wide shot, both feet fully visible"
        )
        parts.append(_clean(character.get("name")))
        parts.append(_short_identity(character.get("description") or ""))
        short_appearance = _short_appearance(appearance_positive)
        if is_back:
            short_appearance = _back_safe(short_appearance)
        if short_appearance:
            parts.append(short_appearance)
        core_clothing = _core_clothing(clothing_positive, include_signature=not is_back)
        if core_clothing:
            parts.append(f"wearing {core_clothing}")
        parts.append("not a portrait, not a headshot, not a waist-up crop")
        parts.append("clean bold outlines, flat colors, children's 2D animation")
        # Secondary detail is appended after the 77-token core so SDXL keeps framing
        # and wardrobe even though CLIP truncates the tail.
        parts.append("one camera angle only, one character, one view")
        if view == "front":
            parts.append(
                "body facing directly toward the camera, both arms and legs clearly visible, "
                "or forelimbs and hindlimbs where applicable"
            )
        if is_back:
            # Positive phrasing only: "no straps" would seed strap tokens in CLIP.
            parts.append(
                "uninterrupted fabric across the back, clean smooth back silhouette, "
                "back of the top and overalls fully visible"
            )
        elif view == "side profile":
            parts.append("clean torso silhouette, uninterrupted side profile of the outfit")
        if appearance_positive and not is_back:
            parts.append(appearance_positive)
        clothing_tail = clothing_positive
        if is_back:
            clothing_tail = ". ".join(
                sentence
                for sentence in _sentences(clothing_positive)
                if "signature" not in sentence.lower()
            )
        if clothing_tail:
            parts.append(clothing_tail)
        if style:
            parts.append(_back_safe(style) if is_back else style)
        parts.append(style_text(back=is_back))

    if extra:
        parts.append(extra.strip())
    return ", ".join(part for part in parts if part)


def background_prompt(background: dict[str, Any], extra: str | None = None) -> str:
    parts: list[str] = [_clean(background.get("name"))]
    description = _clean(background.get("description"))
    if description:
        parts.append(description)
    parts.append(style_text())
    parts.append("environment background art, establishing shot, no characters, no people, no text")
    if extra:
        parts.append(extra.strip())
    return ", ".join(part for part in parts if part)


def scene_negative_prompt(characters: list[dict[str, Any]]) -> str:
    """Scene negative prompt plus wardrobe-accessory exclusions for the cast.

    A character whose profile says "No backpack" must also suppress backpacks in
    group shots, not just in solo reference sheets.
    """
    phrases: list[str] = []
    for character in characters:
        for phrase in _accessory_exclusions(character.get("clothing")):
            if phrase not in phrases:
                phrases.append(phrase)
    if not phrases:
        return NEGATIVE_DEFAULT
    return ", ".join([*phrases, NEGATIVE_DEFAULT])


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
        appearance = _strip_negated_accessories(character.get("appearance") or "")
        clothing = _strip_negated_accessories(character.get("clothing") or "")
        style = _clean(character.get("style"))
        if appearance:
            bits.append(appearance)
        if clothing:
            bits.append(f"wearing {clothing}")
        if style:
            bits.append(style)
        parts.append(", ".join(bit for bit in bits if bit))

    parts.append(style_text())
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
