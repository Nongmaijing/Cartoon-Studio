from __future__ import annotations

import asyncio
import hashlib
import os
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from ..config import load_config

# Only these explicitly reviewed sources can be downloaded. Nothing is accepted
# from the client except the recommendation name and a licence confirmation.
SOURCES: dict[str, dict[str, Any]] = {
    "SDXL Base 1.0": {
        "provider": "huggingface",
        "filename": "sd_xl_base_1.0.safetensors",
        "category": "checkpoints",
        "url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors",
        "size_bytes": 6938078334,
        "sha256": "31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b",
        "license": "CreativeML Open RAIL++-M",
        "token_env": "HF_TOKEN",
    },
    "DreamShaper XL": {
        "provider": "civitai",
        "filename": "DreamShaperXL1.0Alpha2_fixedVae_half_00001_.safetensors",
        "category": "checkpoints",
        "url": "https://civitai.com/api/download/models/126688",
        "size_bytes": 6938068556,
        "sha256": "0f1b80cfe81b9c3bde7fdcbf6898897b2811b27be1df684583c3d85cbc9b1fa4",
        "license": "CreativeML Open RAIL++-M",
        "token_env": "CIVITAI_TOKEN",
    },
    "Blue Pencil XL": {
        "provider": "civitai",
        "filename": "blue_pencil-XL-v7.0.0.safetensors",
        "category": "checkpoints",
        "url": "https://civitai.com/api/download/models/592322",
        "size_bytes": 6938041144,
        "sha256": "cff5a50ddeddad52b655a1786992b8f60ffa863b5678527722c1ce404d7f4ee7",
        "license": "CreativeML Open RAIL++-M",
        "token_env": "CIVITAI_TOKEN",
    },
    "Juggernaut XL": {
        "provider": "civitai",
        "filename": "JuggernautXL_Ragnarok_ByRunDiffusion.safetensors",
        "category": "checkpoints",
        "url": "https://civitai.com/api/download/models/1759168",
        "size_bytes": 7105350162,
        "sha256": "dd08fa32f98d05a2443ca1419e46df1575a0811f6e3b246d9dd47ff20f5eb66a",
        "license": "CreativeML Open RAIL++-M",
        "token_env": "CIVITAI_TOKEN",
    },
    "SDXL Lightning 8-step (LoRA)": {
        "provider": "huggingface",
        "filename": "sdxl_lightning_8step_lora.safetensors",
        "category": "loras",
        "url": "https://huggingface.co/ByteDance/SDXL-Lightning/resolve/main/sdxl_lightning_8step_lora.safetensors",
        "size_bytes": 393854592,
        "sha256": "5aa30d94cdf7950a8b53a693682650ee061eddb128c5435a8f88defea73b2ac6",
        "license": "CreativeML Open RAIL++-M",
        "token_env": "",
    },
    "SDXL Lightning 4-step (LoRA)": {
        "provider": "huggingface",
        "filename": "sdxl_lightning_4step_lora.safetensors",
        "category": "loras",
        "url": "https://huggingface.co/ByteDance/SDXL-Lightning/resolve/main/sdxl_lightning_4step_lora.safetensors",
        "size_bytes": 393854592,
        "sha256": "bf56cf2657efb15e465d81402ed481d1e11c4677e4bcce1bc11fe71ad8506b79",
        "license": "CreativeML Open RAIL++-M",
        "token_env": "",
    },
}

_DOWNLOADS: dict[str, dict[str, Any]] = {}
_TASKS: dict[str, asyncio.Task[None]] = {}
_QUEUE_LOCK = asyncio.Lock()


def describe(recommendation: str) -> dict[str, Any]:
    source = SOURCES.get(recommendation)
    if not source:
        return {
            "available": False,
            "reason": "No vetted direct download. Choose a model card and install it manually.",
        }
    token_env = str(source.get("token_env") or "")
    return {
        "available": True,
        "provider": source["provider"],
        "filename": source["filename"],
        "category": source["category"],
        "size_bytes": source["size_bytes"],
        "size_gb": round(source["size_bytes"] / 1024**3, 2),
        "sha256": source["sha256"],
        "license": source["license"],
        "token_configured": bool(token_env and os.environ.get(token_env)),
        "token_env": token_env or None,
    }


def _download_root(category: str) -> Path:
    config = load_config()
    dirs = [Path(value) for value in (config.get("comfyui", {}).get("models_dirs") or []) if value]
    if not dirs:
        raise ValueError("No ComfyUI model directories are configured.")
    # First configured directory is the intended bulk-storage location.
    base = dirs[0]
    if not base.parent.exists():
        raise ValueError(f"Model directory parent does not exist: {base.parent}")
    target = base / category
    target.mkdir(parents=True, exist_ok=True)
    return target


def _snapshot(state: dict[str, Any]) -> dict[str, Any]:
    total = int(state.get("bytes_total") or 0)
    done = int(state.get("bytes_downloaded") or 0)
    speed = float(state.get("speed_mbps") or 0.0)
    return {
        "id": state["id"],
        "recommendation": state["recommendation"],
        "filename": state["filename"],
        "category": state["category"],
        "status": state["status"],
        "bytes_downloaded": done,
        "bytes_total": total,
        "percent": round(done / total * 100, 2) if total else 0.0,
        "speed_mbps": round(speed, 2),
        "path": state.get("path") or "",
        "error": state.get("error"),
        "message": state.get("message") or "",
        "started_at": state.get("started_at"),
        "finished_at": state.get("finished_at"),
    }


def list_downloads() -> list[dict[str, Any]]:
    return [_snapshot(state) for state in _DOWNLOADS.values()]


def get_download(download_id: str) -> dict[str, Any] | None:
    state = _DOWNLOADS.get(download_id)
    return _snapshot(state) if state else None


def cancel_download(download_id: str) -> dict[str, Any] | None:
    state = _DOWNLOADS.get(download_id)
    if not state:
        return None
    if state["status"] in ("completed", "failed", "cancelled"):
        return _snapshot(state)
    state["cancel"] = True
    state["message"] = "Cancelling…"
    return _snapshot(state)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _run(state: dict[str, Any], source: dict[str, Any]) -> None:
    async with _QUEUE_LOCK:
        if state.get("cancel"):
            state["status"] = "cancelled"
            state["finished_at"] = time.time()
            return
        state["status"] = "downloading"
        state["started_at"] = state.get("started_at") or time.time()
        target = Path(state["path"])
        part = target.with_suffix(target.suffix + ".part")
        expected = int(source.get("size_bytes") or 0)
        headers: dict[str, str] = {"User-Agent": "CartoonStudio-Downloader/1.0"}
        token_env = str(source.get("token_env") or "")
        token = os.environ.get(token_env, "") if token_env else ""
        if token:
            headers["Authorization"] = f"Bearer {token}"
        url = str(source["url"])
        if source.get("provider") == "civitai" and token:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}token={token}"

        start = part.stat().st_size if part.exists() else 0
        if expected and start > expected:
            part.unlink()
            start = 0
        if expected and start == expected:
            state["bytes_downloaded"] = start
            state["bytes_total"] = expected
        else:
            if start:
                headers["Range"] = f"bytes={start}-"
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(60.0, read=120.0), follow_redirects=True
                ) as client:
                    async with client.stream("GET", url, headers=headers) as response:
                        if response.status_code not in (200, 206):
                            hint = ""
                            if response.status_code in (401, 403):
                                hint = (
                                    f" Set {token_env} to an account token that has accepted this "
                                    "model's licence." if token_env else ""
                                )
                            raise ValueError(
                                f"Download refused with HTTP {response.status_code}.{hint}"
                            )
                        if response.status_code == 200 and start:
                            start = 0
                        total = expected or int(response.headers.get("content-length") or 0) + start
                        state["bytes_total"] = total
                        state["bytes_downloaded"] = start
                        mode = "ab" if start else "wb"
                        written = start
                        last = time.time()
                        window_start = last
                        window_bytes = written
                        with part.open(mode) as handle:
                            async for chunk in response.aiter_bytes(1024 * 1024):
                                if state.get("cancel"):
                                    state["status"] = "cancelled"
                                    state["message"] = "Cancelled; partial file kept for resume."
                                    state["finished_at"] = time.time()
                                    return
                                handle.write(chunk)
                                written += len(chunk)
                                now = time.time()
                                if now - last >= 0.5:
                                    state["bytes_downloaded"] = written
                                    state["speed_mbps"] = (
                                        (written - window_bytes) / max(0.001, now - window_start) / 1024**2
                                    )
                                    last = now
                                    window_start = now
                                    window_bytes = written
                            handle.flush()
                            os.fsync(handle.fileno())
            except httpx.HTTPError as exc:
                state["status"] = "failed"
                state["error"] = f"Network error: {exc}"
                state["finished_at"] = time.time()
                return
            except ValueError as exc:
                state["status"] = "failed"
                state["error"] = str(exc)
                state["finished_at"] = time.time()
                return

        actual = part.stat().st_size if part.exists() else 0
        if expected and actual != expected:
            state["status"] = "failed"
            state["error"] = f"Size mismatch: got {actual} bytes, expected {expected}."
            state["finished_at"] = time.time()
            return

        state["status"] = "verifying"
        state["message"] = "Verifying SHA256…"
        state["speed_mbps"] = 0.0
        state["bytes_downloaded"] = actual
        try:
            actual_sha = await asyncio.to_thread(_sha256, part)
        except OSError as exc:
            state["status"] = "failed"
            state["error"] = f"Could not read downloaded file: {exc}"
            state["finished_at"] = time.time()
            return
        if str(source["sha256"]).lower() != actual_sha.lower():
            bad = part.with_suffix(part.suffix + ".bad")
            part.replace(bad)
            state["status"] = "failed"
            state["error"] = (
                "SHA256 mismatch. The file was quarantined for inspection: " + str(bad)
            )
            state["finished_at"] = time.time()
            return

        if target.exists():
            part.unlink(missing_ok=True)
            state["status"] = "completed"
            state["message"] = "File already existed; verified copy kept."
        else:
            os.replace(part, target)
            state["status"] = "completed"
            state["message"] = "Installed. Refresh the model catalog."
        state["path"] = str(target)
        state["finished_at"] = time.time()


async def start_download(
    recommendation: str,
    *,
    accept_license: bool,
    actor: str = "user",
) -> dict[str, Any]:
    if not accept_license:
        raise ValueError("Licence confirmation is required before downloading.")
    source = SOURCES.get(recommendation)
    if not source:
        raise ValueError("This recommendation has no vetted direct download.")
    for state in _DOWNLOADS.values():
        if (
            state["recommendation"] == recommendation
            and state["status"] in ("queued", "downloading", "verifying")
        ):
            return _snapshot(state)

    directory = _download_root(str(source["category"]))
    target = directory / str(source["filename"])
    if target.exists():
        raise ValueError(f"Already installed at {target}. Delete or rename it first.")

    download_id = uuid.uuid4().hex[:12]
    state: dict[str, Any] = {
        "id": download_id,
        "recommendation": recommendation,
        "filename": source["filename"],
        "category": source["category"],
        "status": "queued",
        "bytes_downloaded": 0,
        "bytes_total": int(source.get("size_bytes") or 0),
        "speed_mbps": 0.0,
        "path": str(target),
        "error": None,
        "message": "Queued.",
        "started_at": None,
        "finished_at": None,
        "cancel": False,
    }
    _DOWNLOADS[download_id] = state
    task = asyncio.create_task(_run(state, source))
    _TASKS[download_id] = task
    task.add_done_callback(lambda _: _TASKS.pop(download_id, None))
    return _snapshot(state)
