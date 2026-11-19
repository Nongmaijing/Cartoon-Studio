from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..schemas import ModelDownloadRequest
from ..schemas_ai import FastModeUpdate, ModelConfigUpdate
from ..services import model_config_service, model_download_service
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


@router.get("/fast-mode")
async def fast_mode() -> dict[str, Any]:
    return model_config_service.fast_mode_status()


@router.put("/fast-mode")
async def update_fast_mode(payload: FastModeUpdate) -> dict[str, Any]:
    try:
        return model_config_service.save_fast_mode(payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/downloads")
async def downloads() -> list[dict[str, Any]]:
    return model_download_service.list_downloads()


@router.post("/downloads", status_code=202)
async def start_download(payload: ModelDownloadRequest) -> dict[str, Any]:
    try:
        return await model_download_service.start_download(
            payload.recommendation,
            accept_license=payload.accept_license,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/downloads/{download_id}")
async def download_status(download_id: str) -> dict[str, Any]:
    state = model_download_service.get_download(download_id)
    if not state:
        raise HTTPException(status_code=404, detail="Download not found.")
    return state


@router.post("/downloads/{download_id}/cancel")
async def cancel_download(download_id: str) -> dict[str, Any]:
    state = model_download_service.cancel_download(download_id)
    if not state:
        raise HTTPException(status_code=404, detail="Download not found.")
    return state
