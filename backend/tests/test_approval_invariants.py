from __future__ import annotations

import uuid

import pytest

from app.ai.tool_registry import ToolContext, tool_registry
from app.db import execute, now
from app.services import character_service, episode_service, project_service, scene_service
from app.services.errors import ServiceError
from app.services.media import link_asset


def _asset(project_id: str, *, kind: str = "image", character_id: str | None = None, role: str = "reference") -> str:
    asset_id = uuid.uuid4().hex[:12]
    execute(
        """INSERT INTO assets (id, project_id, kind, filename, rel_path, mime, meta_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, '{}', ?)""",
        (
            asset_id,
            project_id,
            kind,
            f"{asset_id}.png" if kind == "image" else f"{asset_id}.bin",
            f"{project_id}/test/{asset_id}.png" if kind == "image" else f"{project_id}/test/{asset_id}.bin",
            "image/png" if kind == "image" else "application/octet-stream",
            now(),
        ),
    )
    if character_id:
        link_asset("character", character_id, asset_id, role=role, label=role)
    return asset_id


def _character(project_id: str, name: str = "Invariant Character") -> dict:
    return character_service.create_character(project_id, name=name, appearance="rounded shapes", clothing="teal overalls")


def test_character_cannot_be_approved_without_canonical():
    project = project_service.create_project("Approval Invariant A")
    character = _character(project["id"])
    with pytest.raises(ServiceError) as exc:
        character_service.approve_character(character["id"], actor="test")
    assert exc.value.code == "canonical_required"
    assert character_service.get_character(character["id"])["approval_status"] == "draft"


def test_character_can_be_approved_with_linked_canonical():
    project = project_service.create_project("Approval Invariant B")
    character = _character(project["id"])
    asset_id = _asset(project["id"], character_id=character["id"])
    character_service.set_canonical(character["id"], asset_id, actor="test")
    result = character_service.approve_character(character["id"], actor="test")
    assert result["status"] == "approved"
    stored = character_service.get_character(character["id"])
    assert stored["approval_status"] == "approved"
    assert stored["canonical_asset_id"] == asset_id


def test_canonical_setter_rejects_unlinked_asset():
    project = project_service.create_project("Approval Invariant C")
    character = _character(project["id"])
    asset_id = _asset(project["id"])
    with pytest.raises(ServiceError) as exc:
        character_service.set_canonical(character["id"], asset_id, actor="test")
    assert exc.value.code == "canonical_not_linked"


def test_canonical_setter_rejects_cross_project_asset():
    owner_project = project_service.create_project("Approval Invariant D")
    other_project = project_service.create_project("Approval Invariant D2")
    character = _character(owner_project["id"])
    asset_id = _asset(other_project["id"])
    link_asset("character", character["id"], asset_id, role="reference")
    with pytest.raises(ServiceError) as exc:
        character_service.set_canonical(character["id"], asset_id, actor="test")
    assert exc.value.code == "canonical_project_mismatch"


def test_canonical_setter_rejects_non_image():
    project = project_service.create_project("Approval Invariant E")
    character = _character(project["id"])
    asset_id = _asset(project["id"], kind="audio", character_id=character["id"])
    with pytest.raises(ServiceError) as exc:
        character_service.set_canonical(character["id"], asset_id, actor="test")
    assert exc.value.code == "canonical_not_image"


def test_approved_character_cannot_lose_canonical():
    project = project_service.create_project("Approval Invariant F")
    character = _character(project["id"])
    asset_id = _asset(project["id"], character_id=character["id"])
    character_service.set_canonical(character["id"], asset_id, actor="test")
    character_service.approve_character(character["id"], actor="test")
    with pytest.raises(ServiceError) as exc:
        character_service.clear_canonical(character["id"], actor="test")
    assert exc.value.code == "canonical_locked"
    assert character_service.get_character(character["id"])["canonical_asset_id"] == asset_id


def test_generic_update_cannot_bypass_approval_or_canonical():
    project = project_service.create_project("Approval Invariant G")
    character = _character(project["id"])
    character_service.update_character(
        character["id"],
        {"approval_status": "approved", "canonical_asset_id": "forged", "name": "Renamed"},
        actor="test",
    )
    stored = character_service.get_character(character["id"])
    assert stored["name"] == "Renamed"
    assert stored["approval_status"] == "draft"
    assert stored["canonical_asset_id"] is None


@pytest.mark.asyncio
async def test_mcp_character_approval_requires_confirm():
    project = project_service.create_project("Approval MCP A")
    character = _character(project["id"])
    asset_id = _asset(project["id"], character_id=character["id"])
    character_service.set_canonical(character["id"], asset_id, actor="test")
    context = ToolContext(actor="mcp")
    blocked = await tool_registry.execute("approve_character", {"character_id": character["id"]}, context)
    assert blocked["ok"] is False
    assert blocked["confirmation_required"] is True
    assert character_service.get_character(character["id"])["approval_status"] == "draft"
    approved = await tool_registry.execute(
        "approve_character",
        {"character_id": character["id"], "confirm": True},
        context,
    )
    assert approved["ok"] is True
    assert character_service.get_character(character["id"])["approval_status"] == "approved"


@pytest.mark.asyncio
async def test_mcp_character_approval_requires_canonical_even_when_confirmed():
    project = project_service.create_project("Approval MCP D")
    character = _character(project["id"])
    context = ToolContext(actor="mcp")
    result = await tool_registry.execute(
        "approve_character",
        {"character_id": character["id"], "confirm": True},
        context,
    )
    assert result["ok"] is False
    assert "canonical" in result["error"].lower()
    assert character_service.get_character(character["id"])["approval_status"] == "draft"


@pytest.mark.asyncio
async def test_mcp_scene_and_script_approvals_require_confirm():
    project = project_service.create_project("Approval MCP B")
    episode = episode_service.create_episode(project["id"], "Approval Episode")
    scene = scene_service.create_scene(project["id"], name="Approval Scene")
    context = ToolContext(actor="mcp", project_id=project["id"], episode_id=episode["id"])
    scene_blocked = await tool_registry.execute("approve_scene", {"scene_id": scene["id"]}, context)
    script_blocked = await tool_registry.execute("approve_script", {"episode_id": episode["id"]}, context)
    assert scene_blocked["ok"] is False and scene_blocked["confirmation_required"] is True
    assert script_blocked["ok"] is False and script_blocked["confirmation_required"] is True
    assert scene_service.get_scene_details(scene["id"])["approval_status"] == "draft"
    scene_ok = await tool_registry.execute(
        "approve_scene",
        {"scene_id": scene["id"], "confirm": True},
        context,
    )
    script_ok = await tool_registry.execute(
        "approve_script",
        {"episode_id": episode["id"], "confirm": True},
        context,
    )
    assert scene_ok["ok"] is True
    assert script_ok["ok"] is True


@pytest.mark.asyncio
async def test_mcp_canonical_tools_are_available_and_validated():
    project = project_service.create_project("Approval MCP C")
    character = _character(project["id"])
    asset_id = _asset(project["id"], character_id=character["id"])
    context = ToolContext(actor="mcp")
    result = await tool_registry.execute(
        "set_canonical_asset",
        {"character_id": character["id"], "asset_id": asset_id},
        context,
    )
    assert result["ok"] is True
    assert character_service.get_character(character["id"])["canonical_asset_id"] == asset_id
    missing = await tool_registry.execute(
        "set_canonical_asset",
        {"character_id": character["id"], "asset_id": "missing"},
        context,
    )
    assert missing["ok"] is False

def test_editing_an_approved_character_resets_approval():
    project = project_service.create_project("Approval Reset Test")
    character = _character(project["id"])
    asset_id = _asset(project["id"], character_id=character["id"])
    character_service.set_canonical(character["id"], asset_id, actor="test")
    character_service.approve_character(character["id"], actor="test")
    assert character_service.get_character(character["id"])["approval_status"] == "approved"

    character_service.update_character(character["id"], {"clothing": "new overalls"}, actor="test")
    updated = character_service.get_character(character["id"])
    assert updated["approval_status"] == "draft"
    assert updated["approved_at"] is None
