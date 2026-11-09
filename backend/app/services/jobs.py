from __future__ import annotations

import asyncio
import json
import mimetypes
import re
import uuid
from pathlib import Path
from typing import Any

import websockets

from ..comfy.client import ComfyClient, ComfyError
from ..config import load_config
from ..db import execute, now, query, query_one
from ..logging_setup import logger
from ..workflows.adapter import build_prompt, validate_workflow
from ..workflows.registry import load_workflow
from .engines import combo_options
from .workflow_checks import missing_node_classes


def _safe_name(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name or "output"


def _unique_path(directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    counter = 2
    while (directory / f"{stem}_{counter}{suffix}").exists():
        counter += 1
    return directory / f"{stem}_{counter}{suffix}"


def _client(config: dict[str, Any]) -> ComfyClient:
    return ComfyClient(
        config["comfyui"]["server_url"],
        timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
    )


def mark_interrupted_jobs() -> None:
    execute(
        "UPDATE jobs SET status='interrupted', error=?, finished_at=? WHERE status IN ('queued','running')",
        ("Application restarted while this job was active.", now()),
    )


def list_jobs(limit: int = 50, status: str | None = None, project_id: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM jobs"
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if project_id:
        clauses.append("project_id = ?")
        params.append(project_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = query(sql, params)
    positions = _queue_positions()
    for row in rows:
        row["params"] = json.loads(row.pop("params_json") or "{}")
        row["outputs"] = json.loads(row.pop("outputs_json") or "[]")
        _decorate_queue(row, positions)
    return rows


def _queue_positions() -> dict[str, int]:
    rows = query("SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at ASC")
    return {row["id"]: index + 1 for index, row in enumerate(rows)}


def _decorate_queue(job: dict[str, Any], positions: dict[str, int] | None = None) -> dict[str, Any]:
    if job.get("status") == "queued":
        if positions is None:
            positions = _queue_positions()
        job["queue_position"] = positions.get(job["id"])
    elif job.get("status") == "running":
        job["queue_position"] = 0
    else:
        job["queue_position"] = None
    return job


def get_job(job_id: str) -> dict[str, Any] | None:
    row = query_one("SELECT * FROM jobs WHERE id = ?", (job_id,))
    if not row:
        return None
    row["params"] = json.loads(row.pop("params_json") or "{}")
    row["outputs"] = json.loads(row.pop("outputs_json") or "[]")
    return _decorate_queue(row)


def queue_state() -> dict[str, Any]:
    """Snapshot of the single-worker queue, with stable positions for queued jobs."""
    running_row = query_one(
        "SELECT id FROM jobs WHERE status = 'running' ORDER BY started_at ASC LIMIT 1"
    )
    pending_rows = query("SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at ASC")
    positions = {row["id"]: index + 1 for index, row in enumerate(pending_rows)}
    running = get_job(running_row["id"]) if running_row else None
    pending: list[dict[str, Any]] = []
    for row in pending_rows:
        job = get_job(row["id"])
        if job:
            job["queue_position"] = positions[row["id"]]
            pending.append(job)
    return {
        "running": running,
        "pending": pending,
        "counts": {"running": 1 if running else 0, "queued": len(pending)},
    }


def current_job() -> dict[str, Any] | None:
    row = query_one(
        "SELECT * FROM jobs WHERE status IN ('running','queued') ORDER BY created_at ASC LIMIT 1"
    )
    return get_job(row["id"]) if row else None


class JobRunner:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self._cancel_requested: set[str] = set()
        self._active: str | None = None

    async def start(self) -> None:
        mark_interrupted_jobs()
        self._worker = asyncio.create_task(self._worker_loop(), name="cartoon-studio-job-worker")
        logger.info("Generation queue worker started.")

    async def stop(self) -> None:
        if self._worker:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None

    async def submit(self, project_id: str, workflow_id: str, workflow_name: str, params: dict[str, Any]) -> dict[str, Any]:
        job_id = uuid.uuid4().hex[:12]
        execute(
            """INSERT INTO jobs (id, project_id, scene_id, workflow_id, workflow_name, status, progress,
                                 params_json, created_at)
               VALUES (?, ?, ?, ?, ?, 'queued', 0, ?, ?)""",
            (
                job_id,
                project_id,
                params.get("scene_id"),
                workflow_id,
                workflow_name,
                json.dumps(params),
                now(),
            ),
        )
        await self._queue.put(job_id)
        logger.info("Queued job %s (%s) for project %s", job_id, workflow_id, project_id)
        return get_job(job_id) or {}

    async def cancel(self, job_id: str) -> str:
        job = get_job(job_id)
        if not job:
            return "not_running"
        if job["status"] == "queued":
            execute("UPDATE jobs SET status='cancelled', finished_at=? WHERE id=?", (now(), job_id))
            return "cancelled"
        if job["status"] == "running":
            self._cancel_requested.add(job_id)
            config = load_config()
            try:
                await _client(config).interrupt()
            except ComfyError as exc:
                logger.warning("Interrupt failed for job %s: %s", job_id, exc)
            return "cancelling"
        return "not_running"

    async def _worker_loop(self) -> None:
        while True:
            job_id = await self._queue.get()
            self._active = job_id
            try:
                await self._run_job(job_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - a failed job must not kill the worker
                logger.exception("Job %s failed", job_id)
                execute(
                    "UPDATE jobs SET status='failed', error=?, finished_at=? WHERE id=?",
                    (str(exc), now(), job_id),
                )
            finally:
                self._active = None
                self._cancel_requested.discard(job_id)
                self._queue.task_done()

    async def _run_job(self, job_id: str) -> None:
        job = get_job(job_id)
        if not job:
            return
        if job["status"] == "cancelled":
            return

        config = load_config()
        client = _client(config)
        params = dict(job["params"])
        params.setdefault("negative_prompt", config["generation"].get("negative_prompt"))

        loaded = load_workflow(config, job["workflow_id"])
        api = loaded["api"]
        mapping = loaded["mapping"]
        if not mapping:
            raise ValueError("Workflow has no mapping sidecar, so it cannot be run.")

        object_info = await client.object_info()
        checks = validate_workflow(api, mapping, object_info)
        failed = [check for check in checks if not check["ok"]]
        if failed:
            raise ValueError("; ".join(check["message"] for check in failed))

        missing_nodes = missing_node_classes(api, object_info)
        if missing_nodes:
            raise ValueError(
                "Workflow needs node types that are not installed in ComfyUI: "
                + ", ".join(missing_nodes)
                + "."
            )

        # Model availability check: fail before spending time on a bad workflow.
        for check in mapping.get("model_checks") or []:
            role = check.get("role")
            spec = (mapping.get("roles") or {}).get(role)
            if not spec:
                continue
            node = api.get(str(spec["node"]))
            if not node:
                continue
            value = node["inputs"].get(spec["input"])
            loader_info = object_info.get(check.get("loader", "")) or {}
            spec = (
                ((loader_info.get("input") or {}).get("required") or {})
                .get(check.get("input", ""), None)
            )
            options = combo_options(spec)
            if options and value not in options:
                raise ValueError(
                    f"Model '{value}' for role '{role}' is not available in ComfyUI. "
                    f"Available: {', '.join(map(str, options[:8])) or 'none'}."
                )

        # Never let two jobs reuse an output prefix.
        prefix_role = (mapping.get("roles") or {}).get("filename_prefix")
        if prefix_role:
            node = api.get(str(prefix_role["node"]))
            if node:
                node["inputs"][prefix_role["input"]] = f"cartoon_studio/{job_id}"

        prompt, applied = build_prompt(api, mapping, params)
        logger.info("Submitting job %s with roles applied: %s", job_id, ", ".join(sorted(applied)))

        submitted = await client.submit(prompt, client_id=f"cartoon-studio-{job_id}")
        prompt_id = submitted.get("prompt_id")
        if not prompt_id:
            raise ValueError(f"ComfyUI did not return a prompt_id: {submitted}")

        execute(
            "UPDATE jobs SET status='running', prompt_id=?, started_at=?, progress=0 WHERE id=?",
            (prompt_id, now(), job_id),
        )

        done = asyncio.Event()
        listener = asyncio.create_task(self._listen_progress(client, job_id, prompt_id, done))
        try:
            entry = await self._wait_for_completion(client, job_id, prompt_id, config)
        finally:
            done.set()
            listener.cancel()
            try:
                await listener
            except asyncio.CancelledError:
                pass

        if job_id in self._cancel_requested:
            execute("UPDATE jobs SET status='cancelled', finished_at=? WHERE id=?", (now(), job_id))
            return

        status = (entry.get("status") or {}).get("status_str", "success")
        if status != "success":
            messages = json.dumps((entry.get("status") or {}).get("messages", []))[:800]
            raise ValueError(f"ComfyUI reported status '{status}': {messages}")

        outputs = await self._save_outputs(config, client, job, entry)
        execute(
            "UPDATE jobs SET status='completed', progress=100, outputs_json=?, finished_at=? WHERE id=?",
            (json.dumps(outputs), now(), job_id),
        )
        logger.info("Job %s completed with %d output(s).", job_id, len(outputs))

    async def _wait_for_completion(
        self,
        client: ComfyClient,
        job_id: str,
        prompt_id: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + float(config["generation"].get("timeout_seconds", 1800))
        while True:
            if job_id in self._cancel_requested:
                return {"status": {"status_str": "cancelled"}}
            if asyncio.get_running_loop().time() > deadline:
                raise TimeoutError("Generation timed out.")
            try:
                history = await client.history(prompt_id)
            except ComfyError as exc:
                logger.warning("History poll failed for %s: %s", prompt_id, exc)
                await asyncio.sleep(2)
                continue
            if prompt_id in history:
                return history[prompt_id]
            await asyncio.sleep(2)

    async def _listen_progress(
        self,
        client: ComfyClient,
        job_id: str,
        prompt_id: str,
        done: asyncio.Event,
    ) -> None:
        url = client.ws_url(f"cartoon-studio-{job_id}")
        try:
            async with websockets.connect(url, max_size=None, open_timeout=10) as socket:
                while not done.is_set():
                    try:
                        message = await asyncio.wait_for(socket.recv(), timeout=3)
                    except asyncio.TimeoutError:
                        continue
                    if not isinstance(message, str):
                        continue
                    try:
                        payload = json.loads(message)
                    except json.JSONDecodeError:
                        continue
                    event_type = payload.get("type")
                    data = payload.get("data") or {}
                    if data.get("prompt_id") not in (None, prompt_id):
                        continue
                    if event_type == "progress":
                        maximum = data.get("max") or 0
                        value = data.get("value") or 0
                        progress = round(100 * value / maximum, 1) if maximum else 0
                        execute("UPDATE jobs SET progress=? WHERE id=?", (progress, job_id))
                    elif event_type == "progress_state":
                        nodes = data.get("nodes") or {}
                        total = 0
                        value = 0
                        for node in nodes.values():
                            if not isinstance(node, dict):
                                continue
                            total += int(node.get("max") or 0)
                            value += int(node.get("value") or 0)
                        if total:
                            execute(
                                "UPDATE jobs SET progress=? WHERE id=?",
                                (round(100 * value / total, 1), job_id),
                            )
                    elif event_type == "executing":
                        node = data.get("node")
                        execute("UPDATE jobs SET node=? WHERE id=?", (str(node) if node else None, job_id))
                    elif event_type == "executed":
                        node = data.get("node")
                        if node:
                            execute("UPDATE jobs SET node=? WHERE id=?", (str(node), job_id))
                    elif event_type == "execution_error":
                        message = (
                            data.get("exception_message")
                            or data.get("exception_type")
                            or "ComfyUI reported an execution error."
                        )
                        execute("UPDATE jobs SET error=? WHERE id=?", (str(message)[:800], job_id))
        except (OSError, websockets.WebSocketException) as exc:
            logger.debug("Progress WebSocket closed for %s: %s", job_id, exc)

    async def _save_outputs(
        self,
        config: dict[str, Any],
        client: ComfyClient,
        job: dict[str, Any],
        entry: dict[str, Any],
    ) -> list[dict[str, Any]]:
        outputs = entry.get("outputs") or {}
        saved: list[dict[str, Any]] = []
        project_dir = Path(config["paths"]["output_dir"]) / job["project_id"] / job["id"]
        attach = (job.get("params") or {}).get("attach") or {}

        for node_id, node_output in outputs.items():
            if not isinstance(node_output, dict):
                continue
            for key in ("images", "gifs", "videos", "audio"):
                for item in node_output.get(key) or []:
                    if not isinstance(item, dict) or not item.get("filename"):
                        continue
                    filename = _safe_name(item["filename"])
                    target = _unique_path(project_dir, filename)
                    try:
                        content = await client.view(
                            item["filename"],
                            item.get("subfolder", ""),
                            item.get("type", "output"),
                        )
                    except ComfyError as exc:
                        logger.error("Could not download %s: %s", item["filename"], exc)
                        continue
                    target.write_bytes(content)
                    asset_id = uuid.uuid4().hex[:12]
                    rel_path = str(target.relative_to(Path(config["paths"]["output_dir"]))).replace("\\", "/")
                    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
                    meta = dict(item.get("metadata") or {})
                    video_suffixes = (".mp4", ".webm", ".mov", ".mkv", ".gif")
                    kind = str(meta.get("kind") or "")
                    if key in ("videos", "gifs") or filename.lower().endswith(video_suffixes):
                        kind = "video"
                    elif not kind:
                        kind = key.rstrip("s")
                    meta.update({"node_id": node_id, "comfy_filename": item["filename"], "kind": kind})
                    execute(
                        """INSERT INTO assets (id, project_id, job_id, kind, filename, rel_path, mime, meta_json, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            asset_id,
                            job["project_id"],
                            job["id"],
                            kind,
                            target.name,
                            rel_path,
                            mime,
                            json.dumps(meta),
                            now(),
                        ),
                    )
                    saved.append(
                        {
                            "asset_id": asset_id,
                            "filename": target.name,
                            "rel_path": rel_path,
                            "kind": kind,
                            "mime": mime,
                            "url": f"/api/assets/{asset_id}/file",
                            "metadata": meta,
                        }
                    )
                    if attach.get("owner_type") and attach.get("owner_id"):
                        link_id = uuid.uuid4().hex[:12]
                        execute(
                            """INSERT INTO media_links (id, asset_id, owner_type, owner_id, role, label, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (
                                link_id,
                                asset_id,
                                str(attach["owner_type"]),
                                str(attach["owner_id"]),
                                str(attach.get("role", "reference")),
                                str(attach.get("label", "")),
                                now(),
                            ),
                        )
                        saved[-1]["attach"] = {
                            "link_id": link_id,
                            "owner_type": attach["owner_type"],
                            "owner_id": attach["owner_id"],
                            "role": attach.get("role", "reference"),
                            "label": attach.get("label", ""),
                        }
        return saved


runner = JobRunner()
