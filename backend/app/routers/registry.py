from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..services import production_registry_service

router = APIRouter(prefix="/api/v1/registry", tags=["registry"])


@router.get("")
async def registry() -> dict[str, Any]:
    return await production_registry_service.registry()


@router.get("/recommendations")
async def recommendations() -> dict[str, Any]:
    data = await production_registry_service.registry()
    return {"recommendations": data["recommendations"], "note": data["note"]}
