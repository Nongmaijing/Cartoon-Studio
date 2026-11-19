from __future__ import annotations

from typing import Any

from ..db import query_one
from .errors import NotFoundError, ServiceError


def validate_canonical_asset(character: dict[str, Any], asset_id: str | None) -> dict[str, Any]:
    """Return the canonical asset row when it is a valid reference for this character.

    A valid canonical asset:
    - exists;
    - is an image;
    - belongs to the same project as the character;
    - is linked to this character as a reference or pose image.
    """
    if not asset_id:
        raise ServiceError(
            "A canonical reference image is required before a character can be approved.",
            status_code=409,
            code="canonical_required",
        )
    asset = query_one("SELECT id, project_id, kind FROM assets WHERE id = ?", (asset_id,))
    if not asset:
        raise NotFoundError("Canonical reference asset not found.")
    character_project = character.get("project_id")
    if not character_project or asset.get("project_id") != character_project:
        raise ServiceError(
            "Canonical reference asset belongs to a different project.",
            status_code=409,
            code="canonical_project_mismatch",
        )
    if asset.get("kind") != "image":
        raise ServiceError(
            "Canonical reference must be an image.",
            status_code=409,
            code="canonical_not_image",
        )
    link = query_one(
        """SELECT id FROM media_links
           WHERE asset_id = ? AND owner_type = 'character' AND owner_id = ?
             AND role IN ('reference', 'pose')
           LIMIT 1""",
        (asset_id, character.get("id")),
    )
    if not link:
        raise ServiceError(
            "Canonical reference must be linked to this character as a reference or pose image.",
            status_code=409,
            code="canonical_not_linked",
        )
    return asset
