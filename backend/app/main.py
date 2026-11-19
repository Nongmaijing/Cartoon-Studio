from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .comfy.discovery import discover_comfy
from .config import BASE_DIR, ensure_dirs, load_config, save_config
from .db import init_db
from .logging_setup import logger
from .orchestration.production_orchestrator import resume_pending_runs
from .routers import (
    ai_director,
    animation,
    assets,
    backgrounds,
    characters,
    comfy,
    dashboard,
    dialogue,
    editing,
    episodes,
    generate,
    health,
    llm,
    lip_sync,
    mcp_support,
    models,
    motion,
    production,
    projects,
    providers,
    registry,
    resources,
    scenes,
    settings,
    speech,
    voice,
    workflows,
)
from .services.episodes import mark_interrupted_exports
from .services.jobs import runner
from .services import mcp_tunnel_service, opencode_tunnel_service

load_dotenv(BASE_DIR / ".env")
APP_VERSION = "0.7.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    ensure_dirs(config)
    init_db()
    mark_interrupted_exports()
    await resume_pending_runs()
    await mcp_tunnel_service.cleanup_stale_state()
    await opencode_tunnel_service.cleanup_stale_state()

    # Discover the live ComfyUI installation once at startup, then remember it.
    try:
        info = discover_comfy(config)
        changed = False
        if info["install_path"] and not config["comfyui"].get("install_path"):
            config["comfyui"]["install_path"] = info["install_path"]
            changed = True
        if info["output_dir"] and not config["comfyui"].get("output_dir"):
            config["comfyui"]["output_dir"] = info["output_dir"]
            changed = True
        if info["model_dirs"] and not config["comfyui"].get("models_dirs"):
            config["comfyui"]["models_dirs"] = info["model_dirs"]
            changed = True
        if changed:
            save_config(config)
        logger.info(
            "ComfyUI discovery: install=%s server=%s models=%s",
            info.get("install_path"),
            config["comfyui"]["server_url"],
            config["comfyui"].get("models_dirs"),
        )
    except Exception as exc:  # noqa: BLE001 - discovery is best effort
        logger.warning("ComfyUI discovery failed: %s", exc)

    await runner.start()
    logger.info("Cartoon Studio backend %s ready on port %s.", APP_VERSION, config["server"]["port"])
    yield
    await runner.stop()
    logger.info("Cartoon Studio backend stopped.")


app = FastAPI(title="Cartoon Studio", version=APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(projects.router)
app.include_router(characters.router)
app.include_router(backgrounds.router)
app.include_router(scenes.router)
app.include_router(animation.router)
app.include_router(voice.router)
app.include_router(dialogue.router)
app.include_router(episodes.router)
app.include_router(ai_director.router)
app.include_router(production.router)
app.include_router(providers.router)
app.include_router(resources.router)
app.include_router(registry.router)
app.include_router(mcp_support.router)
app.include_router(models.router)
app.include_router(motion.router)
app.include_router(health.router)
app.include_router(llm.router)
app.include_router(lip_sync.router)
app.include_router(workflows.router)
app.include_router(speech.router)
app.include_router(editing.router)
app.include_router(generate.router)
app.include_router(assets.router)
app.include_router(settings.router)
app.include_router(comfy.router)


@app.get("/api/health")
async def health() -> dict:
    config = load_config()
    return {
        "status": "ok",
        "app": "Cartoon Studio",
        "version": APP_VERSION,
        "time": datetime.now(timezone.utc).isoformat(),
        "comfyui_server": config["comfyui"]["server_url"],
    }


# Serve the built frontend when it exists (production mode). In development,
# Vite serves the UI and proxies /api to this backend.
_dist = BASE_DIR / "frontend" / "dist"
if (_dist / "index.html").exists():
    if (_dist / "assets").exists():
        app.mount("/ui-assets", StaticFiles(directory=_dist / "assets"), name="ui-assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found.")
        candidate = _dist / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html")
