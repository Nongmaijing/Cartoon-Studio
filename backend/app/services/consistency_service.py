from __future__ import annotations

from typing import Any

from . import character_service, llm_provider
from .assets import asset_file, get_asset

CONSISTENCY_PROMPT = """You are a character continuity reviewer for a children's animation studio.
Image 1 is the approved master reference for the character.
Image 2 is a newly generated image that should show the same character.

Compare the two images on identity, not pose or background:
- facial structure and features
- hairstyle and hair color
- apparent age and body proportions
- clothing, footwear and accessories
- color palette and distinguishing marks

Return ONLY a JSON object with this shape:
{"same_character": true, "confidence": 0.0, "wardrobe_match": true,
 "differences": [], "summary": "one sentence"}

Set same_character to false if the images could not plausibly be the same character.
Use confidence between 0 and 1. Put concrete observations in differences; do not copy
placeholder values from the shape above. The two images may show different poses or views,
so ignore pose and camera angle when judging identity."""


async def check_identity(
    character_id: str,
    candidate_asset_id: str,
    *,
    model: str | None = None,
) -> dict[str, Any]:
    character = character_service.get_character(character_id)
    canonical_id = character.get("canonical_asset_id")
    if not canonical_id:
        raise ValueError(
            "This character has no approved canonical reference. Set a canonical asset first."
        )
    canonical = asset_file(canonical_id)
    if not canonical:
        raise ValueError("The canonical reference file is missing on disk.")
    candidate = get_asset(candidate_asset_id)
    if not candidate:
        raise ValueError("Candidate asset not found.")
    candidate_file = asset_file(candidate_asset_id)
    if not candidate_file:
        raise ValueError("Candidate asset file is missing on disk.")
    if candidate.get("project_id") != character.get("project_id"):
        raise ValueError("Candidate image belongs to a different project.")
    if candidate.get("kind") != "image":
        raise ValueError("Candidate asset must be an image.")

    canonical_path, _ = canonical
    candidate_path, _ = candidate_file
    verdict = await llm_provider.vision_compare(
        [str(canonical_path), str(candidate_path)],
        CONSISTENCY_PROMPT,
        model=model,
    )
    return {
        "character_id": character_id,
        "canonical_asset_id": canonical_id,
        "candidate_asset_id": candidate_asset_id,
        "same_character": bool(verdict.get("same_character")),
        "confidence": verdict.get("confidence"),
        "wardrobe_match": verdict.get("wardrobe_match"),
        "differences": verdict.get("differences") or [],
        "summary": verdict.get("summary") or "",
        "model": verdict.get("model"),
        "provider": verdict.get("provider"),
        "human_review_required": True,
    }
