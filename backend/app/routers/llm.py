from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..services import llm_provider
from ..services.assets import asset_file
from ..services.errors import ServiceError

router = APIRouter(prefix="/api/v1/llm", tags=["llm"])


@router.get("/health")
async def health() -> dict[str, Any]:
    return await llm_provider.health()


@router.get("/models")
async def models() -> dict[str, Any]:
    return {"models": await llm_provider.ollama_models()}


@router.post("/generate")
async def generate(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required.")
    try:
        if payload.get("json_mode"):
            data = await llm_provider.generate_json(
                prompt,
                provider=payload.get("provider"),
                model=payload.get("model"),
                system=payload.get("system"),
            )
            return {"json": data}
        text = await llm_provider.generate_text(
            prompt,
            provider=payload.get("provider"),
            model=payload.get("model"),
            system=payload.get("system"),
        )
        return {"text": text}
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/vision-review")
async def vision_review(payload: dict[str, Any]) -> dict[str, Any]:
    asset_id = str(payload.get("asset_id") or "").strip()
    prompt = str(payload.get("prompt") or "").strip()
    if not asset_id:
        raise HTTPException(status_code=400, detail="asset_id is required.")
    if not prompt:
        prompt = (
            "Review this cartoon production image. Return JSON with keys: "
            "character_identity, clothing, accessories, colors, character_count, composition, "
            "background, defects, continuity, score (0-10 or null), summary, issues (array). "
            "Do not claim certainty beyond what you can see. Set human_review_required to true."
        )
    resolved = asset_file(asset_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Asset file not found.")
    path, _asset = resolved
    try:
        return await llm_provider.vision_review(str(path), prompt, model=payload.get("model"))
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
