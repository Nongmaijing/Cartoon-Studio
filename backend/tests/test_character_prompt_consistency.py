from app.services.creative import character_negative_prompt, character_prompt


LEO = {
    "name": "Leo",
    "description": "Draft character profile: human boy, age 4. Sweet, sensitive and imaginative.",
    "appearance": "Four-year-old human boy with short black side-parted hair and warm brown eyes.",
    "clothing": "Mustard-yellow top, teal-blue short overalls with a small star patch, white sneakers.",
    "style": "Premium modern 2D Western children's television animation.",
}

# Live profile after the 2026-11-11 creative-direction update: backpack removed.
LEO_NO_BACKPACK = {
    "name": "Leo",
    "description": (
        "Draft character profile: human boy, age 4. Sweet, sensitive and imaginative. "
        "No backpack or back-mounted accessory; keep his silhouette clean and unobstructed."
    ),
    "appearance": (
        "Four-year-old human boy with short black side-parted hair and warm brown eyes. "
        "No backpack, straps, shoulder bag or other back-mounted accessory."
    ),
    "clothing": (
        "Mustard-yellow top, teal-blue short overalls with a small star patch, white sneakers. "
        "No backpack. The small star patch is his primary visual signature."
    ),
    "style": "Premium modern 2D Western children's television animation.",
}

BACKPACK_EXCLUSION = "backpack, back pack, rucksack, satchel"
BAG_EXCLUSION = "shoulder bag, crossbody bag, handbag, messenger bag"
STRAP_EXCLUSION = "backpack straps, bag straps, sternum strap, dangling strap ends"
BACK_ACCESSORY_EXCLUSION = "back-mounted accessory, backpack harness, cape, wings"

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
        if label != "back":
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


def test_framing_and_wardrobe_survive_clip_truncation():
    prompt = character_prompt(LEO, "reference", "front")
    head = " ".join(prompt.split()[:77]).lower()
    assert "front view" in head
    assert "single full-body character" in head
    assert "both feet fully visible" in head
    assert "mustard-yellow top" in head
    assert "portrait" in head

    negative = character_negative_prompt("reference", "front")
    neg_head = " ".join(negative.split()[:77]).lower()
    assert "multiple views" in neg_head
    assert "duplicate character" in neg_head
    assert "headshot" in neg_head
    assert "cropped feet" in neg_head


def test_back_view_drops_face_and_eye_language():
    front = character_prompt(LEO, "reference", "front")
    back = character_prompt(LEO, "reference", "back")
    assert "warm brown eyes" in front.lower()
    assert "expressive readable faces" in front.lower()
    assert "warm brown eyes" not in back.lower()
    assert "expressive readable faces" not in back.lower()
    assert "expressive face and eyes" not in back.lower()
    assert "short black side-parted hair" in back.lower()
    assert "face completely hidden" in back.lower()


def test_outfit_aware_negative_prompt_blocks_extra_accessories():
    bruno = character_negative_prompt(
        "reference", "front", "Simple little blue waistcoat as signature clothing."
    )
    assert "bow tie, necktie, cravat" in bruno
    assert "shirt, collar" in bruno
    assert "trousers, pants, jeans" in bruno
    assert BACKPACK_EXCLUSION in bruno
    assert BAG_EXCLUSION in bruno
    assert STRAP_EXCLUSION in bruno
    assert BACK_ACCESSORY_EXCLUSION in bruno

    leo = character_negative_prompt(
        "reference",
        "front",
        "Mustard-yellow top, teal-blue short overalls, white sneakers, little yellow backpack.",
    )
    assert "shirt, collar" not in leo
    assert "trousers, pants, jeans" not in leo
    assert BACKPACK_EXCLUSION not in leo


def test_negated_accessory_in_profile_becomes_a_negative_exclusion():
    # "No backpack" must be read as "exclude", not as a requested accessory.
    negative = character_negative_prompt("reference", "front", LEO_NO_BACKPACK["clothing"])
    assert BACKPACK_EXCLUSION in negative
    assert BAG_EXCLUSION in negative
    assert STRAP_EXCLUSION in negative
    assert BACK_ACCESSORY_EXCLUSION in negative

    prompt = character_prompt(LEO_NO_BACKPACK, "reference", "front")
    lowered = prompt.lower()
    assert "backpack" not in lowered
    assert "strap" not in lowered
    assert "shoulder bag" not in lowered
    assert "Mustard-yellow top" in prompt
    assert "star patch" in prompt


def test_back_view_asks_for_a_clean_uninterrupted_back():
    back = character_prompt(LEO_NO_BACKPACK, "reference", "back")
    lowered = back.lower()
    assert "uninterrupted fabric across the back" in lowered
    assert "clean smooth back silhouette" in lowered
    assert "backpack" not in lowered
    assert "strap" not in lowered
    assert "signature" not in lowered
    assert "face completely hidden" in lowered

    side = character_prompt(LEO_NO_BACKPACK, "reference", "side profile")
    assert "clean torso silhouette" in side.lower()
    assert "backpack" not in side.lower()


def test_scene_negative_prompt_carries_cast_accessory_exclusions():
    from app.services.creative import scene_negative_prompt

    negative = scene_negative_prompt([LEO_NO_BACKPACK])
    assert BACKPACK_EXCLUSION in negative
    assert BAG_EXCLUSION in negative
    assert STRAP_EXCLUSION in negative


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


def test_versioned_view_label_keeps_the_camera_instruction():
    prompt = character_prompt(LEO_NO_BACKPACK, "reference", "front-no-backpack-20261111-v2")
    assert "front view" in prompt
    assert "v2 view" not in prompt
    assert "backpack" not in prompt.lower()

    back = character_prompt(LEO_NO_BACKPACK, "reference", "back-no-backpack-20261111-v2")
    assert "rear view" in back
    assert "uninterrupted fabric across the back" in back.lower()


def test_non_reference_character_prompts_keep_default_negative_prompt():
    from app.services.creative import NEGATIVE_DEFAULT

    assert character_negative_prompt("expression", "happy") == NEGATIVE_DEFAULT
    assert character_negative_prompt("pose", "walking") == NEGATIVE_DEFAULT
