from __future__ import annotations

import base64
import json
import os
import re
from typing import Any

import httpx

from ..config import load_config
from ..core.runtime import openai_settings
from .errors import ConfigurationError, ServiceError


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def llm_settings() -> dict[str, Any]:
    config = load_config()
    section = config.get("llm") or {}
    return {
        "provider": (_env("LLM_PROVIDER", str(section.get("provider") or "auto")) or "auto").lower(),
        "ollama_url": _env("OLLAMA_BASE_URL", str(section.get("ollama_url") or "http://127.0.0.1:11434")).rstrip("/"),
        "ollama_model": _env("OLLAMA_MODEL", str(section.get("ollama_model") or "qwen3:8b")),
        "vision_model": _env("OLLAMA_VISION_MODEL", str(section.get("vision_model") or "qwen2.5vl:7b")),
        "timeout_seconds": float(_env("OLLAMA_TIMEOUT_SECONDS", str(section.get("timeout_seconds", 180)))),
        "temperature": float(section.get("temperature", 0.4)),
    }


async def ollama_tags() -> list[dict[str, Any]]:
    settings = llm_settings()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{settings['ollama_url']}/api/tags")
            response.raise_for_status()
            data = response.json()
            return list(data.get("models") or [])
    except (httpx.HTTPError, ValueError):
        return []


async def ollama_models() -> list[dict[str, Any]]:
    models = []
    for item in await ollama_tags():
        details = item.get("details") or {}
        models.append(
            {
                "name": item.get("name") or item.get("model"),
                "size_bytes": item.get("size"),
                "size_gb": round((item.get("size") or 0) / (1024**3), 2) if item.get("size") else None,
                "family": details.get("family") or "",
                "parameter_size": details.get("parameter_size") or "",
                "quantization": details.get("quantization_level") or "",
                "context_length": details.get("context_length"),
                "capabilities": item.get("capabilities") or [],
                "modified_at": item.get("modified_at"),
            }
        )
    return models


def _extract_openai_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            value = getattr(content, "text", None)
            if isinstance(value, str):
                chunks.append(value)
    return "\n".join(chunks).strip()


def parse_json_text(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        starts = [index for index in (cleaned.find("{"), cleaned.find("[")) if index >= 0]
        start = min(starts) if starts else -1
        if start >= 0:
            for end in range(len(cleaned), start, -1):
                try:
                    return json.loads(cleaned[start:end])
                except json.JSONDecodeError:
                    continue
    raise ServiceError("The LLM returned text that was not valid JSON.")


async def _ollama_generate(
    prompt: str,
    *,
    model: str,
    json_mode: bool = False,
    system: str | None = None,
    images: list[str] | None = None,
    temperature: float | None = None,
) -> str:
    settings = llm_settings()
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": settings["temperature"] if temperature is None else temperature,
            "num_ctx": 8192,
        },
    }
    if system:
        payload["system"] = system
    if json_mode:
        payload["format"] = "json"
    if images:
        payload["images"] = images
    try:
        async with httpx.AsyncClient(timeout=settings["timeout_seconds"]) as client:
            response = await client.post(f"{settings['ollama_url']}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return str(data.get("response") or "")
    except httpx.HTTPError as exc:
        raise ConfigurationError(f"Ollama request failed: {exc}") from exc


async def _openai_generate(prompt: str, *, model: str | None = None, system: str | None = None) -> str:
    settings = openai_settings()
    if not settings["api_key"] or not settings["model"]:
        raise ConfigurationError("OpenAI is not configured. Set OPENAI_API_KEY and OPENAI_MODEL.")
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings["api_key"], base_url=settings["base_url"])
    input_items: Any = prompt
    if system:
        input_items = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    response = await client.responses.create(model=model or settings["model"], input=input_items)
    text = _extract_openai_text(response)
    if not text:
        raise ServiceError("OpenAI returned an empty response.")
    return text


async def _choose_provider(provider: str | None = None) -> str:
    selected = (provider or llm_settings()["provider"] or "auto").lower()
    if selected in ("ollama", "openai"):
        return selected
    if await ollama_tags():
        return "ollama"
    if openai_settings()["api_key"] and openai_settings()["model"]:
        return "openai"
    raise ConfigurationError(
        "No LLM provider is available. Start Ollama with a local model, or set OPENAI_API_KEY and OPENAI_MODEL."
    )


async def generate_text(
    prompt: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    system: str | None = None,
    json_mode: bool = False,
) -> str:
    chosen = await _choose_provider(provider)
    if chosen == "ollama":
        return await _ollama_generate(
            prompt,
            model=model or llm_settings()["ollama_model"],
            json_mode=json_mode,
            system=system,
        )
    return await _openai_generate(prompt, model=model, system=system)


async def generate_json(
    prompt: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    system: str | None = None,
) -> Any:
    text = await generate_text(prompt, provider=provider, model=model, system=system, json_mode=True)
    return parse_json_text(text)


async def vision_review(
    image_path: str,
    prompt: str,
    *,
    model: str | None = None,
) -> dict[str, Any]:
    settings = llm_settings()
    selected_model = model or settings["vision_model"]
    tags = await ollama_tags()
    available = {str(item.get("name") or item.get("model")) for item in tags}
    if not available:
        raise ConfigurationError("Ollama is not running or has no local models.")
    if selected_model not in available:
        raise ConfigurationError(
            f"Vision model '{selected_model}' is not installed in Ollama. Available: {', '.join(sorted(available))}"
        )
    try:
        with open(image_path, "rb") as handle:
            encoded = base64.b64encode(handle.read()).decode("ascii")
    except OSError as exc:
        raise ServiceError(f"Could not read image for vision review: {exc}") from exc
    text = await _ollama_generate(
        prompt,
        model=selected_model,
        json_mode=True,
        images=[encoded],
        temperature=0.1,
    )
    data = parse_json_text(text)
    if not isinstance(data, dict):
        raise ServiceError("Vision review did not return a JSON object.")
    data["model"] = selected_model
    data["provider"] = "ollama"
    data["human_review_required"] = True
    return data


async def health() -> dict[str, Any]:
    settings = llm_settings()
    tags = await ollama_tags()
    openai = openai_settings()
    return {
        "selected_provider": await _choose_provider() if (tags or (openai["api_key"] and openai["model"])) else None,
        "preferred": settings["provider"],
        "ollama": {
            "available": bool(tags),
            "url": settings["ollama_url"],
            "default_model": settings["ollama_model"],
            "vision_model": settings["vision_model"],
            "models": await ollama_models(),
        },
        "openai": {
            "configured": bool(openai["api_key"] and openai["model"]),
            "model": openai["model"] or None,
        },
    }
