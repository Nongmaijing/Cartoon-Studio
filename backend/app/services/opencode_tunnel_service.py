from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..config import BASE_DIR
from . import mcp_tunnel_service as base
from .audit_service import log
from .errors import ConfirmationRequired, ConfigurationError, ServiceError

PORT = 8030
PROFILE = "opencode"
STATE_FILE = BASE_DIR / "data" / "opencode_tunnel_state.json"
DEFAULT_TTL_MINUTES = base.DEFAULT_TTL_MINUTES

_state: dict[str, Any] = {
    "active": False,
    "public_url": None,
    "host": None,
    "tunnel_pid": None,
    "mcp_pid": None,
    "started_at": None,
    "expires_at": None,
    "ttl_minutes": DEFAULT_TTL_MINUTES,
    "public_reachable": False,
    "message": "",
}
_lock = asyncio.Lock()
_expiry_task: asyncio.Task | None = None
_tunnel_proc: asyncio.subprocess.Process | None = None
_tunnel_drain_task: asyncio.Task | None = None
_mcp_proc: subprocess.Popen | None = None


def _reset_state() -> None:
    _state.update(
        {
            "active": False,
            "public_url": None,
            "host": None,
            "tunnel_pid": None,
            "mcp_pid": None,
            "started_at": None,
            "expires_at": None,
            "ttl_minutes": DEFAULT_TTL_MINUTES,
            "public_reachable": False,
            "message": "",
        }
    )


def _persist() -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(_state, indent=2), encoding="utf-8")


def _clear_state_file() -> None:
    try:
        STATE_FILE.unlink()
    except FileNotFoundError:
        pass


def _load_persisted() -> dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


async def _ensure_bearer() -> None:
    pid = base._find_port_pid(PORT)
    if pid:
        if not base._cmdline_contains(pid, "run_mcp.py"):
            raise ServiceError(
                f"Port {PORT} is occupied by another process; cannot restore the OpenCode MCP.",
                status_code=409,
                code="port_in_use",
            )
        if await base._probe_auth(PORT) == "bearer":
            return
        base._terminate_pid(pid, "run_mcp.py")
        await base._wait_port_free(PORT)
    global _mcp_proc
    _mcp_proc = base._spawn_mcp(PORT, auth_mode="bearer", profile=PROFILE)
    await base._wait_mcp_health(PORT, "bearer", timeout=25)


async def _hard_cleanup() -> None:
    global _tunnel_proc, _tunnel_drain_task, _mcp_proc
    if _tunnel_drain_task and not _tunnel_drain_task.done():
        _tunnel_drain_task.cancel()
    _tunnel_drain_task = None
    if _tunnel_proc is not None:
        try:
            if _tunnel_proc.returncode is None:
                _tunnel_proc.terminate()
                try:
                    await asyncio.wait_for(_tunnel_proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    _tunnel_proc.kill()
        except ProcessLookupError:
            pass
        _tunnel_proc = None
    if _mcp_proc is not None:
        base._terminate_pid(_mcp_proc.pid, "run_mcp.py")
        _mcp_proc = None
    persisted = _load_persisted()
    base._terminate_pid(persisted.get("tunnel_pid"))
    base._terminate_pid(persisted.get("mcp_pid"), "run_mcp.py")


def _schedule_expiry(seconds: float) -> None:
    global _expiry_task
    if _expiry_task and not _expiry_task.done():
        _expiry_task.cancel()

    async def _expire() -> None:
        try:
            await asyncio.sleep(max(1.0, seconds))
            await stop_tunnel(actor="system", reason="ttl_expired")
        except asyncio.CancelledError:
            return

    _expiry_task = asyncio.create_task(_expire())


async def _status_unlocked() -> dict[str, Any]:
    mcp_pid = _state.get("mcp_pid") or base._find_port_pid(PORT)
    mcp_alive = base._is_alive(mcp_pid)
    tunnel_alive = base._is_alive(_state.get("tunnel_pid"))
    if _state["active"] and not (tunnel_alive and mcp_alive):
        _reset_state()
        _clear_state_file()
    if _state["active"]:
        auth = await base._probe_auth(PORT)
    else:
        auth = await base._probe_auth(PORT) if mcp_alive else None
    remaining = None
    if _state.get("expires_at"):
        remaining = max(0, int(_state["expires_at"] - time.time()))
    return {
        "active": bool(_state["active"]),
        "profile": PROFILE,
        "public_url": _state.get("public_url"),
        "connector_url": f"{_state['public_url']}/mcp" if _state.get("public_url") else None,
        "host": _state.get("host"),
        "port": PORT,
        "auth_mode": "none" if _state["active"] else "bearer",
        "mcp_running": mcp_alive,
        "mcp_auth": auth,
        "expires_at": _state.get("expires_at"),
        "remaining_seconds": remaining,
        "ttl_minutes": _state.get("ttl_minutes"),
        "public_reachable": bool(_state.get("public_reachable")),
        "cloudflared_available": bool(base.cloudflared_path()),
        "warning": (
            "No-auth mode is active. Anyone with the connector URL can start an OpenCode agent."
            if _state["active"]
            else ""
        ),
        "message": _state.get("message") or "Tunnel is not running.",
    }


async def get_status() -> dict[str, Any]:
    async with _lock:
        return await _status_unlocked()


async def start_tunnel(
    *,
    confirm: bool,
    ttl_minutes: int = DEFAULT_TTL_MINUTES,
    actor: str = "user",
) -> dict[str, Any]:
    if not confirm:
        raise ConfirmationRequired(
            "Starting the OpenCode tunnel exposes a coding agent. Re-send with confirm=true."
        )
    async with _lock:
        if _state["active"] and base._is_alive(_state.get("tunnel_pid")) and base._is_alive(_state.get("mcp_pid")):
            return await _status_unlocked()
        binary = base.cloudflared_path()
        if not binary:
            raise ConfigurationError(
                "cloudflared is not installed. Install it and add it to PATH, then retry."
            )
        ttl = base.normalize_ttl_minutes(ttl_minutes)
        expires_at = time.time() + ttl * 60 if ttl > 0 else None
        global _tunnel_proc, _tunnel_drain_task, _mcp_proc
        _reset_state()
        _clear_state_file()
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        _tunnel_proc = await asyncio.create_subprocess_exec(
            str(binary),
            "tunnel",
            "--url",
            f"http://127.0.0.1:{PORT}",
            "--no-autoupdate",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            creationflags=creationflags,
        )
        try:
            public_url = await base._read_tunnel_url(_tunnel_proc)
            host = urlparse(public_url).netloc
            _tunnel_drain_task = asyncio.create_task(base._drain_tunnel(_tunnel_proc))
            await base._stop_existing_mcp(PORT)
            _mcp_proc = base._spawn_mcp(
                PORT,
                auth_mode="none",
                public_url=public_url,
                host=host,
                profile=PROFILE,
            )
            await base._wait_mcp_health(PORT, "none")
            public_ok, public_error = await base._wait_public_health(public_url, timeout=20.0)
            _state.update(
                {
                    "active": True,
                    "public_url": public_url,
                    "host": host,
                    "tunnel_pid": _tunnel_proc.pid,
                    "mcp_pid": _mcp_proc.pid,
                    "started_at": time.time(),
                    "expires_at": expires_at,
                    "ttl_minutes": ttl,
                    "public_reachable": public_ok,
                    "message": (
                        "OpenCode tunnel is live."
                        if public_ok
                        else f"Tunnel started, but the public URL is not reachable yet ({public_error}). Refresh in a few seconds."
                    ),
                }
            )
            _persist()
            if ttl > 0:
                _schedule_expiry(ttl * 60)
            log(
                actor,
                "start_opencode_tunnel",
                "opencode_tunnel",
                host,
                {"public_url": public_url, "ttl_minutes": ttl},
            )
            return await _status_unlocked()
        except Exception:
            await _hard_cleanup()
            try:
                await _ensure_bearer()
            except ServiceError:
                pass
            raise


async def stop_tunnel(*, actor: str = "user", reason: str = "user") -> dict[str, Any]:
    global _expiry_task
    async with _lock:
        if _expiry_task and not _expiry_task.done():
            _expiry_task.cancel()
        _expiry_task = None
        was_active = bool(_state.get("active"))
        host = _state.get("host")
        await _hard_cleanup()
        try:
            await _ensure_bearer()
        except ServiceError as exc:
            if was_active:
                raise
            log(actor, "stop_opencode_tunnel_failed", "opencode_tunnel", host, {"error": exc.message})
        _reset_state()
        _clear_state_file()
        if was_active:
            log(actor, "stop_opencode_tunnel", "opencode_tunnel", host, {"reason": reason})
        return await _status_unlocked()


async def cleanup_stale_state() -> None:
    persisted = _load_persisted()
    if persisted.get("active") and not (
        base._is_alive(persisted.get("tunnel_pid")) and base._is_alive(persisted.get("mcp_pid"))
    ):
        _reset_state()
        _clear_state_file()
