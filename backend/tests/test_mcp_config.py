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


def _tool_names(server) -> set[str]:
    manager = getattr(server, "_tool_manager")
    return {tool.name for tool in manager.list_tools()}


def test_profiles_separate_studio_and_opencode_tools(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_MODE", "bearer")
    studio = _tool_names(create_mcp_server("studio"))
    opencode = _tool_names(create_mcp_server("opencode"))
    combined = _tool_names(create_mcp_server("all"))
    assert len(studio) == 56
    assert opencode == {
        "opencode_ask",
        "opencode_task",
        "opencode_sessions",
        "opencode_permission",
    }
    assert studio.isdisjoint(opencode)
    assert combined == studio | opencode


def test_unknown_profile_is_rejected(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_MODE", "bearer")
    with pytest.raises(RuntimeError, match="MCP_PROFILE"):
        create_mcp_server("everything")
