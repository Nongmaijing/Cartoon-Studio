from __future__ import annotations

import json
from typing import Any

from ..ai.llm_text import generate_json
from ..db import execute, now
from . import episode_service, project_service
from .approval_service import approve_script as approve_script_record
from .audit_service import log
from .character_service import list_characters
from .errors import NotFoundError, ServiceError


def _save_episode_memory(episode_id: str, *, production: dict[str, Any] | None = None, script: dict[str, Any] | None = None) -> dict[str, Any]:
    episode = episode_service.get_episode(episode_id)
    current_production = episode.get("production") or {}
    current_script = episode.get("script") or {}
    if production is not None:
        current_production = {**current_production, **production}
    if script is not None:
        current_script = {**current_script, **script}
    execute(
        "UPDATE episodes SET production_json = ?, script_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(current_production), json.dumps(current_script), now(), episode_id),
    )
    return episode_service.get_episode(episode_id)


def _context(project_id: str) -> dict[str, Any]:
    project = project_service.get_project(project_id)
    characters = list_characters(project_id)
    return {
        "project": {
            "id": project["id"],
            "name": project["name"],
            "description": project.get("description"),
            "memory": project.get("memory"),
        },
        "characters": [
            {
                "id": character["id"],
                "name": character["name"],
                "description": character.get("description"),
                "appearance": character.get("appearance"),
                "clothing": character.get("clothing"),
                "style": character.get("style"),
                "approval_status": character.get("approval_status"),
            }
            for character in characters
        ],
    }


async def generate_story(
    project_id: str,
    premise: str,
    episode_id: str | None = None,
    actor: str = "user",
) -> dict[str, Any]:
    context = _context(project_id)
    if not episode_id:
        episode = episode_service.create_episode(
            project_id,
            name=premise[:70] or "New Episode",
            description=premise,
            actor=actor,
        )
        episode_id = episode["id"]
    prompt = f"""You are a children's animation storywriter.
Create a short, kind, school-appropriate story based on this premise: {premise}

Project context:
{json.dumps(context, ensure_ascii=False)}

Return ONLY valid JSON with this shape:
{{
  "title": "string",
  "logline": "string",
  "moral": "string",
  "scenes": [
    {{
      "title": "string",
      "summary": "string",
      "action": "string",
      "camera": "string",
      "characters": ["character name"],
      "dialogue": [{{"speaker": "character name or Narrator", "text": "string", "emotion": "neutral/happy/sad/scared/excited/calm"}}]
    }}
  ]
}}
Keep the story suitable for children ages 5-9. Do not include violence, scary imagery, or unsafe content."""
    story = await generate_json(prompt)
    if not isinstance(story, dict) or not isinstance(story.get("scenes"), list):
        raise ServiceError("The story generator returned an invalid structure.")
    _save_episode_memory(episode_id, production={"story": story}, script={"story": story})
    log(actor, "generate_story", "episode", episode_id, {"title": story.get("title")})
    return {"episode_id": episode_id, "story": story}


async def generate_script(
    episode_id: str,
    instructions: str | None = None,
    actor: str = "user",
) -> dict[str, Any]:
    episode = episode_service.get_episode(episode_id)
    story = (episode.get("production") or {}).get("story") or (episode.get("script") or {}).get("story")
    if not story:
        raise ServiceError("Generate a story first, or provide a story in the episode memory.")
    prompt = f"""Turn this children's story into a production script.
Story:
{json.dumps(story, ensure_ascii=False)}

Additional instructions: {instructions or 'Keep it warm, clear, and easy for young children to follow.'}

Return ONLY valid JSON:
{{
  "title": "string",
  "scenes": [
    {{
      "number": 1,
      "title": "string",
      "summary": "string",
      "action": "string",
      "camera": "string",
      "duration_seconds": 5,
      "characters": ["name"],
      "dialogue": [{{"speaker": "name or Narrator", "text": "string", "emotion": "neutral/happy/sad/scared/excited/calm"}}]
    }}
  ]
}}"""
    script = await generate_json(prompt)
    if not isinstance(script, dict) or not isinstance(script.get("scenes"), list):
        raise ServiceError("The script generator returned an invalid structure.")
    _save_episode_memory(episode_id, production={"script": script}, script=script)
    log(actor, "generate_script", "episode", episode_id, {"scenes": len(script.get("scenes", []))})
    return {"episode_id": episode_id, "script": script}


async def revise_script(episode_id: str, instructions: str, actor: str = "user") -> dict[str, Any]:
    episode = episode_service.get_episode(episode_id)
    script = episode.get("script") or {}
    if not script:
        raise ServiceError("There is no script to revise.")
    prompt = f"""Revise this children's animation script:
{json.dumps(script, ensure_ascii=False)}

Revision instructions: {instructions}

Return ONLY the complete revised script JSON with the same structure."""
    revised = await generate_json(prompt)
    if not isinstance(revised, dict) or not isinstance(revised.get("scenes"), list):
        raise ServiceError("The revised script returned an invalid structure.")
    _save_episode_memory(episode_id, production={"script": revised}, script=revised)
    log(actor, "revise_script", "episode", episode_id)
    return {"episode_id": episode_id, "script": revised}


def approve_script(episode_id: str, actor: str = "user") -> dict[str, Any]:
    return approve_script_record(episode_id, actor=actor)
