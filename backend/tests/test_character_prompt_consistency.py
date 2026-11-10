from app.services.creative import character_negative_prompt, character_prompt


LEO = {
    "name": "Leo",
    "description": "Draft character profile: human boy, age 4. Sweet, sensitive and imaginative.",
    "appearance": "Four-year-old human boy with short black side-parted hair and warm brown eyes.",
    "clothing": "Mustard-yellow top, teal-blue short overalls with a small star patch, white sneakers.",
    "style": "Premium modern 2D Western children's television animation.",
}

PIP = {
    "name": "Pip",
    "description": "Draft character profile: talking rabbit, cheerful and affectionate.",
    "appearance": "Cute rabbit with warm light-brown fur and long expressive ears.",
    "clothing": "Orange neckerchief.",
    "style": "Premium modern 2D Western children's television animation.",
}


def test_human_reference_prompts_use_one_explicit_camera_view():
    expected = {
        "front": "body facing directly toward the camera",
        "three-quarter": "approximately 45 degrees",
        "side profile": "exactly 90 degrees",
        "back": "body facing directly away from the camera",
    }

    for label, camera_instruction in expected.items():
        prompt = character_prompt(LEO, "reference", label)
        assert camera_instruction in prompt
        assert "single full-body character" in prompt
        assert "full-length wide shot" in prompt
        assert "both feet fully visible" in prompt
        assert "not a portrait" in prompt
        assert "not a headshot" in prompt
        assert "not a waist-up crop" in prompt
        assert "cartoon animal character" not in prompt
        assert "view view" not in prompt
        assert prompt.count("one camera angle only") == 1
        assert "Mustard-yellow top" in prompt
        assert "star patch" in prompt

    front_prompt = character_prompt(LEO, "reference", "front")
    assert "both arms and legs clearly visible" in front_prompt
    assert "forelimbs and hindlimbs where applicable" in front_prompt
    assert ".," not in front_prompt

    side_prompt = character_prompt(LEO, "reference", "side profile")
    assert "three-quarter" not in side_prompt
    assert "approximately 45 degrees" not in side_prompt

    back_prompt = character_prompt(LEO, "reference", "back view")
    assert "face completely hidden" in back_prompt
    assert "no facial features visible" in back_prompt
    assert "no front-facing eyes" in back_prompt


def test_view_aliases_are_normalised_without_duplicate_wording():
    for label in ("front view", "front", "FRONT"):
        prompt = character_prompt(LEO, "reference", label)
        assert prompt.count("front view") == 1
        assert "view view" not in prompt

    for label in ("three-quarter", "three_quarter", "3/4", "3 4"):
        prompt = character_prompt(LEO, "reference", label)
        assert "approximately 45 degrees" in prompt
        assert "view view" not in prompt

    for label in ("side", "profile", "side profile view"):
        prompt = character_prompt(LEO, "reference", label)
        assert "exactly 90 degrees" in prompt
        assert "view view" not in prompt


def test_animal_reference_keeps_species_from_saved_identity():
    prompt = character_prompt(PIP, "reference", "front")
    assert "talking rabbit" in prompt.lower()
    assert "long expressive ears" in prompt
    assert "Orange neckerchief" in prompt
    assert "cartoon animal character" not in prompt
    assert "forelimbs and hindlimbs where applicable" in prompt
    assert "human" not in prompt.lower()


def test_turnaround_negative_prompt_blocks_collages_and_wrong_views():
    common_terms = (
        "multiple views",
        "contact sheet",
        "collage",
        "split panel",
        "duplicate character",
        "close-up",
        "missing feet",
        "inconsistent anatomy",
        "unrequested clothing changes",
        "unrequested accessories",
        "incorrect viewing angle",
        "anime",
    )
    for label in ("front", "three-quarter", "side profile", "back"):
        negative = character_negative_prompt("reference", label)
        for term in common_terms:
            assert term in negative

    back_negative = character_negative_prompt("reference", "back")
    assert "face visible" in back_negative
    assert "front-facing eyes" in back_negative
    assert "front-facing pose" in back_negative
    assert "looking at camera" in back_negative
    assert "front-facing" in back_negative


def test_non_reference_character_prompts_keep_default_negative_prompt():
    from app.services.creative import NEGATIVE_DEFAULT

    assert character_negative_prompt("expression", "happy") == NEGATIVE_DEFAULT
    assert character_negative_prompt("pose", "walking") == NEGATIVE_DEFAULT
