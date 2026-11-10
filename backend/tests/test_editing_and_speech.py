from __future__ import annotations

import pytest

from app.config import default_config
from app.services import editing_service, llm_provider, production_registry_service, speech_service
from app.workflows.registry import load_workflow


def test_srt_is_built_from_segments():
    srt = speech_service.to_srt(
        [
            {"start": 0.0, "end": 1.5, "text": "Hello, Leo."},
            {"start": 1.5, "end": 3.25, "text": "Look at the stars."},
            {"start": 3.3, "end": 3.4, "text": "  "},
        ]
    )
    assert "1\n00:00:00,000 --> 00:00:01,500\nHello, Leo." in srt
    assert "2\n00:00:01,500 --> 00:00:03,250\nLook at the stars." in srt
    assert "\n3\n" not in srt


def test_speech_availability_reports_paths():
    status = speech_service.availability()
    assert set(status) >= {
        "available",
        "package_installed",
        "model_installed",
        "model_path",
        "model_name",
        "device",
        "compute_type",
    }
    assert isinstance(status["model_path"], str)


def test_inpaint_workflow_maps_image_and_mask():
    loaded = load_workflow(default_config(), "sdxl_inpaint")
    roles = loaded["mapping"]["roles"]
    assert roles["input_image"]["class"] == "LoadImage"
    assert roles["mask_image"]["class"] == "LoadImageMask"
    assert roles["denoise"]["class"] == "KSampler"
    classes = {node["class_type"] for node in loaded["api"].values()}
    assert {"VAEEncodeForInpaint", "LoadImageMask", "CheckpointLoaderSimple"} <= classes


def test_inpaint_checkpoint_prefers_configured_name():
    config = default_config()
    object_info = {
        "CheckpointLoaderSimple": {
            "input": {
                "required": {
                    "ckpt_name": [["SDXL_Inpainting_0.1.safetensors", "dreamshaper.safetensors"]]
                }
            }
        }
    }
    assert (
        production_registry_service._inpaint_checkpoint(config, object_info)
        == "SDXL_Inpainting_0.1.safetensors"
    )
    config["models"]["checkpoints"]["sdxl_inpaint"] = "SDXL_Inpainting_0.1.safetensors"
    assert (
        production_registry_service._inpaint_checkpoint(config, object_info)
        == "SDXL_Inpainting_0.1.safetensors"
    )


def test_inpaint_checkpoint_ignores_unrelated_models():
    config = default_config()
    object_info = {
        "CheckpointLoaderSimple": {
            "input": {"required": {"ckpt_name": [["dreamshaper.safetensors"]]}}
        }
    }
    assert production_registry_service._inpaint_checkpoint(config, object_info) == ""


def test_target_size_scales_without_upscaling(tmp_path):
    from PIL import Image

    path = tmp_path / "source.png"
    Image.new("RGB", (2048, 1024), "white").save(path)
    width, height = editing_service._target_size(path, 1250000)
    assert width * height <= 1250000
    assert width % 8 == 0 and height % 8 == 0
    small = tmp_path / "small.png"
    Image.new("RGB", (256, 128), "white").save(small)
    assert editing_service._target_size(small, 1250000) == (256, 128)


@pytest.mark.asyncio
async def test_vision_compare_needs_two_images():
    with pytest.raises(Exception):
        await llm_provider.vision_compare(["only-one.png"], "compare")
