from __future__ import annotations

from app.services import art_styles
from app.services.creative import character_prompt


def test_default_and_known_presets_resolve():
    ids = [item["id"] for item in art_styles.available_styles()]
    assert art_styles.DEFAULT_STYLE in ids
    assert "western_preschool" in ids

    ghibli = art_styles.resolve_style({"creative": {"art_style": "ghibli_painterly"}})
    assert "painterly" in ghibli["positive"]

    western = art_styles.style_text(
        config={"creative": {"art_style": "western_preschool"}}
    )
    assert western.startswith("premium Western preschool")


def test_unknown_style_falls_back_to_default():
    resolved = art_styles.resolve_style({"creative": {"art_style": "does_not_exist"}})
    assert resolved["id"] == art_styles.DEFAULT_STYLE


def test_custom_style_is_appended():
    text = art_styles.style_text(
        config={"creative": {"art_style": "clean_anime", "custom_style": "soft film grain"}}
    )
    assert text.endswith("soft film grain")


def test_character_prompt_uses_the_configured_style(monkeypatch):
    monkeypatch.setattr(
        "app.services.creative.style_text", lambda back=False: "TEST_ART_DIRECTION"
    )
    prompt = character_prompt(
        {"name": "Pip", "appearance": "small round bird", "style": ""},
        "reference",
        "front",
    )
    assert "TEST_ART_DIRECTION" in prompt


def test_back_view_uses_the_back_style(monkeypatch):
    calls: list[bool] = []

    def fake_style(back: bool = False) -> str:
        calls.append(back)
        return "BACK_STYLE" if back else "FRONT_STYLE"

    monkeypatch.setattr("app.services.creative.style_text", fake_style)
    prompt = character_prompt(
        {"name": "Pip", "appearance": "small round bird", "style": ""},
        "reference",
        "back view",
    )
    assert "BACK_STYLE" in prompt
    assert calls == [True]
