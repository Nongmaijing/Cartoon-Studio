from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from ..config import load_config


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env(name, "1" if default else "0").lower()
    return value in ("1", "true", "yes", "on")


def openai_settings() -> dict[str, Any]:
    config = load_config()
    ai = config.get("ai") or {}
    return {
        "api_key": _env("OPENAI_API_KEY"),
        "model": _env("OPENAI_MODEL", str(ai.get("model") or "")),
        "base_url": _env("OPENAI_BASE_URL", str(ai.get("base_url") or "https://api.openai.com/v1")),
        "max_tool_rounds": int(_env("OPENAI_MAX_TOOL_ROUNDS", str(ai.get("max_tool_rounds", 8)))),
        "timeout_seconds": float(_env("OPENAI_TIMEOUT_SECONDS", str(ai.get("timeout_seconds", 120)))),
        "max_context_chars": int(ai.get("max_context_chars", 60000)),
    }


def _csv_env(name: str) -> list[str]:
    value = _env(name)
    return [item.strip() for item in value.split(",") if item.strip()]


def mcp_settings() -> dict[str, Any]:
    config = load_config()
    mcp = config.get("mcp") or {}
    return {
        "host": _env("MCP_HOST", str(mcp.get("host") or "127.0.0.1")),
        "port": int(_env("MCP_PORT", str(mcp.get("port", 8020)))),
        "public_url": _env("MCP_PUBLIC_URL", str(mcp.get("public_url") or "")),
        "transport": _env("MCP_TRANSPORT", str(mcp.get("transport") or "streamable-http")),
        "bearer_token": _env("MCP_BEARER_TOKEN"),
        "auth_mode": _env("MCP_AUTH_MODE", str(mcp.get("auth_mode") or "bearer")).lower(),
        "allow_unauthenticated": _env_bool("MCP_ALLOW_UNAUTHENTICATED", False),
        "allowed_hosts": _csv_env("MCP_ALLOWED_HOSTS"),
        "allowed_origins": _csv_env("MCP_ALLOWED_ORIGINS"),
        "enabled": _env_bool("MCP_ENABLED", bool(mcp.get("enabled", False))),
    }


def base_url() -> str:
    config = load_config()
    return _env(
        "CARTOON_STUDIO_BASE_URL",
        f"http://{config['server']['host']}:{config['server']['port']}",
    ).rstrip("/")


def allow_cloud_generation() -> bool:
    config = load_config()
    return _env_bool("ALLOW_CLOUD_GENERATION", bool((config.get("providers") or {}).get("allow_cloud", False)))


def ai_qc_enabled() -> bool:
    return _env_bool("ENABLE_AI_QC", False)


def integration_status() -> dict[str, Any]:
    ai = openai_settings()
    mcp = mcp_settings()
    config = load_config()
    return {
        "openai": {
            "configured": bool(ai["api_key"] and ai["model"]),
            "model": ai["model"] or None,
            "base_url": ai["base_url"],
            "api_key_present": bool(ai["api_key"]),
        },
        "mcp": {
            "enabled": mcp["enabled"],
            "transport": mcp["transport"],
            "public_url": mcp["public_url"] or None,
            "auth_mode": mcp["auth_mode"],
            "token_configured": bool(mcp["bearer_token"]),
        },
        "providers": {
            "allow_cloud": allow_cloud_generation(),
            "default_image": (config.get("providers") or {}).get("default_image", "comfyui"),
            "default_video": (config.get("providers") or {}).get("default_video", "comfyui"),
            "default_audio": (config.get("providers") or {}).get("default_audio", "kokoro"),
            "default_editing": (config.get("providers") or {}).get("default_editing", "ffmpeg"),
        },
        "ai_qc_enabled": ai_qc_enabled(),
        "server_time": time.time(),
    }
