from __future__ import annotations

from app.routers.assets import inline_media


def test_images_video_and_audio_are_inline():
    assert inline_media("image/png", False)
    assert inline_media("video/mp4", False)
    assert inline_media("audio/wav", False)
    assert inline_media("application/x-subrip", False)


def test_download_flag_forces_attachment():
    assert not inline_media("image/png", True)
    assert not inline_media("video/mp4", True)


def test_unknown_binary_is_not_inline():
    assert not inline_media("application/octet-stream", False)
    assert not inline_media("application/zip", False)
