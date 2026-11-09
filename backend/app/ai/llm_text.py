from __future__ import annotations

from typing import Any

from ..services import llm_provider


async def generate_text(prompt: str) -> str:
    """Generate text using Ollama when available, otherwise OpenAI."""
    return await llm_provider.generate_text(prompt)


async def generate_json(prompt: str) -> Any:
    """Generate structured JSON using the configured local or external LLM."""
    return await llm_provider.generate_json(prompt)
