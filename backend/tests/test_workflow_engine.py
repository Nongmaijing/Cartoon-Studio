from __future__ import annotations

import pytest

from app.orchestration import workflow_engine as wf


def test_legal_forward_transitions():
    assert wf.can_transition(wf.DRAFT, wf.PLANNING)
    assert wf.can_transition(wf.PLANNING, wf.SCENE_GENERATION)
    assert wf.can_transition(wf.SCENE_GENERATION, wf.SCENE_REVIEW)
    assert wf.can_transition(wf.SCENE_REVIEW, wf.ANIMATION)
    assert wf.can_transition(wf.FINAL_EDITING, wf.COMPLETED)


def test_illegal_transitions():
    assert not wf.can_transition(wf.COMPLETED, wf.SCENE_GENERATION)
    assert not wf.can_transition(wf.CANCELLED, wf.PLANNING)
    assert not wf.can_transition(wf.DRAFT, wf.COMPLETED)
    with pytest.raises(wf.WorkflowError):
        wf.assert_transition(wf.DRAFT, wf.COMPLETED)


def test_pause_resume_paths():
    assert wf.can_transition(wf.SCENE_GENERATION, wf.PAUSED)
    assert wf.can_transition(wf.PAUSED, wf.SCENE_GENERATION)
    assert wf.can_transition(wf.PAUSED, wf.CANCELLED)


def test_next_stage():
    assert wf.next_state(wf.PLANNING) == wf.SCRIPT_GENERATION
    assert wf.next_state(wf.FINAL_REVIEW) == wf.COMPLETED
    assert wf.next_state(wf.COMPLETED) is None
