from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from ..config import load_config
from ..db import execute, now, query, query_one
from ..providers.registry import registry
from ..schemas import EpisodeTimeline
from ..services import dialogue_service, episode_export, episode_service, episodes, scene_service
from ..services.audit_service import log
from ..services.errors import ConfirmationRequired, NotFoundError, ServiceError
from ..services.media import list_media
from . import workflow_engine as wf
from .workflow_engine import (
    ANIMATION,
    AUDIO_GENERATION,
    COMPLETED,
    FINAL_EDITING,
    FINAL_REVIEW,
    PAUSED,
    PLANNING,
    SCENE_GENERATION,
    SCENE_REVIEW,
    CANCELLED,
    FAILED,
)

_workers: dict[str, asyncio.Task] = {}
_cancel_requests: set[str] = set()


def _run(run_id: str) -> dict[str, Any]:
    row = query_one("SELECT * FROM production_runs WHERE id = ?", (run_id,))
    if not row:
        raise NotFoundError("Production run not found.")
    row["plan"] = json.loads(row.get("plan_json") or "{}")
    return row


def _task(task_id: str) -> dict[str, Any]:
    row = query_one("SELECT * FROM production_tasks WHERE id = ?", (task_id,))
    if not row:
        raise NotFoundError("Production task not found.")
    row["payload"] = json.loads(row.get("payload_json") or "{}")
    row["result"] = json.loads(row.get("result_json") or "{}")
    return row


def _update_run(run_id: str, **updates: Any) -> None:
    allowed = {"state", "status", "progress", "current_stage", "error", "log", "started_at", "finished_at"}
    parts: list[str] = []
    params: list[Any] = []
    for key, value in updates.items():
        if key in allowed:
            parts.append(f"{key} = ?")
            params.append(value)
    if parts:
        parts.append("updated_at = ?")
        params.extend([now(), run_id])
        execute(f"UPDATE production_runs SET {', '.join(parts)} WHERE id = ?", params)


def _append_log(run_id: str, message: str) -> None:
    row = query_one("SELECT log FROM production_runs WHERE id = ?", (run_id,))
    existing = (row.get("log") if row else "") or ""
    combined = (existing + ("\n" if existing else "") + message)[-16000:]
    _update_run(run_id, log=combined)


def _create_task(run_id: str, stage: str, scene_id: str | None, payload: dict[str, Any], order: int) -> str:
    task_id = uuid.uuid4().hex[:12]
    execute(
        """INSERT INTO production_tasks
           (id, run_id, stage, scene_id, status, attempts, payload_json, result_json, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'pending', 0, ?, '{}', ?, ?)""",
        (task_id, run_id, stage, scene_id, json.dumps(payload), now(), now()),
    )
    return task_id


def _scene_has_keyframe(scene_id: str) -> bool:
    return any(item["role"] == "keyframe" for item in list_media("scene", scene_id))


def _scene_dialogue_missing(scene_id: str) -> bool:
    status = dialogue_service.audio_status(scene_id)
    return bool(status["total"] and status["missing_audio"])


def _build_tasks(run_id: str, plan: dict[str, Any]) -> int:
    scenes = plan.get("scenes") or []
    if not scenes:
        raise ServiceError("A production plan must contain at least one scene.")
    order = 0
    for index, item in enumerate(scenes):
        scene_id = str(item.get("scene_id") or "")
        if not scene_id:
            raise ServiceError("Every production scene needs a scene_id.")
        scene_service.get_scene_details(scene_id)
        if item.get("regenerate") or not _scene_has_keyframe(scene_id):
            _create_task(
                run_id,
                "SCENE_IMAGE",
                scene_id,
                {
                    "seed": item.get("seed"),
                    "steps": item.get("steps"),
                    "cfg": item.get("cfg"),
                    "width": item.get("width"),
                    "height": item.get("height"),
                    "prompt": item.get("prompt"),
                    "reference_asset_id": item.get("reference_asset_id"),
                    "reference_mode": item.get("reference_mode", "identity"),
                    "denoise": item.get("denoise", 0.55),
                },
                order,
            )
            order += 1
        if _scene_dialogue_missing(scene_id):
            _create_task(run_id, "AUDIO", scene_id, {}, order)
            order += 1
        if item.get("animate") or plan.get("animate"):
            _create_task(
                run_id,
                "ANIMATION",
                scene_id,
                {
                    "seed": item.get("animation_seed"),
                    "length": item.get("length", plan.get("length")),
                    "fps": item.get("fps", plan.get("fps")),
                    "workflow_id": item.get("animation_workflow_id"),
                },
                order,
            )
            order += 1
    if plan.get("assemble", True):
        _create_task(run_id, "ASSEMBLY", None, {"plan": plan}, order)
        order += 1
    return order


def start_production(
    project_id: str,
    episode_id: str,
    *,
    plan: dict[str, Any] | None = None,
    actor: str = "user",
    confirm: bool = False,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    if not confirm:
        raise ConfirmationRequired("Starting production requires explicit confirmation (confirm=true).")
    episode = episode_service.get_episode(episode_id)
    production = episode.get("production") or {}
    if not production.get("script_approved"):
        raise ServiceError(
            "The episode script must be approved before production can start.",
            status_code=409,
            code="script_not_approved",
        )
    existing = query_one(
        "SELECT * FROM production_runs WHERE episode_id = ? AND status IN ('running','paused') ORDER BY created_at DESC LIMIT 1",
        (episode_id,),
    )
    if existing:
        return get_status(existing["id"])
    if plan is None:
        rows = query("SELECT id FROM scenes WHERE project_id = ? ORDER BY created_at ASC", (project_id,))
        storyboard_ids = [
            str(item.get("scene_id")) for item in (episode.get("storyboard") or [])
            if item.get("scene_id")
        ]
        if storyboard_ids:
            allowed = set(storyboard_ids)
            rows = [row for row in rows if row["id"] in allowed]
        plan = {"scenes": [{"scene_id": row["id"]} for row in rows], "assemble": True}
    if not plan.get("scenes"):
        raise ServiceError("No scenes are available for production.")

    missing_scenes: list[str] = []
    missing_cast: list[str] = []
    for item in plan.get("scenes") or []:
        scene_id = str(item.get("scene_id") or "")
        if not scene_id:
            continue
        scene = scene_service.get_scene_details(scene_id)
        if scene.get("approval_status") != "approved":
            missing_scenes.append(scene.get("name") or scene_id)
        for member in scene.get("cast") or []:
            character_id = member.get("character_id")
            if not character_id:
                continue
            row = query_one("SELECT name, approval_status FROM characters WHERE id = ?", (character_id,))
            if row and row.get("approval_status") != "approved":
                missing_cast.append(row.get("name") or character_id)
    if missing_scenes or missing_cast:
        parts = []
        if missing_scenes:
            parts.append("unapproved scenes: " + ", ".join(sorted(set(missing_scenes))))
        if missing_cast:
            parts.append("unapproved cast: " + ", ".join(sorted(set(missing_cast))))
        raise ServiceError(
            "Approve all scenes and cast before production. Missing " + "; ".join(parts) + ".",
            status_code=409,
            code="production_not_ready",
        )
    run_id = uuid.uuid4().hex[:12]
    timestamp = now()
    execute(
        """INSERT INTO production_runs
           (id, project_id, episode_id, state, status, progress, plan_json, created_at, updated_at, started_at)
           VALUES (?, ?, ?, ?, 'running', 0, ?, ?, ?, ?)""",
        (run_id, project_id, episode_id, PLANNING, json.dumps(plan), timestamp, timestamp, timestamp),
    )
    _build_tasks(run_id, plan)
    _update_run(run_id, state=SCENE_GENERATION, current_stage="SCENE_GENERATION", progress=1)
    _append_log(run_id, f"Production started with {len(plan.get('scenes') or [])} scene(s).")
    log(actor, "start_production", "production_run", run_id, {"episode_id": episode_id, "idempotency_key": idempotency_key})
    _ensure_worker(run_id)
    return get_status(run_id)


def _ensure_worker(run_id: str) -> None:
    task = _workers.get(run_id)
    if task and not task.done():
        return
    _workers[run_id] = asyncio.create_task(_run_worker(run_id), name=f"production-{run_id}")


async def _wait_job(run_id: str, job_id: str, timeout: float = 3600) -> dict[str, Any]:
    from ..services.jobs import get_job

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        run = _run(run_id)
        if run["status"] == "cancelled":
            try:
                provider = registry.get("image")
                await provider.cancel_job(job_id)
            except Exception:  # noqa: BLE001
                pass
            raise asyncio.CancelledError("Production cancelled.")
        if run["status"] == "paused":
            await asyncio.sleep(2)
            continue
        job = get_job(job_id)
        if not job:
            raise ServiceError(f"Job {job_id} was not found.")
        if job["status"] == "completed":
            return job
        if job["status"] in ("failed", "cancelled", "interrupted"):
            raise ServiceError(job.get("error") or f"Job {job_id} ended as {job['status']}.")
        await asyncio.sleep(2)
    raise ServiceError(f"Job {job_id} timed out.")


async def _execute_task(run_id: str, task: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    stage = task["stage"]
    scene_id = task.get("scene_id")
    payload = task.get("payload") or {}
    if stage == "SCENE_IMAGE":
        result = await scene_service.generate_scene_image(
            scene_id,
            prompt=payload.get("prompt"),
            seed=payload.get("seed"),
            steps=payload.get("steps"),
            cfg=payload.get("cfg"),
            width=payload.get("width"),
            height=payload.get("height"),
            reference_asset_id=payload.get("reference_asset_id"),
            reference_mode=payload.get("reference_mode", "identity"),
            denoise=payload.get("denoise", 0.55),
            actor="production",
        )
        job_id = (result.get("job") or {}).get("id") or result.get("job_id")
        if job_id:
            execute(
                "UPDATE production_tasks SET job_id = ?, updated_at = ? WHERE id = ?",
                (job_id, now(), task["id"]),
            )
            await _wait_job(run_id, job_id)
        return {"mode": result.get("mode"), "job_id": job_id}
    if stage == "AUDIO":
        result = await dialogue_service.generate_scene(scene_id, actor="production")
        return {"generated": result.get("generated"), "errors": result.get("errors")}
    if stage == "ANIMATION":
        result = await scene_service.animate_scene(
            scene_id,
            seed=payload.get("seed"),
            length=payload.get("length"),
            fps=payload.get("fps"),
            workflow_id=payload.get("workflow_id"),
            actor="production",
        )
        job_id = (result.get("job") or {}).get("id") or result.get("job_id")
        if job_id:
            execute(
                "UPDATE production_tasks SET job_id = ?, updated_at = ? WHERE id = ?",
                (job_id, now(), task["id"]),
            )
            await _wait_job(run_id, job_id)
        return {"job_id": job_id}
    if stage == "ASSEMBLY":
        episode = await _assemble_episode(run_id, plan)
        return {"episode_id": episode["id"], "output_url": episode.get("output_url")}
    raise ServiceError(f"Unknown production stage '{stage}'.")


async def _assemble_episode(run_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    run = _run(run_id)
    episode_id = run["episode_id"]
    episode = episode_service.get_episode(episode_id)
    settings = {
        "width": 1280,
        "height": 720,
        "fps": 24,
        "subtitles": "soft",
        "background_music_asset_id": None,
        "background_music_volume": 0.22,
        "fade_duration_ms": 400,
    }
    settings.update(plan.get("settings") or {})
    segments: list[dict[str, Any]] = []
    audio_items: list[dict[str, Any]] = []
    scene_start = 0
    for index, item in enumerate(plan.get("scenes") or []):
        scene_id = item["scene_id"]
        scene = scene_service.get_scene_details(scene_id)
        media = list_media("scene", scene_id)
        keyframes = [asset for asset in media if asset["role"] == "keyframe"]
        if not keyframes:
            raise ServiceError(f"Scene {scene_id} has no keyframe for assembly.")
        preferred = [asset for asset in keyframes if asset.get("label") == "production-upscale"]
        keyframe = (preferred or keyframes)[-1]
        duration_ms = int(item.get("duration_ms") or round(float(scene.get("duration") or 5.0) * 1000))
        segments.append(
            {
                "scene_id": scene_id,
                "asset_id": keyframe["id"],
                "kind": "image",
                "duration_ms": max(100, duration_ms),
                "trim_start_ms": 0,
                "transition": item.get("transition", "fade"),
                "motion": item.get("motion", "none"),
                "label": f"{scene.get('name') or scene_id} #{index + 1}",
            }
        )
        lines = dialogue_service.list_lines(scene_id)
        cursor = 0
        for line_index, line in enumerate(lines):
            if not line.get("audio_asset_id"):
                continue
            start = int(line.get("start_ms") or 0)
            if start <= 0:
                start = cursor
            audio_items.append(
                {
                    "id": f"aud_{index}_{line_index}",
                    "asset_id": line["audio_asset_id"],
                    "start_ms": scene_start + start,
                    "volume": 1.0,
                    "loop": False,
                    "label": f"{line.get('character_name') or 'Narrator'} · {str(line.get('text') or '')[:40]}",
                    "kind": "dialogue",
                }
            )
            cursor = max(cursor, start + int(line.get("duration_ms") or 0) + 150)
        scene_start += max(100, duration_ms)
    timeline = EpisodeTimeline.model_validate(
        {
            "segments": segments,
            "audio": audio_items,
            "settings": settings,
        }
    )
    episodes.save_timeline(episode_id, timeline)
    episode_export.start_export(episode_id)
    _append_log(run_id, f"Assembly queued for episode {episode_id}.")
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 3600
    while loop.time() < deadline:
        current = episode_service.get_episode(episode_id)
        if current["status"] == "completed":
            episode_service.set_production_state(episode_id, COMPLETED, {"completed_by": "production_orchestrator"})
            return current
        if current["status"] in ("failed", "cancelled", "interrupted"):
            raise ServiceError(current.get("error") or f"Episode export ended as {current['status']}.")
        await asyncio.sleep(2)
    raise ServiceError("Episode export timed out.")


async def _run_worker(run_id: str) -> None:
    try:
        while True:
            run = _run(run_id)
            if run["status"] == "cancelled" or run_id in _cancel_requests:
                _update_run(run_id, state=CANCELLED, status="cancelled", finished_at=now())
                _append_log(run_id, "Production cancelled.")
                return
            if run["status"] == "paused":
                await asyncio.sleep(2)
                continue
            task_row = query_one(
                "SELECT * FROM production_tasks WHERE run_id = ? AND status = 'pending' ORDER BY rowid ASC LIMIT 1",
                (run_id,),
            )
            if not task_row:
                failed = query_one(
                    "SELECT COUNT(*) AS n FROM production_tasks WHERE run_id = ? AND status = 'failed'",
                    (run_id,),
                )
                if failed and int(failed["n"]) > 0:
                    _update_run(run_id, state=FAILED, status="failed", error="One or more production tasks failed.", finished_at=now())
                else:
                    _update_run(run_id, state=COMPLETED, status="completed", progress=100, current_stage="COMPLETED", finished_at=now())
                    _append_log(run_id, "Production completed.")
                return
            task = _task(task_row["id"])
            execute(
                "UPDATE production_tasks SET status='running', attempts=attempts+1, started_at=?, updated_at=? WHERE id=?",
                (now(), now(), task["id"]),
            )
            _update_run(run_id, current_stage=task["stage"])
            _append_log(run_id, f"Starting task {task['stage']} for scene {task.get('scene_id') or '-'}.")
            plan: dict[str, Any] = {}
            try:
                plan = json.loads(_run(run_id).get("plan_json") or "{}")
                result = await _execute_task(run_id, task, plan)
                execute(
                    "UPDATE production_tasks SET status='completed', result_json=?, finished_at=?, updated_at=? WHERE id=?",
                    (json.dumps(result), now(), now(), task["id"]),
                )
                completed = query_one(
                    "SELECT COUNT(*) AS n FROM production_tasks WHERE run_id = ? AND status = 'completed'",
                    (run_id,),
                )
                total = query_one(
                    "SELECT COUNT(*) AS n FROM production_tasks WHERE run_id = ?",
                    (run_id,),
                )
                progress = round(100 * int(completed["n"]) / max(1, int(total["n"])), 1)
                state = SCENE_GENERATION if task["stage"] in ("SCENE_IMAGE", "AUDIO", "ANIMATION") else FINAL_EDITING
                _update_run(run_id, progress=progress, state=state)
                _append_log(run_id, f"Completed task {task['stage']}.")
            except asyncio.CancelledError:
                execute(
                    "UPDATE production_tasks SET status='cancelled', finished_at=?, updated_at=? WHERE id=?",
                    (now(), now(), task["id"]),
                )
                _update_run(run_id, state=CANCELLED, status="cancelled", finished_at=now())
                return
            except Exception as exc:  # noqa: BLE001
                max_attempts = int((plan or {}).get("max_attempts", 2)) if isinstance(plan, dict) else 2
                if int(task["attempts"]) + 1 < max_attempts:
                    execute(
                        "UPDATE production_tasks SET status='pending', error=?, updated_at=? WHERE id=?",
                        (str(exc)[:2000], now(), task["id"]),
                    )
                    _append_log(run_id, f"Task {task['stage']} failed, retrying: {exc}")
                    await asyncio.sleep(2)
                else:
                    execute(
                        "UPDATE production_tasks SET status='failed', error=?, finished_at=?, updated_at=? WHERE id=?",
                        (str(exc)[:4000], now(), now(), task["id"]),
                    )
                    _update_run(run_id, state=FAILED, status="failed", error=str(exc)[:4000], finished_at=now())
                    _append_log(run_id, f"Task {task['stage']} failed permanently: {exc}")
                    return
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        _update_run(run_id, state=FAILED, status="failed", error=str(exc)[:4000], finished_at=now())
    finally:
        _workers.pop(run_id, None)


def pause_production(run_id: str, actor: str = "user") -> dict[str, Any]:
    run = _run(run_id)
    if run["status"] not in ("running",):
        raise ServiceError("Only a running production can be paused.")
    _update_run(run_id, status="paused", state=PAUSED)
    _append_log(run_id, "Production paused.")
    log(actor, "pause_production", "production_run", run_id)
    return get_status(run_id)


def resume_production(run_id: str, actor: str = "user") -> dict[str, Any]:
    run = _run(run_id)
    if run["status"] != "paused":
        raise ServiceError("Only a paused production can be resumed.")
    _update_run(run_id, status="running", state=SCENE_GENERATION)
    _append_log(run_id, "Production resumed.")
    log(actor, "resume_production", "production_run", run_id)
    _ensure_worker(run_id)
    return get_status(run_id)


def cancel_production(run_id: str, actor: str = "user", confirm: bool = False) -> dict[str, Any]:
    if not confirm:
        raise ConfirmationRequired("Cancelling production requires explicit confirmation (confirm=true).")
    run = _run(run_id)
    if run["status"] in ("completed", "cancelled"):
        return get_status(run_id)
    _cancel_requests.add(run_id)
    _update_run(run_id, status="cancelled", state=CANCELLED, finished_at=now())
    running = query_one(
        "SELECT * FROM production_tasks WHERE run_id = ? AND status = 'running' LIMIT 1",
        (run_id,),
    )
    if running and running.get("job_id"):
        try:
            provider = registry.get("image")
            asyncio.create_task(provider.cancel_job(running["job_id"]))
        except Exception:  # noqa: BLE001
            pass
    if running and running.get("stage") == "ASSEMBLY":
        episode_export.cancel_export(run["episode_id"])
    _append_log(run_id, "Production cancelled.")
    log(actor, "cancel_production", "production_run", run_id)
    return get_status(run_id)


def get_status(run_id: str) -> dict[str, Any]:
    run = _run(run_id)
    tasks = query(
        "SELECT * FROM production_tasks WHERE run_id = ? ORDER BY rowid ASC",
        (run_id,),
    )
    for task in tasks:
        task["payload"] = json.loads(task.pop("payload_json") or "{}")
        task["result"] = json.loads(task.pop("result_json") or "{}")
    return {
        "run_id": run_id,
        "project_id": run["project_id"],
        "episode_id": run["episode_id"],
        "state": run["state"],
        "status": run["status"],
        "progress": run["progress"],
        "current_stage": run.get("current_stage"),
        "plan": run.get("plan"),
        "error": run.get("error"),
        "log": run.get("log"),
        "tasks": tasks,
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
    }


def get_queue(project_id: str | None = None) -> list[dict[str, Any]]:
    if project_id:
        rows = query(
            "SELECT * FROM production_runs WHERE project_id = ? ORDER BY created_at DESC LIMIT 50",
            (project_id,),
        )
    else:
        rows = query("SELECT * FROM production_runs ORDER BY created_at DESC LIMIT 50")
    return [get_status(row["id"]) for row in rows]


def get_job_status(job_id: str) -> dict[str, Any]:
    from ..services.jobs import get_job

    return get_job(job_id) or {"id": job_id, "status": "not_found"}


def get_logs(run_id: str, limit: int = 200) -> dict[str, Any]:
    run = _run(run_id)
    logs = query(
        "SELECT * FROM audit_logs WHERE entity_type = 'production_run' AND entity_id = ? ORDER BY created_at DESC LIMIT ?",
        (run_id, limit),
    )
    return {"run_id": run_id, "log": run.get("log"), "audit": logs}


def regenerate_failed_scenes(episode_id: str, actor: str = "user", confirm: bool = False) -> dict[str, Any]:
    if not confirm:
        raise ConfirmationRequired("Regenerating failed scenes requires explicit confirmation (confirm=true).")
    episode = episode_service.get_episode(episode_id)
    run = query_one(
        "SELECT * FROM production_runs WHERE episode_id = ? ORDER BY created_at DESC LIMIT 1",
        (episode_id,),
    )
    failed_scene_ids: list[str] = []
    if run:
        rows = query(
            "SELECT DISTINCT scene_id FROM production_tasks WHERE run_id = ? AND status = 'failed' AND scene_id IS NOT NULL",
            (run["id"],),
        )
        failed_scene_ids = [row["scene_id"] for row in rows]
    if not failed_scene_ids:
        failed_scene_ids = [
            row["scene_id"]
            for row in (episode.get("storyboard") or [])
            if row.get("scene_id")
        ]
    if not failed_scene_ids:
        raise ServiceError("No failed scenes were found for this episode.")
    plan = {"scenes": [{"scene_id": scene_id, "regenerate": True} for scene_id in failed_scene_ids], "assemble": True}
    return start_production(episode["project_id"], episode_id, plan=plan, actor=actor, confirm=True)


async def resume_pending_runs() -> None:
    rows = query("SELECT id, status FROM production_runs WHERE status IN ('running','paused')")
    for row in rows:
        execute(
            "UPDATE production_tasks SET status='pending', error='Resumed after application restart.', updated_at=? WHERE run_id=? AND status='running'",
            (now(), row["id"]),
        )
        _update_run(row["id"], status="running", state=SCENE_GENERATION)
        _ensure_worker(row["id"])
