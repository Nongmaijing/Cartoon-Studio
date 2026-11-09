from __future__ import annotations

import json
import re
from typing import Any

from ..core.runtime import openai_settings
from ..services.errors import ConfigurationError, ServiceError


def _extract_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text
    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            value = getattr(content, "text", None)
            if isinstance(value, str):
                chunks.append(value)
    return "\n".join(chunks).strip()


def _parse_json(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = min([index for index in (cleaned.find("{"), cleaned.find("[")) if index >= 0], default=-1)
        if start >= 0:
            for end in range(len(cleaned), start, -1):
                try:
                    return json.loads(cleaned[start:end])
                except json.JSONDecodeError:
                    continue
    raise ServiceError("OpenAI returned text that was not valid JSON.")


async def generate_text(prompt: str) -> str:
    settings = openai_settings()
    if not settings["api_key"] or not settings["model"]:
        raise ConfigurationError("OpenAI is not configured. Set OPENAI_API_KEY and OPENAI_MODEL.")
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings["api_key"], base_url=settings["base_url"])
    response = await client.responses.create(model=settings["model"], input=prompt)
    text = _extract_text(response)
    if not text:
        raise ServiceError("OpenAI returned an empty response.")
    return text


async def generate_json(prompt: str) -> Any:
    text = await generate_text(prompt)
    return _parse_json(text)
