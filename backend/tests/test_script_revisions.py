from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import query, query_one
from app.routers import episodes as episodes_router
from app.services import (
    approval_service,
    episode_service,
    project_service,
    script_revision_service,
)
from app.services.errors import ServiceError

V3_PATH = Path(__file__).resolve().parent / "fixtures" / "S01E01_SCRIPT_V3.json"


def _v3() -> dict:
    return json.loads(V3_PATH.read_text(encoding="utf-8"))


def _episode() -> dict:
    project = project_service.create_project("Script Revision Test")
    return episode_service.create_episode(project["id"], "Script Revision Episode")


def test_v3_validates_and_creates_revision():
    episode = _episode()
    script = _v3()
    validated = script_revision_service.validate_script_document(script)
    assert validated["format"] == "story_scenes"
    assert validated["scene_count"] == 4
    assert validated["dialogue_lines"] == 69
    assert len(validated["sha256"]) == 64

    result = script_revision_service.create_revision(
        episode["id"], script, notes="valid v3 revision", actor="test"
    )
    assert result["revision_number"] == 1
    assert result["sha256"] == validated["sha256"]
    assert result["script_approved"] is False
    assert result["approval_reset"] is True

    row = query_one("SELECT * FROM episodes WHERE id = ?", (episode["id"],))
    script_json = json.loads(row["script_json"])
    production = json.loads(row["production_json"])
    assert script_json["story"]["scenes"][0]["title"] == "The Old Oak Gathering"
    assert production["script_approved"] is False
    assert production["script_revision_id"] == result["revision_id"]
    assert production["script_revision_number"] == 1
    assert production["storyboard_stale"] is True
    assert row["approved_at"] is None
    assert row["approved_by"] is None

    state = script_revision_service.get_state(episode["id"])
    assert state["has_script"] is True
    assert state["latest_revision_number"] == 1
    assert state["current_sha256"] == result["sha256"]
    assert state["script_approved"] is False


@pytest.mark.parametrize(
    "bad_script",
    [
        {},
        {"story": {"scenes": []}},
        {"story": {"scenes": [{"title": "", "characters": [], "dialogue": []}]}},
        {
            "story": {
                "scenes": [
                    {
                        "title": "Scene",
                        "characters": [],
                        "dialogue": [{"speaker": "Toby", "text": ""}],
                    }
                ]
            }
        },
        {"scenes": [{"title": "Scene", "characters": "Toby", "dialogue": []}]},
    ],
)
def test_invalid_payload_is_rejected_without_writing(bad_script):
    episode = _episode()
    with pytest.raises(ServiceError) as exc:
        script_revision_service.create_revision(episode["id"], bad_script, actor="test")
    assert exc.value.status_code == 400
    assert query("SELECT * FROM script_revisions WHERE episode_id = ?", (episode["id"],)) == []


def test_revision_history_and_hash_conflict():
    episode = _episode()
    rev1 = script_revision_service.create_revision(episode["id"], _v3(), actor="test")

    modified = copy.deepcopy(_v3())
    modified["story"]["title"] = "Pilot: The Little Seed - Revision 2"
    rev2 = script_revision_service.create_revision(
        episode["id"],
        modified,
        base_revision_id=rev1["revision_id"],
        expected_current_sha256=rev1["sha256"],
        notes="second revision",
        actor="test",
    )
    assert rev2["revision_number"] == 2

    revisions = script_revision_service.list_revisions(episode["id"], include_script=True)
    assert [item["revision_number"] for item in revisions] == [2, 1]
    assert revisions[0]["is_current"] is True
    assert revisions[1]["is_current"] is False
    assert revisions[0]["script"]["story"]["title"].endswith("Revision 2")
    assert revisions[1]["script"]["story"]["title"] == "Pilot: The Little Seed"

    one = script_revision_service.get_revision(episode["id"], rev1["revision_id"])
    assert one["revision_number"] == 1
    assert one["script"]["story"]["scenes"][0]["title"] == "The Old Oak Gathering"

    with pytest.raises(ServiceError) as exc:
        script_revision_service.create_revision(
            episode["id"],
            modified,
            expected_current_sha256="0" * 64,
            actor="test",
        )
    assert exc.value.status_code == 409
    assert exc.value.code == "script_hash_conflict"
    assert len(query("SELECT * FROM script_revisions WHERE episode_id = ?", (episode["id"],))) == 2


def test_script_change_resets_approval():
    episode = _episode()
    rev1 = script_revision_service.create_revision(episode["id"], _v3(), actor="test")
    approval_service.approve_script(episode["id"], actor="test")

    approved = query_one("SELECT * FROM episodes WHERE id = ?", (episode["id"],))
    assert json.loads(approved["production_json"])["script_approved"] is True
    assert approved["approved_at"] is not None

    modified = copy.deepcopy(_v3())
    modified["story"]["moral"] = "A revised moral for testing."
    rev2 = script_revision_service.create_revision(
        episode["id"],
        modified,
        base_revision_id=rev1["revision_id"],
        expected_current_sha256=rev1["sha256"],
        actor="test",
    )

    after = query_one("SELECT * FROM episodes WHERE id = ?", (episode["id"],))
    production = json.loads(after["production_json"])
    assert rev2["approval_reset"] is True
    assert production["script_approved"] is False
    assert production["script_approval_reset_at"]
    assert after["approved_at"] is None
    assert after["approved_by"] is None


def test_supported_api_route_valid_and_invalid():
    episode = _episode()
    app = FastAPI()
    app.include_router(episodes_router.router)
    client = TestClient(app)

    state = client.get(f"/api/episodes/{episode['id']}/script-revisions/state")
    assert state.status_code == 200
    assert state.json()["latest_revision_number"] == 0

    created = client.post(
        f"/api/episodes/{episode['id']}/script-revisions",
        json={"script": _v3(), "notes": "api revision"},
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["revision_number"] == 1
    assert payload["script_approved"] is False

    listing = client.get(f"/api/episodes/{episode['id']}/script-revisions")
    assert listing.status_code == 200
    assert len(listing.json()["revisions"]) == 1

    revision = client.get(
        f"/api/episodes/{episode['id']}/script-revisions/{payload['revision_id']}"
    )
    assert revision.status_code == 200
    assert revision.json()["script"]["story"]["scenes"][0]["title"] == "The Old Oak Gathering"

    invalid = client.post(
        f"/api/episodes/{episode['id']}/script-revisions",
        json={"script": {"story": {"scenes": []}}},
    )
    assert invalid.status_code == 400
