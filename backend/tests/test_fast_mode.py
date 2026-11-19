from __future__ import annotations

import pytest

import app.config as config_module
from app.config import load_config
from app.services import model_config_service
from app.services.generation import apply_fast_mode


def _fast_config(enabled: bool = True) -> dict:
    config = load_config()
    fast = dict((config.get("generation") or {}).get("fast_mode") or {})
    fast.update({"enabled": enabled, "lora": "sdxl_lightning_8step_lora.safetensors", "steps": 8})
    config.setdefault("generation", {})["fast_mode"] = fast
    return config


def test_fast_mode_rewrites_sdxl_sampling():
    params = {"steps": 28, "cfg": 6.0, "sampler": "dpmpp_2m", "scheduler": "karras"}
    result = apply_fast_mode(params, {"architecture": "sdxl"}, _fast_config())
    assert result["steps"] == 8
    assert result["cfg"] == 1.0
    assert result["sampler"] == "euler"
    assert result["scheduler"] == "sgm_uniform"
    assert result["lora_name"] == "sdxl_lightning_8step_lora.safetensors"
    assert result["fast_mode"] is True


def test_fast_mode_skips_sd15_and_existing_lora():
    sd15 = apply_fast_mode({"steps": 20}, {"architecture": "sd15"}, _fast_config())
    assert sd15["steps"] == 20 and "lora_name" not in sd15

    character_lora = apply_fast_mode(
        {"steps": 28, "lora_name": "leo_character.safetensors"},
        {"architecture": "sdxl"},
        _fast_config(),
    )
    assert character_lora["steps"] == 28
    assert character_lora["lora_name"] == "leo_character.safetensors"


def test_fast_mode_disabled_is_a_noop():
    params = {"steps": 28, "cfg": 6.0}
    result = apply_fast_mode(params, {"architecture": "sdxl"}, _fast_config(enabled=False))
    assert result == {"steps": 28, "cfg": 6.0}


def test_save_fast_mode_refuses_missing_lora(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "CONFIG_PATH", tmp_path / "config.json")
    with pytest.raises(ValueError):
        model_config_service.save_fast_mode({"enabled": True, "steps": 8})


def test_save_fast_mode_persists_lightning_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "CONFIG_PATH", tmp_path / "config.json")
    status = model_config_service.save_fast_mode({"enabled": False, "steps": 4})
    assert status["enabled"] is False
    assert status["steps"] == 4
    assert status["lora"] == "sdxl_lightning_4step_lora.safetensors"
    assert status["cfg"] == 1.0
    stored = config_module.load_config()["generation"]["fast_mode"]
    assert stored["steps"] == 4 and stored["sampler"] == "euler"
