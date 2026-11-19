from __future__ import annotations

import uuid

import pytest

from app.db import execute, now
from app.services import character_sheet_service, character_service, project_service
from app.services.approval_service import approve_character
from app.services.errors import ServiceError
from app.services.media import link_asset


def _make_canonical(project_id: str, character_id: str) -> str:
    asset_id = uuid.uuid4().hex[:12]
    execute(
        """INSERT INTO assets (id, project_id, kind, filename, rel_path, mime, meta_json, created_at)
           VALUES (?, ?, 'image', ?, ?, 'image/png', '{}', ?)""",
        (asset_id, project_id, f"{asset_id}.png", f"{project_id}/test/{asset_id}.png", now()),
    )
    link_asset("character", character_id, asset_id, role="reference", label="front")
    character_service.set_canonical(character_id, asset_id, actor="test")
    return asset_id


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
    assert "expressive readable faces" not in calls[3]["prompt"].lower()


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
    by_label = {call["attach"]["label"]: call for call in calls}
    assert by_label["front"]["input_image"] == "fake.png"
    assert by_label["three_quarter"]["input_image"] == "fake.png"
    assert by_label["side"]["input_image"] == "fake.png"
    assert by_label["back"]["input_image"] is None
    assert by_label["front"]["denoise"] is not None
    assert by_label["three_quarter"]["denoise"] >= 0.55
    assert by_label["side"]["denoise"] >= 0.65
    assert by_label["back"]["denoise"] is None
    assert all(call["attach"]["role"] == "reference" for call in calls)
    assert result["reference_approved"] is False
    assert all("single full-body character" in call["prompt"] for call in calls)
    assert "expressive readable faces" not in by_label["back"]["prompt"].lower()


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
    _make_canonical(project["id"], character["id"])
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

@pytest.mark.asyncio
async def test_generate_sheet_can_skip_the_canonical_reference(monkeypatch):
    project = project_service.create_project("No Reference Test")
    character = character_service.create_character(
        project["id"],
        name="Test Boy",
        description="human boy, age 4",
        appearance="short black hair, brown eyes. No backpack, straps or bag.",
        clothing="mustard-yellow top, teal overalls with a small star patch. No backpack.",
    )
    _make_canonical(project["id"], character["id"])

    uploads: list[dict] = []
    calls: list[dict] = []

    async def fake_upload(*args, **kwargs):
        uploads.append(kwargs)
        return "fake.png"

    class FakeProvider:
        async def generate_image(self, **kwargs):
            calls.append(kwargs)
            return {"id": "job1", "status": "queued", "params": kwargs, "model": {"architecture": "sdxl"}}

    monkeypatch.setattr(character_service, "upload_start_image", fake_upload)
    monkeypatch.setattr(character_service.registry, "get", lambda name: FakeProvider())

    result = await character_service.generate_sheet(
        character["id"],
        kind="reference",
        label="front-no-backpack-20261111-v2",
        use_reference=False,
    )

    assert uploads == []
    assert result["mode"] == "text-to-image"
    assert result["reference_asset_id"] is None
    assert calls[0]["input_image"] is None
    assert "front view" in calls[0]["prompt"]
    assert "backpack" not in calls[0]["prompt"].lower()
    assert "backpack" in calls[0]["negative_prompt"].lower()
    assert calls[0]["attach"]["label"] == "front-no-backpack-20261111-v2"
