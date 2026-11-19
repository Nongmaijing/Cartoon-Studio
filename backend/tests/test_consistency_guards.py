from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.db import execute, now
from app.services import character_service, consistency_service, project_service
from app.services.media import link_asset


def _asset(project_id: str, *, kind: str = "image") -> str:
    asset_id = uuid.uuid4().hex[:12]
    execute(
        """INSERT INTO assets (id, project_id, kind, filename, rel_path, mime, meta_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, '{}', ?)""",
        (
            asset_id,
            project_id,
            kind,
            f"{asset_id}.png",
            f"{project_id}/test/{asset_id}.png",
            "image/png" if kind == "image" else "application/octet-stream",
            now(),
        ),
    )
    return asset_id


def _character_with_canonical(project_id: str) -> tuple[dict, str]:
    character = character_service.create_character(project_id, name="Consistency Character")
    canonical = _asset(project_id)
    link_asset("character", character["id"], canonical, role="reference", label="front")
    character_service.set_canonical(character["id"], canonical, actor="test")
    return character, canonical


def _fake_files(monkeypatch):
    def fake_asset_file(asset_id: str):
        return Path(f"{asset_id}.png"), {"id": asset_id, "filename": f"{asset_id}.png"}

    monkeypatch.setattr(consistency_service, "asset_file", fake_asset_file)


@pytest.mark.asyncio
async def test_identity_check_requires_canonical_reference():
    project = project_service.create_project("Consistency A")
    character = character_service.create_character(project["id"], name="No Canonical")
    candidate = _asset(project["id"])
    with pytest.raises(ValueError, match="canonical reference"):
        await consistency_service.check_identity(character["id"], candidate)


@pytest.mark.asyncio
async def test_identity_check_rejects_cross_project_candidate(monkeypatch):
    project = project_service.create_project("Consistency B")
    other = project_service.create_project("Consistency B2")
    character, _ = _character_with_canonical(project["id"])
    candidate = _asset(other["id"])
    _fake_files(monkeypatch)
    with pytest.raises(ValueError, match="different project"):
        await consistency_service.check_identity(character["id"], candidate)


@pytest.mark.asyncio
async def test_identity_check_rejects_non_image_candidate(monkeypatch):
    project = project_service.create_project("Consistency C")
    character, _ = _character_with_canonical(project["id"])
    candidate = _asset(project["id"], kind="audio")
    _fake_files(monkeypatch)
    with pytest.raises(ValueError, match="must be an image"):
        await consistency_service.check_identity(character["id"], candidate)


@pytest.mark.asyncio
async def test_identity_check_returns_advisory_structured_verdict(monkeypatch):
    project = project_service.create_project("Consistency D")
    character, canonical = _character_with_canonical(project["id"])
    candidate = _asset(project["id"])
    _fake_files(monkeypatch)
    captured = {}

    async def fake_compare(paths, prompt, model=None):
        captured["paths"] = paths
        captured["prompt"] = prompt
        return {
            "same_character": True,
            "confidence": 0.91,
            "wardrobe_match": True,
            "differences": [],
            "summary": "Same design.",
            "model": "test-vlm",
            "provider": "test",
        }

    monkeypatch.setattr(consistency_service.llm_provider, "vision_compare", fake_compare)
    result = await consistency_service.check_identity(character["id"], candidate)
    assert captured["paths"] == [f"{canonical}.png", f"{candidate}.png"]
    assert result["same_character"] is True
    assert result["canonical_asset_id"] == canonical
    assert result["candidate_asset_id"] == candidate
    assert result["human_review_required"] is True
