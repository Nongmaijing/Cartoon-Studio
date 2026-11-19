"""Art-direction presets for image and video prompts.

The render pipeline used to hardcode one Western preschool style. Art direction
is now a configuration choice so a series can switch between a painterly
storybook look, a clean anime look or the original flat Western cartoon without
touching code.

Set ``creative.art_style`` in ``config/config.json`` (or via
``PUT /api/settings``). Unknown ids fall back to ``ghibli_painterly``.
"""

from __future__ import annotations

from typing import Any

DEFAULT_STYLE = "ghibli_painterly"

STYLE_PRESETS: dict[str, dict[str, str]] = {
    "ghibli_painterly": {
        "name": "Painterly storybook (Ghibli-inspired)",
        "positive": (
            "ghibli-inspired hand-painted 2D animation, painterly gouache backgrounds, "
            "soft watercolour washes, delicate ink linework, warm nostalgic colour palette, "
            "gentle cel shading, expressive readable faces, expressive storybook characters, "
            "clean readable silhouettes, cinematic composition"
        ),
        "back": (
            "ghibli-inspired hand-painted 2D animation, painterly gouache backgrounds, "
            "soft watercolour washes, delicate ink linework, warm nostalgic colour palette, "
            "gentle cel shading, clean readable silhouettes, cinematic composition"
        ),
        "negative_extra": (
            "3d render, cgi, plastic, photorealistic, harsh digital outlines, neon colours, "
            "generic anime screencap"
        ),
    },
    "storybook_painterly": {
        "name": "Storybook watercolour",
        "positive": (
            "hand-painted storybook illustration, soft watercolour and gouache, pastel palette, "
            "gentle ink outlines, whimsical shapes, tactile paper texture, warm light, "
            "cinematic composition"
        ),
        "back": (
            "hand-painted storybook illustration, soft watercolour and gouache, pastel palette, "
            "gentle ink outlines, whimsical shapes, tactile paper texture, warm light"
        ),
        "negative_extra": "3d render, cgi, photorealistic, harsh outlines, neon colours",
    },
    "clean_anime": {
        "name": "Clean anime keyframe",
        "positive": (
            "modern 2D anime keyframe, crisp confident line art, flat cel shading, "
            "expressive readable faces, detailed painted background, cinematic lighting, "
            "consistent character design"
        ),
        "back": (
            "modern 2D anime keyframe, crisp confident line art, flat cel shading, "
            "detailed painted background, cinematic lighting, consistent character design"
        ),
        "negative_extra": "3d render, cgi, photorealistic, sketch, rough lines",
    },
    "western_preschool": {
        "name": "Flat Western preschool cartoon",
        "positive": (
            "premium Western preschool 2D television animation, stylized graphic cartoon design, "
            "clean confident outlines, simplified rounded shapes, flat solid color fills, "
            "subtle cel shading, expressive readable faces, appealing silhouettes, "
            "consistent proportions"
        ),
        "back": (
            "premium Western preschool 2D television animation, stylized graphic cartoon design, "
            "clean confident outlines, simplified rounded shapes, flat solid color fills, "
            "subtle cel shading, appealing silhouettes, consistent proportions"
        ),
        "negative_extra": "3d render, cgi, photorealistic, painterly, sketch, rough lines",
    },
}


def available_styles() -> list[dict[str, str]]:
    """Return the selectable presets (id, name and positive prompt)."""
    return [
        {"id": style_id, "name": preset["name"], "positive": preset["positive"]}
        for style_id, preset in STYLE_PRESETS.items()
    ]


def resolve_style(config: dict[str, Any] | None = None) -> dict[str, str]:
    """Return the active preset, falling back to the default on unknown ids."""
    if config is None:
        from ..config import load_config

        config = load_config()
    creative = (config or {}).get("creative") or {}
    style_id = str(creative.get("art_style") or DEFAULT_STYLE)
    preset = STYLE_PRESETS.get(style_id) or STYLE_PRESETS[DEFAULT_STYLE]
    resolved = dict(preset)
    resolved["id"] = style_id if style_id in STYLE_PRESETS else DEFAULT_STYLE
    custom = str(creative.get("custom_style") or "").strip()
    if custom:
        resolved["positive"] = f"{resolved['positive']}, {custom}"
        resolved["back"] = f"{resolved['back']}, {custom}"
    return resolved


def style_text(back: bool = False, config: dict[str, Any] | None = None) -> str:
    preset = resolve_style(config)
    return preset["back"] if back else preset["positive"]


def style_negative_extra(config: dict[str, Any] | None = None) -> str:
    return resolve_style(config).get("negative_extra", "")
