from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import psutil

from ..config import BASE_DIR
from ..core.runtime import mcp_settings
from .audit_service import log
from .errors import ConfirmationRequired, ConfigurationError, ServiceError

STATE_FILE = BASE_DIR / "data" / "chatgpt_tunnel_state.json"
LOG_DIR = BASE_DIR / "logs"
BACKEND_DIR = BASE_DIR / "backend"
MCP_SCRIPT = BACKEND_DIR / "run_mcp.py"
TUNNEL_URL_RE = re.compile(r"https://[a-zA-Z0-9][a-zA-Z0-9.-]*\.trycloudflare\.com")
DEFAULT_TTL_MINUTES = 30
MIN_TTL_MINUTES = 5
MAX_TTL_MINUTES = 480


def normalize_ttl_minutes(value: Any) -> int:
    """0 (or a negative value) means no automatic expiry."""
    if value is None:
        return DEFAULT_TTL_MINUTES
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return DEFAULT_TTL_MINUTES
    if minutes <= 0:
        return 0
    return max(MIN_TTL_MINUTES, min(MAX_TTL_MINUTES, minutes))

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


def _python_path() -> str:
    candidate = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    return str(candidate if candidate.exists() else sys.executable)


def cloudflared_path() -> Path | None:
    candidates = [
        shutil.which("cloudflared"),
        r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
        r"C:\Program Files\cloudflared\cloudflared.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    return None


def parse_tunnel_url(text: str) -> str | None:
    match = TUNNEL_URL_RE.search(text or "")
    return match.group(0).rstrip("/") if match else None


def _is_alive(pid: Any) -> bool:
    if not pid:
        return False
    try:
        process = psutil.Process(int(pid))
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, TypeError):
        return False


def _cmdline(pid: Any) -> str:
    if not pid:
        return ""
    try:
        return " ".join(psutil.Process(int(pid)).cmdline())
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, TypeError):
        return ""


def _cmdline_contains(pid: Any, needle: str) -> bool:
    return needle in _cmdline(pid)


def _terminate_pid(pid: Any, expected: str | None = None) -> None:
    if not pid:
        return
    try:
        process = psutil.Process(int(pid))
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, TypeError):
        return
    if expected and expected not in " ".join(process.cmdline()):
        return
    try:
        processes = [process, *process.children(recursive=True)]
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        processes = [process]
    for item in processes:
        try:
            item.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    _, alive = psutil.wait_procs(processes, timeout=5)
    for item in alive:
        try:
            item.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def _find_port_pid(port: int) -> int | None:
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                return conn.pid
    except (psutil.AccessDenied, OSError):
        pass
    try:
        output = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            errors="ignore",
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[1].endswith(f":{port}") and parts[3] == "LISTENING":
            try:
                return int(parts[4])
            except ValueError:
                return None
    return None


async def _wait_port_free(port: int, timeout: float = 10.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if _find_port_pid(port) is None:
            return
        await asyncio.sleep(0.25)
    raise ServiceError(f"Port {port} did not become free.")


def _persist() -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        key: value
        for key, value in _state.items()
        if key in {
            "active",
            "public_url",
            "host",
            "tunnel_pid",
            "mcp_pid",
            "started_at",
            "expires_at",
            "ttl_minutes",
            "public_reachable",
            "message",
        }
    }
    STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_persisted() -> dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _clear_state_file() -> None:
    try:
        STATE_FILE.unlink()
    except OSError:
        pass


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


async def _drain_tunnel(proc: asyncio.subprocess.Process) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "chatgpt_tunnel.log"
    try:
        with log_path.open("ab") as handle:
            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
                handle.write(line)
                handle.flush()
    except (asyncio.CancelledError, OSError):
        return


async def _read_tunnel_url(proc: asyncio.subprocess.Process, timeout: float = 45.0) -> str:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    buffer = ""
    while loop.time() < deadline:
        remaining = max(0.25, deadline - loop.time())
        try:
            line = await asyncio.wait_for(proc.stderr.readline(), timeout=remaining)
        except asyncio.TimeoutError:
            break
        if not line:
            break
        text = line.decode("utf-8", errors="replace")
        buffer = (buffer + text)[-4000:]
        url = parse_tunnel_url(text)
        if url:
            return url
    if proc.returncode is not None:
        raise ServiceError(f"cloudflared exited with code {proc.returncode}: {buffer[-800:]}", status_code=502, code="tunnel_failed")
    raise ServiceError("cloudflared did not publish a public URL in time.", status_code=504, code="tunnel_timeout")


def _spawn_mcp(port: int, *, auth_mode: str, public_url: str = "", host: str = "") -> subprocess.Popen:
    env = os.environ.copy()
    env["MCP_HOST"] = "127.0.0.1"
    env["MCP_PORT"] = str(port)
    env["MCP_AUTH_MODE"] = auth_mode
    if auth_mode == "none":
        env["MCP_ALLOW_UNAUTHENTICATED"] = "true"
        env["MCP_PUBLIC_URL"] = public_url
        env["MCP_ALLOWED_HOSTS"] = host
        env["MCP_ALLOWED_ORIGINS"] = public_url
    else:
        env["MCP_AUTH_MODE"] = "bearer"
        env["MCP_ALLOW_UNAUTHENTICATED"] = "false"
        env["MCP_PUBLIC_URL"] = f"http://127.0.0.1:{port}"
        env.pop("MCP_ALLOWED_HOSTS", None)
        env.pop("MCP_ALLOWED_ORIGINS", None)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = (LOG_DIR / "mcp.out.log").open("ab")
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    try:
        return subprocess.Popen(
            [
                _python_path(),
                str(MCP_SCRIPT),
                "--transport",
                "streamable-http",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=str(BACKEND_DIR),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
    finally:
        log_file.close()


async def _probe_auth(port: int) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(f"http://127.0.0.1:{port}/health")
            if response.status_code == 200:
                return str(response.json().get("auth") or "")
    except (httpx.HTTPError, ValueError):
        return None
    return None


async def _wait_mcp_health(port: int, expected_auth: str, timeout: float = 35.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    last_error = "no response"
    while loop.time() < deadline:
        auth = await _probe_auth(port)
        if auth == expected_auth:
            return
        if auth:
            last_error = f"auth={auth}"
        else:
            last_error = "health endpoint unavailable"
        await asyncio.sleep(0.5)
    raise ServiceError(
        f"MCP on port {port} did not become healthy with auth={expected_auth}: {last_error}",
        status_code=504,
        code="mcp_health_timeout",
    )


async def _wait_public_health(public_url: str, timeout: float = 35.0) -> tuple[bool, str | None]:
    probe = public_url.rstrip("/") + "/health"
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    last_error: str | None = "no response"
    async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
        while loop.time() < deadline:
            try:
                response = await client.get(probe)
                if response.status_code == 200:
                    data = response.json()
                    if str(data.get("auth") or "") == "none":
                        return True, None
                    last_error = f"unexpected auth={data.get('auth')}"
                else:
                    last_error = f"HTTP {response.status_code}"
            except (httpx.HTTPError, ValueError) as exc:
                last_error = str(exc)
            await asyncio.sleep(1.5)
    return False, last_error


async def _stop_existing_mcp(port: int) -> None:
    pid = _find_port_pid(port)
    if not pid:
        return
    if not _cmdline_contains(pid, "run_mcp.py"):
        raise ServiceError(
            f"Port {port} is occupied by another process. Stop it before using the ChatGPT connector.",
            status_code=409,
            code="port_in_use",
        )
    _terminate_pid(pid, "run_mcp.py")
    await _wait_port_free(port)


async def _ensure_bearer_mcp(port: int, timeout: float = 25.0) -> None:
    pid = _find_port_pid(port)
    if pid:
        if not _cmdline_contains(pid, "run_mcp.py"):
            raise ServiceError(
                f"Port {port} is occupied by another process; cannot restore bearer MCP.",
                status_code=409,
                code="port_in_use",
            )
        if await _probe_auth(port) == "bearer":
            return
        _terminate_pid(pid, "run_mcp.py")
        await _wait_port_free(port)
    global _mcp_proc
    _mcp_proc = _spawn_mcp(port, auth_mode="bearer")
    await _wait_mcp_health(port, "bearer", timeout=timeout)


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


async def _hard_cleanup() -> None:
    global _expiry_task, _tunnel_proc, _tunnel_drain_task, _mcp_proc
    if _expiry_task and not _expiry_task.done():
        _expiry_task.cancel()
    _expiry_task = None
    tunnel_pid = _state.get("tunnel_pid") or (_tunnel_proc.pid if _tunnel_proc else None)
    mcp_pid = _state.get("mcp_pid") or (_mcp_proc.pid if _mcp_proc else None)
    _terminate_pid(tunnel_pid, "cloudflared")
    _terminate_pid(mcp_pid, "run_mcp.py")
    if _tunnel_proc is not None:
        try:
            await asyncio.wait_for(_tunnel_proc.wait(), timeout=5)
        except (asyncio.TimeoutError, ProcessLookupError):
            pass
    if _tunnel_drain_task and not _tunnel_drain_task.done():
        _tunnel_drain_task.cancel()
    _tunnel_proc = None
    _tunnel_drain_task = None
    _mcp_proc = None
    _reset_state()
    _clear_state_file()


async def start_tunnel(
    *,
    confirm: bool,
    ttl_minutes: int = DEFAULT_TTL_MINUTES,
    actor: str = "user",
) -> dict[str, Any]:
    if not confirm:
        raise ConfirmationRequired(
            "Starting the ChatGPT tunnel exposes production control. Re-send with confirm=true."
        )
    async with _lock:
        if _state["active"] and _is_alive(_state.get("tunnel_pid")) and _is_alive(_state.get("mcp_pid")):
            return await _status_unlocked()

        binary = cloudflared_path()
        if not binary:
            raise ConfigurationError(
                "cloudflared is not installed. Install it and add it to PATH, then retry."
            )

        ttl = normalize_ttl_minutes(ttl_minutes)
        expires_at = time.time() + ttl * 60 if ttl > 0 else None
        port = int(mcp_settings()["port"])
        global _tunnel_proc, _tunnel_drain_task, _mcp_proc

        _reset_state()
        _clear_state_file()
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        _tunnel_proc = await asyncio.create_subprocess_exec(
            str(binary),
            "tunnel",
            "--url",
            f"http://127.0.0.1:{port}",
            "--no-autoupdate",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            creationflags=creationflags,
        )
        try:
            public_url = await _read_tunnel_url(_tunnel_proc)
            host = urlparse(public_url).netloc
            _tunnel_drain_task = asyncio.create_task(_drain_tunnel(_tunnel_proc))
            await _stop_existing_mcp(port)
            _mcp_proc = _spawn_mcp(port, auth_mode="none", public_url=public_url, host=host)
            await _wait_mcp_health(port, "none")
            public_ok, public_error = await _wait_public_health(public_url, timeout=20.0)
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
                        "ChatGPT tunnel is live."
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
                "start_chatgpt_tunnel",
                "mcp_tunnel",
                host,
                {"public_url": public_url, "ttl_minutes": ttl},
            )
            return await _status_unlocked()
        except Exception:
            await _hard_cleanup()
            try:
                await _ensure_bearer_mcp(port, timeout=15)
            except ServiceError:
                pass
            raise


async def stop_tunnel(*, actor: str = "user", reason: str = "user") -> dict[str, Any]:
    async with _lock:
        was_active = bool(_state.get("active"))
        host = _state.get("host")
        await _hard_cleanup()
        port = int(mcp_settings()["port"])
        try:
            await _ensure_bearer_mcp(port)
        except ServiceError as exc:
            if was_active:
                raise
            log(actor, "stop_chatgpt_tunnel_failed", "mcp_tunnel", host, {"error": exc.message})
        if was_active:
            log(actor, "stop_chatgpt_tunnel", "mcp_tunnel", host, {"reason": reason})
        return await _status_unlocked()


async def cleanup_stale_state() -> None:
    persisted = _load_persisted()
    if not persisted.get("active"):
        _clear_state_file()
        return
    _terminate_pid(persisted.get("tunnel_pid"), "cloudflared")
    _terminate_pid(persisted.get("mcp_pid"), "run_mcp.py")
    _clear_state_file()
    try:
        await _ensure_bearer_mcp(int(mcp_settings()["port"]), timeout=15)
    except ServiceError:
        pass


async def _refresh_state() -> None:
    if not _state.get("active"):
        return
    if _is_alive(_state.get("tunnel_pid")) and _is_alive(_state.get("mcp_pid")):
        return
    await _hard_cleanup()
    try:
        await _ensure_bearer_mcp(int(mcp_settings()["port"]), timeout=15)
    except ServiceError:
        pass


async def _status_unlocked() -> dict[str, Any]:
    await _refresh_state()
    port = int(mcp_settings()["port"])
    if _state.get("active") and not _state.get("public_reachable") and _state.get("public_url"):
        public_ok, _ = await _wait_public_health(str(_state["public_url"]), timeout=4.0)
        if public_ok:
            _state["public_reachable"] = True
            _state["message"] = "ChatGPT tunnel is live."
            _persist()
    mcp_running = False
    mcp_auth: str | None = None
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(f"http://127.0.0.1:{port}/health")
            if response.status_code == 200:
                mcp_running = True
                mcp_auth = str(response.json().get("auth") or "")
    except (httpx.HTTPError, ValueError):
        pass
    active = bool(_state.get("active"))
    remaining = None
    if active and _state.get("expires_at"):
        remaining = max(0, int(float(_state["expires_at"]) - time.time()))
    return {
        "active": active,
        "public_url": _state.get("public_url"),
        "connector_url": f"{_state['public_url']}/mcp" if active and _state.get("public_url") else None,
        "host": _state.get("host"),
        "auth_mode": "none" if active else (mcp_auth or "unknown"),
        "mcp_running": mcp_running,
        "mcp_auth": mcp_auth,
        "expires_at": _state.get("expires_at"),
        "remaining_seconds": remaining,
        "ttl_minutes": _state.get("ttl_minutes") if _state.get("ttl_minutes") is not None else DEFAULT_TTL_MINUTES,
        "public_reachable": bool(_state.get("public_reachable")),
        "cloudflared_available": cloudflared_path() is not None,
        "warning": (
            "No-auth mode is active. Anyone with the connector URL can control production."
            if active
            else ""
        ),
        "message": _state.get("message") or ("ChatGPT tunnel is live." if active else "Tunnel is not running."),
    }


async def get_status() -> dict[str, Any]:
    return await _status_unlocked()
