from __future__ import annotations

import pytest

from app.services import character_sheet_service, character_service, project_service
from app.services.approval_service import approve_character
from app.services.errors import ServiceError


@pytest.mark.asyncio
async def test_turnaround_without_reference_queues_four_views(monkeypatch):
    project = project_service.create_project("Sheet Test")
    character = character_service.create_character(
        project["id"],
        name="Test Raccoon",
        description="a small raccoon",
        appearance="grey fur, black mask",
        clothing="blue scarf",
    )
    calls: list[dict] = []

    async def fake_submit(**kwargs):
        calls.append(kwargs)
        return {"id": f"job{len(calls)}", "status": "queued", "params": kwargs, "model": {"architecture": "sd15"}}

    async def fake_upload(*args, **kwargs):
        return "fake.png"

    monkeypatch.setattr(character_sheet_service, "submit_image", fake_submit)
    monkeypatch.setattr(character_sheet_service, "upload_start_image", fake_upload)
    result = await character_sheet_service.generate_sheet(character["id"], "turnaround")
    assert len(calls) == 4
    assert result["kind"] == "turnaround"
    assert result["reference_asset_id"] is None
    assert {call["attach"]["label"] for call in calls} == {"front", "three_quarter", "side", "back"}
    assert all(call["purpose"] == "character" for call in calls)
    assert all(call.get("input_image") is None for call in calls)
    assert all("single full-body character" in call["prompt"] for call in calls)
    assert all("cartoon animal character" not in call["prompt"] for call in calls)
    assert all("multiple views" in call["negative_prompt"] for call in calls)
    assert all(call["prompt"].count("one camera angle only") == 1 for call in calls)
    assert "face completely hidden" in calls[3]["prompt"]
    assert "face visible" in calls[3]["negative_prompt"]


@pytest.mark.asyncio
async def test_turnaround_with_reference_uses_one_upload(monkeypatch):
    project = project_service.create_project("Sheet Reference Test")
    character = character_service.create_character(
        project["id"],
        name="Reference Character",
        description="a small human child",
        appearance="short black hair, brown eyes",
        clothing="yellow top and teal overalls",
    )
    calls: list[dict] = []
    uploads: list[str] = []

    async def fake_submit(**kwargs):
        calls.append(kwargs)
        return {"id": f"job{len(calls)}", "status": "queued", "params": kwargs, "model": {"architecture": "sdxl"}}

    async def fake_upload(config, client, asset_id, project_id):
        uploads.append(asset_id)
        return "fake.png"

    monkeypatch.setattr(character_sheet_service, "submit_image", fake_submit)
    monkeypatch.setattr(character_sheet_service, "upload_start_image", fake_upload)
    result = await character_sheet_service.generate_sheet(
        character["id"],
        "turnaround",
        reference_asset_id="ref-asset",
        allow_unapproved_reference=True,
    )
    assert len(uploads) == 1
    assert len(calls) == 4
    assert all(call["input_image"] == "fake.png" for call in calls)
    assert all(call["attach"]["role"] == "reference" for call in calls)
    assert result["reference_approved"] is False
    assert all("single full-body character" in call["prompt"] for call in calls)


@pytest.mark.asyncio
async def test_expression_sheet_requires_reference(monkeypatch):
    project = project_service.create_project("Sheet Test 2")
    character = character_service.create_character(project["id"], name="No Reference")
    with pytest.raises(ServiceError, match="master reference"):
        await character_sheet_service.generate_sheet(character["id"], "expressions")


@pytest.mark.asyncio
async def test_expression_sheet_uses_reference_once(monkeypatch):
    project = project_service.create_project("Sheet Test 3")
    character = character_service.create_character(
        project["id"],
        name="Approved Fox",
        appearance="orange fur",
        clothing="green vest",
    )
    approve_character(character["id"], actor="test")
    calls: list[dict] = []
    uploads: list[str] = []

    async def fake_submit(**kwargs):
        calls.append(kwargs)
        return {"id": f"job{len(calls)}", "status": "queued", "params": kwargs, "model": {"architecture": "sd15"}}

    async def fake_upload(config, client, asset_id, project_id):
        uploads.append(asset_id)
        return "fake.png"

    monkeypatch.setattr(character_sheet_service, "submit_image", fake_submit)
    monkeypatch.setattr(character_sheet_service, "upload_start_image", fake_upload)
    result = await character_sheet_service.generate_sheet(
        character["id"],
        "expressions",
        reference_asset_id="ref-asset",
    )
    assert len(uploads) == 1
    assert len(calls) == 8
    assert result["reference_asset_id"] == "ref-asset"
    assert result["reference_approved"] is True
    assert {call["attach"]["label"] for call in calls} == set(character_sheet_service.EXPRESSIONS)
    assert all(call["purpose"] == "expression" for call in calls)
    assert all(call["input_image"] == "fake.png" for call in calls)
    assert all(call["attach"]["role"] == "expression" for call in calls)


@pytest.mark.asyncio
async def test_unapproved_reference_is_not_used_silently(monkeypatch):
    project = project_service.create_project("Sheet Test 4")
    character = character_service.create_character(project["id"], name="Draft Character")
    with pytest.raises(ServiceError, match="not approved"):
        await character_sheet_service.generate_sheet(
            character["id"],
            "poses",
            reference_asset_id="ref-asset",
        )
