from __future__ import annotations

from app.services.character_service import _ipadapter_weight
from app.services.creative import _short_identity, character_prompt


def test_character_style_replaces_the_global_preset():
    character = {
        "name": "Kokoro",
        "description": "a young girl with short pony tail.",
        "style": "ghibli style",
    }
    prompt = character_prompt(character, "reference", "front")
    assert "ghibli style" in prompt
    assert "premium Western preschool" not in prompt


def test_side_prompt_contains_profile_structure():
    character = {
        "name": "Kokoro",
        "description": "a young girl",
        "appearance": "short black hair",
        "clothing": "white shirt",
    }
    prompt = character_prompt(character, "reference", "side profile")
    assert "90 degrees" in prompt
    assert "one eye and one ear visible" in prompt
    assert "both eyes visible" not in prompt


def test_back_prompt_keeps_the_face_hidden():
    character = {"name": "Kokoro", "description": "a young girl", "appearance": "short black hair"}
    prompt = character_prompt(character, "reference", "back")
    assert "face completely hidden" in prompt
    assert "back of head" in prompt


def test_short_identity_drops_a_dangling_style_tail():
    assert (
        _short_identity("a young girl with short pony tail in ghibli style.")
        == "a young girl with short pony tail"
    )


def test_ipadapter_weight_follows_the_requested_view():
    assert _ipadapter_weight("side profile") == 0.35
    assert _ipadapter_weight("back") == 0.25
    assert _ipadapter_weight("three-quarter") == 0.55
    assert _ipadapter_weight("front") == 0.8
