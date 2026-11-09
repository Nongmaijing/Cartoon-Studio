from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..schemas_ai import ModelConfigUpdate
from ..services import model_config_service
from ..services.errors import ServiceError

router = APIRouter(prefix="/api/v1/models", tags=["models"])


def _raise(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/catalog")
async def catalog() -> dict[str, Any]:
    return await model_config_service.catalog()


@router.get("/config")
async def config() -> dict[str, Any]:
    return model_config_service.get_model_config()


@router.put("/config")
async def update_config(payload: ModelConfigUpdate) -> dict[str, Any]:
    try:
        return {"models": model_config_service.save_model_config(payload.models)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/recommendations")
async def recommendations() -> dict[str, Any]:
    data = await model_config_service.catalog()
    return {"recommendations": data["recommendations"], "note": data["note"]}
