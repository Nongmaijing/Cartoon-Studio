from __future__ import annotations

from app.providers.registry import ProviderRegistry


def test_registry_has_expected_providers():
    registry = ProviderRegistry()
    infos = registry.list_infos()
    keys = {(info.type, info.name) for info in infos}
    assert ("image", "comfyui") in keys
    assert ("video", "comfyui") in keys
    assert ("audio", "kokoro") in keys
    assert ("editing", "ffmpeg") in keys
    assert ("image", "openai") in keys


def test_openai_image_is_opt_in(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ALLOW_CLOUD_GENERATION", raising=False)
    registry = ProviderRegistry()
    openai = next(info for info in registry.list_infos() if info.type == "image" and info.name == "openai")
    assert openai.available is False
    assert "ALLOW_CLOUD_GENERATION" in openai.notes


def test_ffmpeg_and_audio_available():
    registry = ProviderRegistry()
    infos = {info.name: info for info in registry.list_infos() if info.type in ("audio", "editing")}
    assert infos["kokoro"].available is True
    assert infos["ffmpeg"].available is True
