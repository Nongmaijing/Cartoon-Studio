from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..comfy.client import ComfyClient, ComfyError
from ..config import load_config
from ..db import query
from .base import ProviderError, ProviderInfo
from .comfyui_image import ComfyUIImageProvider
from .comfyui_video import ComfyUIVideoProvider
from .ffmpeg_editing import FFmpegEditingProvider
from .kokoro_audio import KokoroAudioProvider
from .openai_image import OpenAIImageProvider

PROVIDER_CLASSES: dict[str, dict[str, type]] = {
    "image": {"comfyui": ComfyUIImageProvider, "openai": OpenAIImageProvider},
    "video": {"comfyui": ComfyUIVideoProvider},
    "audio": {"kokoro": KokoroAudioProvider},
    "editing": {"ffmpeg": FFmpegEditingProvider},
}


class ProviderRegistry:
    def __init__(self) -> None:
        self._app_config = load_config()
        self._providers: dict[str, dict[str, Any]] = {}
        self.refresh()

    def _rows(self) -> list[dict[str, Any]]:
        try:
            return query("SELECT * FROM provider_configs WHERE enabled = 1")
        except sqlite3.OperationalError:
            return []

    def refresh(self) -> None:
        self._app_config = load_config()
        self._providers = {}
        rows = self._rows()
        row_config = {(row["type"], row["name"]): row for row in rows}
        for provider_type, classes in PROVIDER_CLASSES.items():
            for name, cls in classes.items():
                config = self._app_config
                if provider_type == "image" and name == "openai":
                    row = row_config.get((provider_type, name))
                    config = {}
                    if row:
                        try:
                            config = json.loads(row.get("config_json") or "{}")
                        except (TypeError, json.JSONDecodeError):
                            config = {}
                try:
                    provider = cls(config)
                except Exception:  # noqa: BLE001 - a missing optional provider must not break the registry
                    continue
                self._providers.setdefault(provider_type, {})[name] = provider

    def _default_name(self, provider_type: str) -> str:
        providers = self._app_config.get("providers") or {}
        return str(providers.get(f"default_{provider_type}") or next(iter(PROVIDER_CLASSES[provider_type])))

    def get(self, provider_type: str, name: str | None = None) -> Any:
        if provider_type not in PROVIDER_CLASSES:
            raise ProviderError(f"Unknown provider type '{provider_type}'.")
        chosen = name or self._default_name(provider_type)
        provider = (self._providers.get(provider_type) or {}).get(chosen)
        if not provider:
            raise ProviderError(f"Provider '{chosen}' is not registered for type '{provider_type}'.")
        if not provider.info.available:
            raise ProviderError(f"Provider '{chosen}' is not available: {provider.info.notes}")
        return provider

    def list_infos(self) -> list[ProviderInfo]:
        result: list[ProviderInfo] = []
        for providers in self._providers.values():
            result.extend(provider.info for provider in providers.values())
        return result

    async def status(self) -> dict[str, Any]:
        config = self._app_config
        client = ComfyClient(
            config["comfyui"]["server_url"],
            timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
        )
        comfy_connected = False
        comfy_device = None
        try:
            stats = await client.system_stats()
            comfy_connected = True
            devices = stats.get("devices") or []
            if devices:
                comfy_device = devices[0]
        except ComfyError:
            comfy_connected = False
        infos = []
        for info in self.list_infos():
            item = info.as_dict()
            if info.type in ("image", "video") and info.name == "comfyui":
                item["live_connected"] = comfy_connected
                item["available"] = bool(info.available and comfy_connected)
                item["device"] = comfy_device
            infos.append(item)
        return {
            "providers": infos,
            "comfyui_connected": comfy_connected,
            "defaults": {
                "image": self._default_name("image"),
                "video": self._default_name("video"),
                "audio": self._default_name("audio"),
                "editing": self._default_name("editing"),
            },
        }


registry = ProviderRegistry()
