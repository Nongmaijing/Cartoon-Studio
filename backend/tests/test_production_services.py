from __future__ import annotations

import json

import pytest

from app.config import default_config
from app.db import execute, now
from app.services import (
    dialogue_service,
    episode_service,
    lip_sync_service,
    llm_provider,
    production_registry_service,
    project_service,
    resource_manager,
    scene_service,
    script_service,
    shot_plan_service,
)


def test_resource_estimates_cover_6gb_profiles():
    config = default_config()
    image = resource_manager.estimate_job(
        config, "sd15_txt2img", {"width": 512, "height": 512, "steps": 20}
    )
    assert image["resource_class"] == "gpu_image"
    assert image["fits_6gb"] is True
    assert image["estimated_seconds"] > 0
    video = resource_manager.estimate_job(
        config, "wan22_i2v", {"width": 320, "height": 192, "steps": 4, "length": 5}
    )
    assert video["resource_class"] == "gpu_video"
    assert video["estimated_vram_gb"] > 5
    assert video["estimated_seconds"] > 0


def test_llm_json_parser_handles_fenced_and_noisy_output():
    assert llm_provider.parse_json_text('```json\n{"ok": true}\n```') == {"ok": True}
    assert llm_provider.parse_json_text('result: {"value": 2} trailing') == {"value": 2}


def test_viseme_units_include_mouth_groups():
    units = lip_sync_service.text_to_units("Milo says hello")
    visemes = {viseme for _, viseme in units}
    assert "MBP" in visemes
    assert "REST" in visemes or "L" in visemes


def test_registry_recommendations_are_documented():
    for item in production_registry_service.recommendations():
        assert item["source"]
        assert item["license"]
        assert item["vram"]
        assert item["commercial_use"]
        assert item["department"]


def test_story_normalization_and_continuity_warnings():
    story = {
        "scenes": [
            {
                "title": "",
                "characters": ["Milo the Fox", "New Squirrel"],
                "dialogue": [
                    {"speaker": "Milo the Fox", "text": "Hello!"},
                    {"speaker": "Narrator", "text": "The forest hums."},
                    {"speaker": "Owl", "text": "Who?"},
                ],
            }
        ]
    }
    normalized = script_service._normalize_story(story)
    assert normalized["scenes"][0]["title"] == "Scene 1"
    warnings = script_service._continuity_warnings(
        normalized, [{"name": "Milo the Fox"}]
    )
    assert warnings == ["New Squirrel", "Owl"]


@pytest.mark.asyncio
async def test_lip_sync_generation_and_manual_update():
    project = project_service.create_project("Lip Sync Test")
    scene = scene_service.create_scene(project["id"], name="Lip Scene", duration=4)
    line = await dialogue_service.create_line(
        scene["id"],
        character_id=None,
        text="Hello little friends",
        start_ms=0,
    )
    generated = lip_sync_service.generate_for_line(line["id"])
    assert generated["editable"] is True
    assert len(generated["cues"]) > 5
    assert generated["cues"][0]["start_ms"] == 0
    manual = lip_sync_service.update_cues(
        line["id"],
        [{"start_ms": 0, "end_ms": 120, "viseme": "MBP", "text": "H"}],
    )
    assert manual["source"] == "manual"
    assert manual["cues"][0]["viseme"] == "MBP"


@pytest.mark.asyncio
async def test_shot_plan_estimate_and_report():
    project = project_service.create_project("Shot Plan Test")
    scene = scene_service.create_scene(project["id"], name="Opening", duration=12)
    episode = episode_service.create_episode(project["id"], "Shot Plan Episode")
    execute(
        "UPDATE episodes SET storyboard_json = ?, production_json = '{}', updated_at = ? WHERE id = ?",
        (json.dumps([{"scene_id": scene["id"], "number": 1}]), now(), episode["id"]),
    )
    await dialogue_service.create_line(
        scene["id"],
        character_id=None,
        text="Welcome to Little Wonder Village.",
        start_ms=0,
    )
    plan = shot_plan_service.build_shot_plan(episode["id"])
    assert plan["shot_count"] >= 1
    assert plan["estimate"]["total_gpu_seconds"] > 0
    assert all(shot["status"] == "planned" for shot in plan["shots"])
    updated = shot_plan_service.update_shot_status(
        episode["id"], plan["shots"][0]["id"], "approved", "looks good"
    )
    assert updated["shots"][0]["status"] == "approved"
    report = shot_plan_service.production_report(project["id"])
    assert report["counts"]["projects"] >= 1
    assert report["counts"]["scenes"] == 1
    assert report["counts"]["episodes"] == 1
