from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..comfy.client import ComfyClient, ComfyError
from ..config import _deep_merge, default_config, load_config, save_config
from ..workflows.registry import find_workflow
from . import model_download_service
from .engines import combo_options

MODEL_CATEGORIES = ("checkpoints", "vae", "loras", "controlnet", "upscale_models")
MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin"}

SDXL_HINTS = (
    "sdxl",
    "sd_xl",
    "sd-xl",
    "xl_base",
    "xl-base",
    "juggernautxl",
    "dreamshaperxl",
    "bluepencilxl",
    "realvisxl",
    "pony",
    "illustrious",
    "noobai",
    "animagine",
    "kohaku",
    "counterfeitxl",
    "playground-v2",
    "sdxl-turbo",
    "zavychromaxl",
)
SD15_HINTS = (
    "sd15",
    "sd_15",
    "v1-5",
    "v1.5",
    "dreamshaper_8",
    "toonyou",
    "anything",
    "revanimated",
    "deliberate",
    "realisticvision",
    "majicmix",
    "meinamix",
)
WAN_HINTS = ("wan2", "wan_2", "wan22")
FLUX_HINTS = ("flux",)

RECOMMENDATIONS: list[dict[str, Any]] = [
    {
        "name": "SDXL Base 1.0",
        "filename_hints": ["sd_xl_base_1.0", "sdxl_base"],
        "category": "checkpoints",
        "source": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0",
        "architecture": "SDXL 1.0",
        "intended_use": "General SDXL base model. Use with a cartoon/illustration style LoRA for Western 2D characters.",
        "license": "CreativeML Open RAIL++-M",
        "license_notes": "Commercial use permitted subject to the use-based restrictions in the license. Review the model card before use.",
        "download_size": "~6.9 GB fp16 safetensors",
        "vram": "8-10 GB recommended; 6 GB requires low-VRAM mode and tiled VAE",
        "compatibility": "Native ComfyUI SDXL support; no custom nodes required for txt2img/img2img",
        "cartoon_suitability": "Moderate. General-purpose base; style comes from the prompt and a cartoon LoRA.",
        "reference_conditioning": "img2img works. SDXL ControlNet/IPAdapter need separate model files.",
        "status": "not_installed",
    },
    {
        "name": "DreamShaper XL",
        "filename_hints": ["dreamshaperxl", "dreamshaper_xl", "dreamshaper xl"],
        "category": "checkpoints",
        "source": "https://civitai.com/models/112902 (verify current version and license on the model page)",
        "architecture": "SDXL fine-tune",
        "intended_use": "Versatile stylized illustration and character art; a practical first SDXL test model.",
        "license": "CreativeML Open RAIL++-M (verify the exact version on the model page)",
        "license_notes": "Check the model card for commercial-use terms and any additional restrictions before production use.",
        "download_size": "~6.5-7 GB",
        "vram": "6-8 GB with low-VRAM mode and tiled VAE; 8+ GB preferred",
        "compatibility": "Native ComfyUI SDXL support; no custom nodes required",
        "cartoon_suitability": "Good for stylized illustration; may need prompt tuning for clean Western TV outlines.",
        "reference_conditioning": "img2img works; SDXL ControlNet requires an SDXL-compatible ControlNet model.",
        "status": "not_installed",
    },
    {
        "name": "Blue Pencil XL",
        "filename_hints": ["bluepencil", "blue_pencil", "blue-pencil"],
        "category": "checkpoints",
        "source": "https://civitai.com/models/119012 (verify current version and license on the model page)",
        "architecture": "SDXL illustration fine-tune",
        "intended_use": "Line-art and illustration-oriented SDXL model; useful for clean outlines and concept art.",
        "license": "CreativeML Open RAIL++-M (verify the exact version on the model page)",
        "license_notes": "Check the model card for commercial-use terms before production use.",
        "download_size": "~6.5 GB",
        "vram": "6-8 GB with low-VRAM mode and tiled VAE",
        "compatibility": "Native ComfyUI SDXL support; no custom nodes required",
        "cartoon_suitability": "Good for line-heavy illustration; test color/flatness prompts for TV-cartoon output.",
        "reference_conditioning": "img2img works; SDXL ControlNet/IPAdapter need separate models.",
        "status": "not_installed",
    },
    {
        "name": "Juggernaut XL",
        "filename_hints": ["juggernautxl", "juggernaut_xl", "juggernaut xl"],
        "category": "checkpoints",
        "source": "https://civitai.com/models/133005 (verify current version and license on the model page)",
        "architecture": "SDXL fine-tune",
        "intended_use": "High-detail general model; useful as a quality/comparison baseline, less suited to flat 2D cartoons.",
        "license": "CreativeML Open RAIL++-M (verify the exact version on the model page)",
        "license_notes": "Check the model card for commercial-use terms before production use.",
        "download_size": "~6.5-7 GB",
        "vram": "8 GB preferred; 6 GB requires low-VRAM mode and tiled VAE",
        "compatibility": "Native ComfyUI SDXL support; no custom nodes required",
        "cartoon_suitability": "Low-moderate; tends toward detailed/photoreal rendering. Use only as a comparison.",
        "reference_conditioning": "img2img works; SDXL ControlNet requires a compatible model.",
        "status": "not_installed",
    },
    {
        "name": "Cartoon style SDXL LoRA (choose a model card with clear commercial terms)",
        "filename_hints": ["cartoon", "toon", "animation"],
        "category": "loras",
        "source": "Civitai / Hugging Face (model-specific)",
        "architecture": "SDXL LoRA",
        "intended_use": "Adds a consistent Western 2D cartoon style on top of SDXL Base or an SDXL fine-tune.",
        "license": "Varies by model card",
        "license_notes": "Do not assume commercial use. Check the LoRA license and training-data notes before production.",
        "download_size": "Typically 100-300 MB",
        "vram": "Minimal overhead; keep batch size 1 on 6 GB",
        "compatibility": "Requires ComfyUI LoraLoader; no extra custom nodes",
        "cartoon_suitability": "Potentially high; verify on your own character prompts.",
        "reference_conditioning": "Use with img2img; LoRA stacking is supported by the workflow injector.",
        "status": "not_installed",
    },
]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safetensors_metadata(path: Path) -> dict[str, Any]:
    """Read only the small safetensors JSON header; never load tensor data."""
    if path.suffix.lower() != ".safetensors":
        return {}
    try:
        with path.open("rb") as handle:
            length_bytes = handle.read(8)
            if len(length_bytes) != 8:
                return {}
            header_len = int.from_bytes(length_bytes, "little")
            if header_len <= 0 or header_len > 10_000_000:
                return {}
            header = json.loads(handle.read(header_len).decode("utf-8"))
            metadata = header.get("__metadata__") or {}
            return metadata if isinstance(metadata, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _metadata_architecture(metadata: dict[str, Any]) -> tuple[str | None, str | None]:
    if not metadata:
        return None, None
    values = " ".join(str(value) for value in metadata.values()).lower()
    base = str(metadata.get("ss_base_model_version") or "").lower()
    spec = str(metadata.get("modelspec.architecture") or "").lower()
    module = str(metadata.get("ss_network_module") or "").lower()
    joined = f"{values} {base} {spec} {module}"
    if "sdxl" in joined or "stable-diffusion-xl" in joined or "sd_xl" in joined:
        return "sdxl", "metadata"
    if "sd_v1" in joined or "stable-diffusion-v1" in joined or "sd1.5" in joined:
        return "sd15", "metadata"
    if "flux" in joined:
        return "flux", "metadata"
    if "wan2" in joined or "wan_2" in joined:
        return "wan", "metadata"
    return None, None


def _filename_architecture(name: str) -> tuple[str | None, str | None]:
    lowered = name.lower()
    if any(hint in lowered for hint in SDXL_HINTS):
        return "sdxl", "filename"
    if any(hint in lowered for hint in SD15_HINTS):
        return "sd15", "filename"
    if any(hint in lowered for hint in WAN_HINTS):
        return "wan", "filename"
    if any(hint in lowered for hint in FLUX_HINTS):
        return "flux", "filename"
    return None, None


def detect_architecture(path: Path | None, name: str, category: str) -> dict[str, Any]:
    """Best-effort architecture detection with an explicit confidence and source."""
    size_bytes = path.stat().st_size if path and path.exists() else 0
    metadata = _safetensors_metadata(path) if path and path.exists() else {}
    architecture, source = _metadata_architecture(metadata)
    confidence = "high" if architecture else "low"
    if not architecture:
        architecture, source = _filename_architecture(name)
        confidence = "high" if architecture else "low"
    if not architecture and category == "checkpoints":
        if size_bytes >= 4_000_000_000:
            architecture, source, confidence = "sdxl", "size", "medium"
        elif 1_200_000_000 <= size_bytes <= 3_600_000_000:
            architecture, source, confidence = "sd15", "size", "medium"
    detail = {
        "metadata": "Detected from safetensors metadata.",
        "filename": "Detected from the filename; verify the model card.",
        "size": "Inferred from file size; verify the model card.",
    }.get(source or "", "Architecture is not labeled; verify the model card.")
    return {
        "architecture": architecture or "unknown",
        "confidence": confidence,
        "source": source or "unknown",
        "detail": detail,
        "size_bytes": size_bytes,
        "metadata": {
            key: metadata.get(key)
            for key in (
                "ss_base_model_version",
                "modelspec.architecture",
                "ss_network_module",
                "ss_network_dim",
                "ss_network_alpha",
            )
            if metadata.get(key)
        },
    }


def _model_dirs(config: dict[str, Any]) -> list[Path]:
    values: list[Path] = []
    for value in config.get("comfyui", {}).get("models_dirs") or []:
        if value:
            values.append(Path(value))
    install = config.get("comfyui", {}).get("install_path")
    if install:
        values.append(Path(install) / "models")
    seen: set[str] = set()
    result: list[Path] = []
    for path in values:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def _scan_category(config: dict[str, Any], category: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for base in _model_dirs(config):
        directory = base / category
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in MODEL_EXTENSIONS:
                continue
            key = str(path.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            detection = detect_architecture(path, path.name, category)
            entries.append(
                {
                    "name": path.name,
                    "relative_path": str(path.relative_to(directory)).replace("\\", "/"),
                    "path": str(path),
                    "category": category,
                    "size_bytes": detection["size_bytes"],
                    "size_gb": round(detection["size_bytes"] / (1024**3), 2) if detection["size_bytes"] else None,
                    "architecture": detection["architecture"],
                    "confidence": detection["confidence"],
                    "detection_source": detection["source"],
                    "detection_detail": detection["detail"],
                    "metadata": detection["metadata"],
                    "installed_in_comfy": False,
                    "modified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime)),
                }
            )
    entries.sort(key=lambda item: item["name"].lower())
    return entries


def _comfy_options(object_info: dict[str, Any], category: str) -> list[str]:
    mapping = {
        "checkpoints": ("CheckpointLoaderSimple", "ckpt_name"),
        "vae": ("VAELoader", "vae_name"),
        "loras": ("LoraLoader", "lora_name"),
        "controlnet": ("ControlNetLoader", "control_net_name"),
        "upscale_models": ("UpscaleModelLoader", "model_name"),
    }
    class_type, input_name = mapping.get(category, ("", ""))
    node = object_info.get(class_type) or {}
    spec = ((node.get("input") or {}).get("required") or {}).get(input_name)
    return combo_options(spec)


def _merge_comfy_options(
    entries: list[dict[str, Any]],
    options: list[str],
    category: str,
) -> list[dict[str, Any]]:
    known = {entry["name"] for entry in entries}
    result = list(entries)
    for name in options:
        if name in known:
            continue
        detection = detect_architecture(None, name, category)
        result.append(
            {
                "name": name,
                "relative_path": None,
                "path": None,
                "category": category,
                "size_bytes": None,
                "size_gb": None,
                "architecture": detection["architecture"],
                "confidence": detection["confidence"],
                "detection_source": detection["source"],
                "detection_detail": detection["detail"],
                "metadata": {},
                "installed_in_comfy": True,
                "modified_at": None,
            }
        )
    for entry in result:
        entry["installed_in_comfy"] = entry["name"] in options
        architecture = entry["architecture"]
        entry["compatible_engines"] = (
            ["sdxl"] if architecture == "sdxl" else ["sd15"] if architecture == "sd15" else []
        )
    result.sort(key=lambda item: item["name"].lower())
    return result


def get_model_config() -> dict[str, Any]:
    config = load_config()
    defaults = default_config()["models"]
    return _deep_merge(defaults, config.get("models") or {})


def save_model_config(payload: dict[str, Any]) -> dict[str, Any]:
    current = load_config()
    merged = _deep_merge(current, {"models": payload})
    saved = save_config(merged)
    return saved.get("models") or get_model_config()


def configured_checkpoint(config: dict[str, Any], engine: str) -> str:
    models = config.get("models") or {}
    return str((models.get("checkpoints") or {}).get(engine) or "")


def _workflow_exists(config: dict[str, Any], workflow_id: str) -> bool:
    if not workflow_id:
        return False
    entry = find_workflow(config, workflow_id)
    return bool(entry and entry.get("format") == "api" and entry.get("valid"))


def _workflow_matches(
    config: dict[str, Any],
    workflow_id: str,
    architecture: str,
) -> bool:
    if not workflow_id:
        return False
    entry = find_workflow(config, workflow_id)
    if not entry or entry.get("format") != "api" or not entry.get("valid"):
        return False
    engine = str(entry.get("engine") or "")
    return engine == architecture


def _workflow_for(
    config: dict[str, Any],
    models: dict[str, Any],
    architecture: str,
    purpose: str,
    input_image: bool,
) -> str:
    key = "scene"
    if purpose == "background":
        key = "background"
    elif purpose == "character":
        key = "character_img2img" if input_image else "character_txt2img"
    elif purpose == "expression":
        key = "expression"
    elif purpose == "pose":
        key = "pose"
    elif input_image:
        key = "img2img"
    workflow_id = str((models.get("workflows") or {}).get(key) or "")
    if _workflow_matches(config, workflow_id, architecture):
        return workflow_id
    if architecture == "sdxl":
        fallbacks = ["sdxl_img2img" if input_image else "sdxl_txt2img"]
        if purpose == "character":
            fallbacks.insert(0, "sdxl_character_turnaround" if not input_image else "sdxl_img2img")
        if purpose == "background":
            fallbacks.insert(0, "sdxl_background")
        if purpose == "expression":
            fallbacks.insert(0, "sdxl_character_expression")
        if purpose == "pose":
            fallbacks.insert(0, "sdxl_character_pose")
    else:
        fallbacks = ["sd15_img2img" if input_image else "sd15_txt2img"]
    for candidate in fallbacks:
        if _workflow_matches(config, candidate, architecture):
            return candidate
    return ""


def resolve_image_model(
    config: dict[str, Any],
    *,
    architecture: str | None = None,
    purpose: str = "scene",
    input_image: bool = False,
    explicit: bool = False,
    preset: str | None = None,
) -> dict[str, Any]:
    models = _deep_merge(default_config()["models"], config.get("models") or {})
    requested = (architecture or models.get("default_architecture") or "sdxl").lower()
    if requested not in ("sdxl", "sd15"):
        requested = "sdxl"
    checkpoints = models.get("checkpoints") or {}
    checkpoint = str(checkpoints.get(requested) or "")
    fallback_reason: str | None = None
    resolved = requested
    if not checkpoint:
        if explicit:
            raise ValueError(
                f"No {requested.upper()} checkpoint is configured. "
                "Install a checkpoint and select it in Model Studio."
            )
        resolved = "sd15" if requested == "sdxl" else "sdxl"
        checkpoint = str(checkpoints.get(resolved) or "")
        fallback_reason = (
            f"No {requested.upper()} checkpoint configured; using {resolved.upper()}."
        )
        if not checkpoint:
            raise ValueError("No image checkpoint is configured. Select one in Model Studio.")
    vae_map = models.get("vae") or {}
    vae = str(vae_map.get(resolved) or "")
    lora = models.get("lora") or {}
    lora_name = str(lora.get("name") or "")
    lora_architecture = str(lora.get("architecture") or "")
    lora_skipped_reason: str | None = None
    if lora_name and lora_architecture and lora_architecture != resolved:
        lora_skipped_reason = (
            f"LoRA '{lora_name}' targets {lora_architecture.upper()} but the active model is "
            f"{resolved.upper()}; the LoRA was not applied."
        )
        lora_name = ""
    lora_strength = _safe_float(lora.get("strength"), 0.8)
    preset_key = preset or f"{resolved}_{purpose}"
    presets = models.get("presets") or {}
    preset_values = presets.get(preset_key) or presets.get(f"{resolved}_character") or presets.get(f"{resolved}_scene") or {}
    workflow_id = _workflow_for(config, models, resolved, purpose, input_image)
    if not workflow_id:
        raise ValueError(
            f"No runnable {resolved.upper()} {'image-to-image' if input_image else 'text-to-image'} workflow is available."
        )
    return {
        "architecture": resolved,
        "requested_architecture": requested,
        "checkpoint": checkpoint,
        "vae": vae,
        "lora_name": lora_name,
        "lora_strength": lora_strength,
        "lora_skipped_reason": lora_skipped_reason,
        "workflow_id": workflow_id,
        "preset": preset_values,
        "preset_key": preset_key,
        "low_vram": bool(models.get("low_vram", True)),
        "tiled_vae": bool(models.get("tiled_vae", True)),
        "batch_size": 1,
        "max_pixels": int(models.get("max_pixels") or 1250000),
        "fallback_reason": fallback_reason,
    }


def apply_model_to_params(params: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    params.setdefault("checkpoint", model["checkpoint"])
    if model.get("vae"):
        params.setdefault("vae", model["vae"])
    if model.get("lora_name"):
        params.setdefault("lora_name", model["lora_name"])
        params.setdefault("lora_strength", model["lora_strength"])
    for key in ("width", "height", "steps", "cfg", "sampler", "scheduler"):
        value = (model.get("preset") or {}).get(key)
        if value is not None:
            params.setdefault(key, value)
    if model.get("architecture") == "sdxl":
        params["batch_size"] = 1
    else:
        params.setdefault("batch_size", 1)
    params["model_architecture"] = model["architecture"]
    params["model_checkpoint"] = model["checkpoint"]
    params["model_workflow"] = model["workflow_id"]
    if model.get("fallback_reason"):
        params["model_fallback"] = model["fallback_reason"]
    if model.get("lora_skipped_reason"):
        params["lora_skipped_reason"] = model["lora_skipped_reason"]
    return params


def validate_dimensions(model: dict[str, Any], width: int, height: int) -> None:
    if model.get("architecture") != "sdxl":
        return
    pixels = max(1, int(width)) * max(1, int(height))
    limit = int(model.get("max_pixels") or 1250000)
    if pixels > limit:
        raise ValueError(
            f"SDXL request {width}x{height} is {pixels:,} pixels, above the 6 GB safe budget "
            f"of {limit:,}. Use 1024x1024, 832x1216, 1216x832, or 1152x896."
        )


def _gpu_summary(stats: dict[str, Any]) -> dict[str, Any]:
    device = (stats.get("devices") or [{}])[0]
    total = int(device.get("vram_total") or 0)
    free = int(device.get("vram_free") or 0)
    return {
        "name": device.get("name") or "",
        "type": device.get("type") or "",
        "vram_total": total,
        "vram_free": free,
        "vram_used": max(0, total - free),
        "vram_total_gb": round(total / (1024**3), 2) if total else None,
        "vram_free_gb": round(free / (1024**3), 2) if free else None,
    }


def _comfy_summary(stats: dict[str, Any], connected: bool, error: str | None) -> dict[str, Any]:
    system = stats.get("system") or {}
    argv = [str(item) for item in (system.get("argv") or [])]
    lowered = " ".join(argv).lower()
    flags = {
        "lowvram": "--lowvram" in lowered,
        "novram": "--novram" in lowered,
        "highvram": "--highvram" in lowered,
        "normalvram": "--normalvram" in lowered,
        "smart_memory_disabled": "--disable-smart-memory" in lowered,
        "pytorch_cross_attention": "--use-pytorch-cross-attention" in lowered,
        "split_cross_attention": "--use-split-cross-attention" in lowered,
        "flash_attention": "--use-flash-attention" in lowered,
    }
    return {
        "connected": connected,
        "error": error,
        "version": system.get("comfyui_version"),
        "python": system.get("python_version"),
        "pytorch": system.get("pytorch_version"),
        "argv": argv,
        "flags": flags,
        "low_vram_mode": bool(
            flags["lowvram"] or flags["novram"] or flags["normalvram"]
        ),
        "attention_optimized": bool(
            flags["pytorch_cross_attention"]
            or flags["split_cross_attention"]
            or flags["flash_attention"]
        ),
    }


def _missing_dependencies(
    config: dict[str, Any],
    models: dict[str, Any],
    entries: dict[str, list[dict[str, Any]]],
    options: dict[str, list[str]],
    comfy: dict[str, Any],
) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    sdxl_checkpoint = str((models.get("checkpoints") or {}).get("sdxl") or "")
    sdxl_installed = [
        entry for entry in entries.get("checkpoints", []) if entry["architecture"] == "sdxl"
    ]
    if not sdxl_checkpoint:
        missing.append(
            {
                "kind": "checkpoint",
                "severity": "blocking",
                "message": "No SDXL checkpoint is selected. SDXL character production will fall back to SD 1.5.",
                "action": "Install an SDXL checkpoint, then select it in Model Studio.",
            }
        )
    elif sdxl_checkpoint not in options.get("checkpoints", []):
        missing.append(
            {
                "kind": "checkpoint",
                "severity": "blocking",
                "message": f"Selected SDXL checkpoint '{sdxl_checkpoint}' is not available in ComfyUI.",
                "action": "Check the model path/refresh ComfyUI, or select another checkpoint.",
            }
        )
    if not sdxl_installed:
        missing.append(
            {
                "kind": "checkpoint",
                "severity": "info",
                "message": "No downloaded file was detected with an SDXL signature.",
                "action": "Review the recommendations and install a model manually; nothing is downloaded automatically.",
            }
        )
    sdxl_vae = str((models.get("vae") or {}).get("sdxl") or "")
    if not sdxl_vae:
        missing.append(
            {
                "kind": "vae",
                "severity": "info",
                "message": "No external SDXL VAE selected. The checkpoint's baked VAE will be used.",
                "action": "Optional: install an SDXL VAE (for example madebyollin/sdxl-vae-fp16-fix) and select it.",
            }
        )
    lora_name = str((models.get("lora") or {}).get("name") or "")
    if lora_name and lora_name not in options.get("loras", []):
        missing.append(
            {
                "kind": "lora",
                "severity": "blocking",
                "message": f"Selected LoRA '{lora_name}' is not available in ComfyUI.",
                "action": "Install the LoRA manually or select another LoRA.",
            }
        )
    sdxl_controlnet = [
        entry for entry in entries.get("controlnet", []) if entry["architecture"] == "sdxl"
    ]
    if not sdxl_controlnet:
        missing.append(
            {
                "kind": "controlnet",
                "severity": "info",
                "message": "No SDXL ControlNet model detected. Pose/expression generation uses img2img reference conditioning.",
                "action": "Optional: install an SDXL-compatible ControlNet model; no download is performed automatically.",
            }
        )
    if not comfy.get("connected"):
        missing.append(
            {
                "kind": "comfyui",
                "severity": "blocking",
                "message": "ComfyUI is not reachable; live model compatibility cannot be checked.",
                "action": "Start ComfyUI and refresh the catalog.",
            }
        )
    elif not comfy.get("low_vram_mode") and (comfy.get("gpu") or {}).get("vram_total_gb", 0) and (comfy.get("gpu") or {}).get("vram_total_gb", 0) < 8:
        missing.append(
            {
                "kind": "vram",
                "severity": "warning",
                "message": "ComfyUI is not running with an explicit low-VRAM flag; SDXL may OOM on this 6 GB GPU.",
                "action": "Restart ComfyUI with --lowvram (or --normalvram) and keep tiled VAE enabled.",
            }
        )
    if not models.get("tiled_vae", True):
        missing.append(
            {
                "kind": "vram",
                "severity": "warning",
                "message": "Tiled VAE decoding is disabled in Model Studio.",
                "action": "Enable tiled VAE for 6 GB SDXL generation.",
            }
        )
    for key in ("character_txt2img", "character_img2img", "background", "scene"):
        workflow_id = str((models.get("workflows") or {}).get(key) or "")
        if not _workflow_exists(config, workflow_id):
            missing.append(
                {
                    "kind": "workflow",
                    "severity": "warning",
                    "message": f"Configured {key} workflow '{workflow_id or 'none'}' is missing or invalid.",
                    "action": "Select a valid workflow in Model Studio or restore the workflow file.",
                }
            )
    return missing


async def catalog() -> dict[str, Any]:
    config = load_config()
    models = get_model_config()
    connected = False
    error: str | None = None
    object_info: dict[str, Any] = {}
    stats: dict[str, Any] = {}
    client = ComfyClient(
        config["comfyui"]["server_url"],
        timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
    )
    try:
        object_info = await client.object_info()
        stats = await client.system_stats()
        connected = True
    except ComfyError as exc:
        error = str(exc)

    options = {category: _comfy_options(object_info, category) for category in MODEL_CATEGORIES}
    entries: dict[str, list[dict[str, Any]]] = {}
    for category in MODEL_CATEGORIES:
        entries[category] = _merge_comfy_options(
            _scan_category(config, category),
            options.get(category, []),
            category,
        )

    comfy = _comfy_summary(stats, connected, error)
    comfy["gpu"] = _gpu_summary(stats)
    try:
        resolved = resolve_image_model(config, purpose="character")
    except ValueError as exc:
        resolved = {
            "architecture": "unknown",
            "checkpoint": "",
            "workflow_id": "",
            "fallback_reason": str(exc),
        }
    recommendations = []
    checkpoint_entries = entries.get("checkpoints", [])
    lora_entries = entries.get("loras", [])
    for item in RECOMMENDATIONS:
        record = dict(item)
        pool = lora_entries if item.get("category") == "loras" else checkpoint_entries
        matches = [
            entry
            for entry in pool
            if any(hint in entry["name"].lower() for hint in item.get("filename_hints", []))
        ]
        record["installed"] = bool(matches)
        record["installed_file"] = matches[0]["name"] if matches else None
        record["status"] = "installed" if matches else "not_installed"
        record["download"] = model_download_service.describe(item["name"])
        recommendations.append(record)

    return {
        "config": models,
        "active": resolved,
        "comfyui": comfy,
        "models": entries,
        "missing": _missing_dependencies(config, models, entries, options, comfy),
        "recommendations": recommendations,
        "model_dirs": [str(path) for path in _model_dirs(config)],
        "note": (
            "Nothing downloads automatically. Model Studio only downloads a vetted source after "
            "you confirm its licence and storage location."
        ),
    }
