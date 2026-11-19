from __future__ import annotations

import pytest

from app.services import mcp_tunnel_service
from app.services.errors import ConfirmationRequired


def test_parse_tunnel_url():
    text = "2026-11-09T12:00:00Z INF |  https://calm-river-1234.trycloudflare.com  |"
    assert mcp_tunnel_service.parse_tunnel_url(text) == "https://calm-river-1234.trycloudflare.com"


def test_parse_tunnel_url_returns_none_for_unrelated_text():
    assert mcp_tunnel_service.parse_tunnel_url("no url here") is None
    assert mcp_tunnel_service.parse_tunnel_url("https://example.com") is None


def test_normalize_ttl_minutes():
    assert mcp_tunnel_service.normalize_ttl_minutes(None) == 30
    assert mcp_tunnel_service.normalize_ttl_minutes(0) == 30
    assert mcp_tunnel_service.normalize_ttl_minutes(-5) == 30
    assert mcp_tunnel_service.normalize_ttl_minutes(1) == 5
    assert mcp_tunnel_service.normalize_ttl_minutes(60) == 60
    assert mcp_tunnel_service.normalize_ttl_minutes(9999) == 480


@pytest.mark.asyncio
async def test_start_requires_confirmation():
    with pytest.raises(ConfirmationRequired):
        await mcp_tunnel_service.start_tunnel(confirm=False)


@pytest.mark.asyncio
async def test_status_shape_when_inactive():
    status = await mcp_tunnel_service.get_status()
    assert status["active"] is False
    assert status["connector_url"] is None
    assert "cloudflared_available" in status
    assert "public_reachable" in status
    assert "warning" in status
    assert status["ttl_minutes"] >= 5
