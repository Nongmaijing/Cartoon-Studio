from __future__ import annotations

import random
import uuid
from typing import Any

from ..comfy.client import ComfyClient
from ..config import load_config
from . import character_service
from .audit_service import log
from .creative import character_negative_prompt, character_prompt
from .errors import ServiceError
from .generation import submit_image, upload_start_image
from .jobs import list_jobs
from .model_config_service import resolve_image_model

TURNAROUND_VIEWS = [
    ("front", "front"),
    ("three_quarter", "three-quarter"),
    ("side", "side profile"),
    ("back", "back"),
]
EXPRESSIONS = [
    "happy",
    "sad",
    "surprised",
    "curious",
    "excited",
    "worried",
    "angry",
    "sleepy",
]
POSES = [
    "standing",
    "walking",
    "running",
    "sitting",
    "jumping",
    "waving",
    "laughing",
    "thinking",
]
SHEET_KINDS = {"turnaround", "expressions", "poses"}


def _base_seed(seed: int | None) -> int:
    if seed is not None and seed >= 0:
        return int(seed)
    return random.randint(0, 2**32 - 1)


def _client(config: dict[str, Any]) -> ComfyClient:
    return ComfyClient(
        config["comfyui"]["server_url"],
        timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
    )


def _items_for(kind: str) -> list[tuple[str, str]]:
    if kind == "turnaround":
        return list(TURNAROUND_VIEWS)
    if kind == "expressions":
        return [(item, item) for item in EXPRESSIONS]
    if kind == "poses":
        return [(item, item) for item in POSES]
    raise ServiceError(f"Unknown character sheet kind '{kind}'.")


def _extra_prompt(kind: str) -> str:
    if kind == "turnaround":
        return "do not redesign, restyle or recolor the character; keep the saved design unchanged"
    if kind == "expressions":
        return (
            "same character, identical clothing and colors, head and shoulders portrait, "
            "one expression only, plain neutral background, no multiple views"
        )
    return (
        "same character, identical clothing and colors, full body, one pose only, "
        "plain neutral background, clear silhouette, no multiple views"
    )


async def generate_sheet(
    character_id: str,
    kind: str,
    *,
    reference_asset_id: str | None = None,
    allow_unapproved_reference: bool = False,
    seed: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    denoise: float = 0.45,
    width: int | None = None,
    height: int | None = None,
    architecture: str | None = None,
    checkpoint: str | None = None,
    vae: str | None = None,
    lora_name: str | None = None,
    lora_strength: float | None = None,
    actor: str = "user",
) -> dict[str, Any]:
    if kind not in SHEET_KINDS:
        raise ServiceError("Sheet kind must be turnaround, expressions or poses.")
    character = character_service.get_character(character_id)
    project_id = character.get("project_id")
    if not project_id:
        raise ServiceError("Character is not attached to a project.")
    character_model = character.get("model") or {}
    if not isinstance(character_model, dict):
        character_model = {}
    architecture = architecture or character_model.get("architecture")
    checkpoint = checkpoint or character_model.get("checkpoint")
    vae = vae or character_model.get("vae")
    lora_name = lora_name or character_model.get("lora_name")
    if lora_strength is None:
        lora_strength = character_model.get("lora_strength")
    if character_model.get("reference_strength") is not None:
        denoise = float(character_model["reference_strength"])
    elif character_model.get("denoise") is not None:
        denoise = float(character_model["denoise"])
    canonical = character.get("canonical_asset_id")
    reference = reference_asset_id or canonical
    if kind in ("expressions", "poses") and not reference:
        raise ServiceError(
            "A master reference image is required for expression and pose sheets. "
            "Set a canonical image or pass reference_asset_id."
        )
    approved = character.get("approval_status") == "approved"
    if reference and not approved and not allow_unapproved_reference:
        raise ServiceError(
            "The character's reference is not approved. Approve the character first, "
            "or pass allow_unapproved_reference=true to acknowledge that this is an unapproved reference.",
            status_code=409,
        )
    config = load_config()
    purpose = "character" if kind == "turnaround" else ("expression" if kind == "expressions" else "pose")
    model = resolve_image_model(
        config,
        architecture=architecture,
        purpose=purpose,
        input_image=bool(reference),
        explicit=bool(architecture),
    )
    input_image = None
    if reference:
        client = _client(config)
        input_image = await upload_start_image(config, client, reference, project_id)
    base_seed = _base_seed(seed)
    sheet_id = uuid.uuid4().hex[:12]
    preset = (
        "sdxl_portrait"
        if model["architecture"] == "sdxl" and kind == "poses"
        else f"{model['architecture']}_character"
    )
    jobs: list[dict[str, Any]] = []
    for label, prompt_label in _items_for(kind):
        composed = character_prompt(character, "reference" if kind == "turnaround" else kind, prompt_label, _extra_prompt(kind))
        job = await submit_image(
            project_id=project_id,
            prompt=composed,
            negative_prompt=character_negative_prompt("reference", label) if kind == "turnaround" else None,
            attach={
                "owner_type": "character",
                "owner_id": character_id,
                "role": "reference" if kind == "turnaround" else ("expression" if kind == "expressions" else "pose"),
                "label": label,
            },
            seed=base_seed,
            steps=steps,
            cfg=cfg,
            width=width,
            height=height,
            input_image=input_image,
            denoise=denoise if reference else None,
            architecture=architecture,
            purpose="character" if kind == "turnaround" else ("expression" if kind == "expressions" else "pose"),
            preset=preset,
            checkpoint=checkpoint,
            vae=vae,
            lora_name=lora_name,
            lora_strength=lora_strength,
            extra_params={"sheet_id": sheet_id, "sheet_kind": kind, "sheet_item": label},
        )
        jobs.append(job)
    log(
        actor,
        f"generate_character_{kind}",
        "character",
        character_id,
        {"sheet_id": sheet_id, "jobs": [job.get("id") for job in jobs], "reference_asset_id": reference},
    )
    return {
        "sheet_id": sheet_id,
        "character_id": character_id,
        "kind": kind,
        "reference_asset_id": reference,
        "reference_approved": approved if reference else None,
        "seed": base_seed,
        "jobs": jobs,
        "items": [
            {
                "label": label,
                "job_id": jobs[index].get("id"),
                "status": jobs[index].get("status"),
            }
            for index, (label, _) in enumerate(_items_for(kind))
            if index < len(jobs)
        ],
        "model": (jobs[0].get("model") if jobs else None),
    }


def get_sheet(character_id: str, sheet_id: str) -> dict[str, Any]:
    jobs = [
        job
        for job in list_jobs(limit=500)
        if (job.get("params") or {}).get("sheet_id") == sheet_id
        and ((job.get("params") or {}).get("attach") or {}).get("owner_id") == character_id
    ]
    jobs.sort(key=lambda item: item.get("created_at") or "")
    items = []
    for job in jobs:
        params = job.get("params") or {}
        items.append(
            {
                "label": params.get("sheet_item"),
                "job_id": job.get("id"),
                "status": job.get("status"),
                "progress": job.get("progress"),
                "error": job.get("error"),
                "outputs": job.get("outputs") or [],
            }
        )
    completed = bool(jobs) and all(job.get("status") == "completed" for job in jobs)
    failed = any(job.get("status") == "failed" for job in jobs)
    return {
        "sheet_id": sheet_id,
        "character_id": character_id,
        "kind": (jobs[0].get("params") or {}).get("sheet_kind") if jobs else None,
        "jobs": jobs,
        "items": items,
        "complete": completed,
        "failed": failed,
    }


def list_sheets(character_id: str, limit: int = 20) -> list[dict[str, Any]]:
    sheets: dict[str, dict[str, Any]] = {}
    for job in list_jobs(limit=500):
        params = job.get("params") or {}
        sheet_id = params.get("sheet_id")
        attach = params.get("attach") or {}
        if not sheet_id or attach.get("owner_id") != character_id:
            continue
        record = sheets.setdefault(
            sheet_id,
            {
                "sheet_id": sheet_id,
                "kind": params.get("sheet_kind"),
                "created_at": job.get("created_at"),
                "jobs": [],
            },
        )
        record["jobs"].append(
            {
                "job_id": job.get("id"),
                "label": params.get("sheet_item"),
                "status": job.get("status"),
                "progress": job.get("progress"),
                "error": job.get("error"),
            }
        )
    ordered = sorted(sheets.values(), key=lambda item: item.get("created_at") or "", reverse=True)
    return ordered[: max(1, min(limit, 100))]
