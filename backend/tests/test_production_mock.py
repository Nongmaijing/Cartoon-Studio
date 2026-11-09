from __future__ import annotations

import asyncio

import pytest

from app.orchestration import production_orchestrator
from app.services import dialogue_service, episode_service, production_service, project_service, scene_service


@pytest.mark.asyncio
async def test_mocked_production_scene_task(monkeypatch):
    project = project_service.create_project("Production Test")
    episode = episode_service.create_episode(project["id"], "Production Test Episode")
    scene = scene_service.create_scene(project["id"], name="Test Scene", duration=5.0)

    async def fake_generate_scene_image(scene_id, **kwargs):
        return {"job": {"id": "fake-production-job"}, "mode": "text-to-image", "scene_id": scene_id}

    async def fake_wait_job(run_id, job_id, timeout=3600):
        return {"id": job_id, "status": "completed"}

    monkeypatch.setattr(scene_service, "generate_scene_image", fake_generate_scene_image)
    monkeypatch.setattr(production_orchestrator, "_wait_job", fake_wait_job)
    monkeypatch.setattr(
        dialogue_service,
        "audio_status",
        lambda scene_id: {"scene_id": scene_id, "lines": [], "total": 0, "with_audio": 0, "missing_audio": []},
    )

    run = production_service.start_production(
        project["id"],
        episode["id"],
        plan={"scenes": [{"scene_id": scene["id"]}], "assemble": False},
        actor="test",
        confirm=True,
    )
    run_id = run["run_id"]
    for _ in range(100):
        current = production_service.get_status(run_id)
        if current["status"] in ("completed", "failed", "cancelled"):
            break
        await asyncio.sleep(0.05)
    assert current["status"] == "completed"
    assert len(current["tasks"]) == 1
    assert current["tasks"][0]["stage"] == "SCENE_IMAGE"
    assert current["tasks"][0]["status"] == "completed"
    assert current["progress"] == 100.0
