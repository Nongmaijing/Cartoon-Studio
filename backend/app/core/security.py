from __future__ import annotations

import asyncio
import hashlib
import secrets
import time
from collections import defaultdict
from typing import Any

from ..db import execute, now, query_one
from .runtime import mcp_settings


class AuthorizationError(RuntimeError):
    pass


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_mcp_token(name: str, scopes: str = "production") -> dict[str, Any]:
    """Create a token and store only its hash. The raw token is returned once."""
    raw = "csm_" + secrets.token_urlsafe(32)
    token_id = secrets.token_hex(8)
    execute(
        """INSERT INTO mcp_tokens (id, name, token_hash, scopes, created_at, revoked)
           VALUES (?, ?, ?, ?, ?, 0)""",
        (token_id, name.strip() or "mcp-client", hash_token(raw), scopes, now()),
    )
    return {"id": token_id, "name": name, "token": raw, "scopes": scopes}


def verify_mcp_token(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    settings = mcp_settings()
    configured = settings.get("bearer_token") or ""
    if configured and secrets.compare_digest(token, configured):
        return {"id": "env", "name": "environment-token", "scopes": "production"}
    row = query_one(
        "SELECT id, name, scopes, revoked FROM mcp_tokens WHERE token_hash = ?",
        (hash_token(token),),
    )
    if not row or row["revoked"]:
        return None
    execute("UPDATE mcp_tokens SET last_used_at = ? WHERE id = ?", (now(), row["id"]))
    return {"id": row["id"], "name": row["name"], "scopes": row["scopes"]}


def require_scope(scope: str, granted: str) -> None:
    granted_set = {item.strip() for item in (granted or "").split(",") if item.strip()}
    if "admin" in granted_set or "production" in granted_set or scope in granted_set:
        return
    raise AuthorizationError(f"Missing scope '{scope}'.")


class RateLimiter:
    """Small in-process limiter for AI/MCP endpoints."""

    def __init__(self) -> None:
        self._events: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check(self, key: str, limit: int, window: float = 60.0) -> None:
        if limit <= 0:
            return
        async with self._lock:
            now_ts = time.time()
            events = [value for value in self._events[key] if now_ts - value < window]
            if len(events) >= limit:
                raise AuthorizationError("Rate limit exceeded. Try again shortly.")
            events.append(now_ts)
            self._events[key] = events


rate_limiter = RateLimiter()
