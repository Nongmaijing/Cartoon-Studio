from __future__ import annotations

import pytest

from app.services import model_download_service


def test_vetted_sources_describe_license_and_hash():
    base = model_download_service.describe("SDXL Base 1.0")
    assert base["available"] is True
    assert base["license"] == "CreativeML Open RAIL++-M"
    assert base["size_bytes"] > 6 * 1024**3
    assert len(base["sha256"]) == 64
    assert base["filename"].endswith(".safetensors")


def test_unvetted_recommendation_is_manual_only():
    lora = model_download_service.describe("Cartoon style SDXL LoRA (choose a model card with clear commercial terms)")
    assert lora["available"] is False
    assert "manually" in lora["reason"].lower()


def test_unknown_recommendation_is_manual_only():
    result = model_download_service.describe("do-not-ship")
    assert result["available"] is False


@pytest.mark.asyncio
async def test_download_requires_explicit_license_confirmation():
    with pytest.raises(ValueError, match="Licence confirmation"):
        await model_download_service.start_download("SDXL Base 1.0", accept_license=False)


@pytest.mark.asyncio
async def test_unknown_download_is_rejected_before_network():
    with pytest.raises(ValueError, match="no vetted direct download"):
        await model_download_service.start_download("make-me-a-model", accept_license=True)


def test_sources_are_whitelisted_checkpoints_only():
    for name, source in model_download_service.SOURCES.items():
        assert source["category"] in ("checkpoints", "loras")
        assert source["url"].startswith("https://")
        assert source["filename"] == source["filename"].split("/")[-1]
        assert len(source["sha256"]) == 64
