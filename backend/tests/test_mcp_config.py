from __future__ import annotations

import pytest

from app.mcp.server import _transport_security, create_mcp_server


def test_transport_security_allows_public_tunnel_host():
    settings = _transport_security("https://example.trycloudflare.com", ["extra.example"], ["https://extra.example"])
    assert "example.trycloudflare.com" in settings.allowed_hosts
    assert "extra.example" in settings.allowed_hosts
    assert "https://example.trycloudflare.com" in settings.allowed_origins
    assert "https://extra.example" in settings.allowed_origins
    assert settings.enable_dns_rebinding_protection is True


def test_noauth_mode_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_MODE", "none")
    monkeypatch.delenv("MCP_ALLOW_UNAUTHENTICATED", raising=False)
    with pytest.raises(RuntimeError, match="MCP_ALLOW_UNAUTHENTICATED"):
        create_mcp_server()


def test_unknown_auth_mode_is_rejected(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_MODE", "oauth")
    with pytest.raises(RuntimeError, match="MCP_AUTH_MODE"):
        create_mcp_server()
