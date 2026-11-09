from __future__ import annotations

import pytest

from app.ai.tool_registry import ToolContext, tool_registry
from app.services import character_service, episode_service, project_service


@pytest.mark.asyncio
async def test_unknown_tool():
    result = await tool_registry.execute("does_not_exist", {}, ToolContext(actor="user"))
    assert result["ok"] is False
    assert result["code"] == "unknown_tool"


@pytest.mark.asyncio
async def test_argument_validation():
    result = await tool_registry.execute("list_projects", {"unexpected": True}, ToolContext(actor="user"))
    assert result["ok"] is False
    assert result["code"] == "validation_error"


@pytest.mark.asyncio
async def test_create_project_and_shared_read():
    context = ToolContext(actor="user")
    result = await tool_registry.execute("create_project", {"name": "Tool Project"}, context)
    assert result["ok"] is True
    project_id = result["project"]["id"]
    assert project_service.get_project(project_id)["name"] == "Tool Project"
    listing = await tool_registry.execute("list_projects", {}, context)
    assert any(project["id"] == project_id for project in listing["projects"])


@pytest.mark.asyncio
async def test_idempotent_create_project():
    context = ToolContext(actor="user")
    first = await tool_registry.execute(
        "create_project",
        {"name": "Idempotent Project"},
        context,
        idempotency_key="idem-create-1",
    )
    second = await tool_registry.execute(
        "create_project",
        {"name": "Idempotent Project"},
        context,
        idempotency_key="idem-create-1",
    )
    assert first["ok"] and second["ok"]
    assert second.get("idempotent_replay") is True
    matches = [project for project in project_service.list_projects(True) if project["name"] == "Idempotent Project"]
    assert len(matches) == 1


@pytest.mark.asyncio
async def test_confirmation_gate():
    context = ToolContext(actor="user")
    project = project_service.create_project("Confirmation Project")
    episode = episode_service.create_episode(project["id"], "Confirmation Episode")
    result = await tool_registry.execute(
        "start_production",
        {"project_id": project["id"], "episode_id": episode["id"]},
        context,
    )
    assert result["ok"] is False
    assert result["confirmation_required"] is True


@pytest.mark.asyncio
async def test_character_created_via_tool_is_visible_to_service():
    context = ToolContext(actor="user")
    project = project_service.create_project("Character Tool Project")
    result = await tool_registry.execute(
        "create_character",
        {"project_id": project["id"], "name": "Tool Fox", "description": "a tool-created fox"},
        context,
    )
    assert result["ok"] is True
    character = character_service.get_character(result["character"]["id"])
    assert character["name"] == "Tool Fox"
    assert character["approval_status"] == "draft"


@pytest.mark.asyncio
async def test_episode_created_via_service_is_visible_to_tool():
    context = ToolContext(actor="user")
    project = project_service.create_project("Episode Tool Project")
    episode = episode_service.create_episode(project["id"], "Service Episode")
    result = await tool_registry.execute("get_episode_details", {"episode_id": episode["id"]}, context)
    assert result["ok"] is True
    assert result["episode"]["name"] == "Service Episode"
