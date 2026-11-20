from __future__ import annotations

from PIL import Image, ImageDraw

from app.services.creative import character_negative_prompt, character_prompt
from app.services.motion_service import (
    CAMERA_PRESETS,
    _camera,
    cutout_image,
    key_plain_background,
    render_camera_motion,
)


def _sample() -> Image.Image:
    image = Image.new("RGB", (200, 300), (206, 206, 206))
    draw = ImageDraw.Draw(image)
    draw.ellipse((40, 40, 160, 260), fill=(190, 60, 50))
    # A grey patch inside the subject must survive: it is not connected to the border.
    draw.rectangle((85, 120, 115, 170), fill=(206, 206, 206))
    return image


def test_key_removes_border_background_and_keeps_subject():
    cutout = key_plain_background(_sample(), tolerance=24, feather=8, padding=4)
    assert cutout.mode == "RGBA"
    assert cutout.getpixel((2, 2))[3] == 0
    assert cutout.getpixel((cutout.width - 3, 2))[3] == 0

    centre = cutout.getpixel((cutout.width // 2, cutout.height // 2))
    assert centre[3] > 200

    # The interior grey patch is enclosed by the subject, so it stays opaque.
    patch = cutout.getpixel((cutout.width // 2, int(cutout.height * 0.45)))
    assert patch[3] > 200


def test_key_crops_to_the_subject():
    cutout = key_plain_background(_sample(), tolerance=24, feather=8, padding=0)
    assert cutout.width < 200
    assert cutout.height < 300
    assert cutout.height > 150


def test_camera_presets_move_between_start_and_end():
    push = _camera(CAMERA_PRESETS["push_in"], 0.0)
    assert push[0] == 1.0
    push_end = _camera(CAMERA_PRESETS["push_in"], 1.0)
    assert push_end[0] == 1.07

    pan_start = _camera(CAMERA_PRESETS["pan_left"], 0.0)
    pan_end = _camera(CAMERA_PRESETS["pan_left"], 1.0)
    assert pan_start[1] == -0.55
    assert pan_end[1] == 0.55


def test_every_preset_has_a_note_and_valid_range():
    for preset in CAMERA_PRESETS.values():
        assert 1.0 <= preset["zoom_start"] <= 1.2
        assert 1.0 <= preset["zoom_end"] <= 1.2


def test_chroma_green_key_removes_background():
    image = Image.new("RGB", (160, 240), (0, 177, 64))
    draw = ImageDraw.Draw(image)
    draw.ellipse((40, 40, 120, 200), fill=(220, 130, 60))
    cutout = key_plain_background(image, tolerance=40, feather=10, padding=0)
    assert cutout.getpixel((1, 1))[3] == 0
    assert cutout.getpixel((cutout.width // 2, cutout.height // 2))[3] > 200


def test_cutout_image_dispatches_to_chroma_keying():
    cutout, engine = cutout_image(_sample(), engine="chroma", tolerance=24, feather=8, padding=2)
    assert engine == "chroma"
    assert cutout.mode == "RGBA"
    assert cutout.getpixel((0, 0))[3] == 0
    assert cutout.getpixel((cutout.width // 2, cutout.height // 2))[3] > 200


def test_cutout_prompt_requests_a_chroma_backdrop():
    character = {
        "name": "Pip",
        "description": "a small round bird",
        "appearance": "cream feathers, orange beak",
        "clothing": "blue scarf",
        "style": "",
    }
    prompt = character_prompt(character, "cutout", "standing")
    assert "chroma green background" in prompt
    assert "no shadow" in prompt
    assert "studio background" not in prompt

    negative = character_negative_prompt("cutout", "standing", "blue scarf")
    assert "floor shadow" in negative
    assert "green" not in negative


def test_camera_motion_renders_a_clip(tmp_path):
    image = Image.new("RGB", (640, 360), (70, 120, 90))
    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 80, 540, 300), fill=(190, 150, 90))
    source = tmp_path / "plate.png"
    image.save(source)
    output = tmp_path / "clip.mp4"
    meta = render_camera_motion(
        background_path=source,
        output_path=output,
        duration=1.0,
        fps=12,
        width=320,
        height=180,
        camera="push_in",
    )
    assert meta["frames"] == 12
    assert meta["camera"] == "push_in"
    assert output.stat().st_size > 1000


def test_camera_motion_rejects_unknown_preset(tmp_path):
    image = Image.new("RGB", (64, 64), (0, 0, 0))
    source = tmp_path / "plate.png"
    image.save(source)
    try:
        render_camera_motion(
            background_path=source,
            output_path=tmp_path / "x.mp4",
            duration=1.0,
            fps=12,
            width=64,
            height=64,
            camera="orbit",
        )
    except ValueError:
        return
    raise AssertionError("unknown camera preset should fail")
