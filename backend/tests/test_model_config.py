from __future__ import annotations

from pathlib import Path

import pytest

from app.config import default_config
from app.services import model_config_service
from app.workflows.adapter import apply_lora, apply_vae


def test_detect_architecture_from_filename(tmp_path):
    sdxl = tmp_path / "DreamShaperXL.safetensors"
    sdxl.write_bytes(b"")
    assert model_config_service.detect_architecture(sdxl, sdxl.name, "checkpoints")["architecture"] == "sdxl"
    sd15 = tmp_path / "DreamShaper_8_pruned.safetensors"
    sd15.write_bytes(b"")
    assert model_config_service.detect_architecture(sd15, sd15.name, "checkpoints")["architecture"] == "sd15"


def test_resolve_model_falls_back_to_sd15_when_sdxl_missing():
    config = default_config()
    resolved = model_config_service.resolve_image_model(config, purpose="character")
    assert resolved["architecture"] == "sd15"
    assert "SDXL" in (resolved["fallback_reason"] or "")
    assert resolved["checkpoint"] == "DreamShaper_8_pruned.safetensors"


def test_explicit_sdxl_without_checkpoint_raises():
    config = default_config()
    with pytest.raises(ValueError, match="No SDXL checkpoint"):
        model_config_service.resolve_image_model(config, architecture="sdxl", purpose="character", explicit=True)


def test_validate_dimensions_rejects_oversized_sdxl():
    model = {"architecture": "sdxl", "max_pixels": 1_250_000}
    model_config_service.validate_dimensions(model, 1024, 1024)
    with pytest.raises(ValueError, match="safe budget"):
        model_config_service.validate_dimensions(model, 1536, 1536)


def test_recommendations_have_license_and_source():
    for item in model_config_service.RECOMMENDATIONS:
        assert item["source"]
        assert item["license"]
        assert item["download_size"]
        assert item["vram"]
        assert item["cartoon_suitability"]


def test_apply_lora_and_vae_rewire_graph():
    api = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "base.safetensors"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "x", "clip": ["4", 1]}},
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["6", 0],
                "latent_image": ["5", 0],
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
    }
    api, lora_applied = apply_lora(api, {"lora_name": "style.safetensors", "lora_strength": 0.7})
    assert lora_applied is True
    lora_nodes = [node for node in api.values() if node["class_type"] == "LoraLoader"]
    assert len(lora_nodes) == 1
    lora_id = next(node_id for node_id, node in api.items() if node["class_type"] == "LoraLoader")
    assert api["6"]["inputs"]["clip"] == [lora_id, 1]
    assert api["3"]["inputs"]["model"] == [lora_id, 0]

    api, vae_applied = apply_vae(api, {"vae": "sdxl-vae.safetensors"})
    assert vae_applied is True
    vae_id = next(node_id for node_id, node in api.items() if node["class_type"] == "VAELoader")
    assert api["8"]["inputs"]["vae"] == [vae_id, 0]
