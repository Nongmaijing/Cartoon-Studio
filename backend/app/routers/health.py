from __future__ import annotations

from fastapi import APIRouter

from ..core.runtime import integration_status
from ..providers.registry import registry
from ..services.stats import system_stats

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health() -> dict:
    from ..main import APP_VERSION

    return {
        "status": "ok",
        "version": APP_VERSION,
        "integration": integration_status(),
        "providers": [info.as_dict() for info in registry.list_infos()],
        "system": system_stats(),
    }
