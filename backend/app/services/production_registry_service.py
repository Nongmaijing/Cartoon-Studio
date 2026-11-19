from __future__ import annotations

from typing import Any

from ..comfy.client import ComfyClient, ComfyError
from ..config import load_config
from ..workflows.registry import find_workflow
from . import llm_provider, model_config_service, resource_manager, speech_service, tts
from .engines import combo_options, detect_engines
from .workflow_checks import workflow_readiness


def _workflow_runnable(config: dict[str, Any], object_info: dict[str, Any], workflow_id: str) -> bool:
    entry = find_workflow(config, workflow_id)
    if not entry or entry.get("format") != "api" or not entry.get("valid"):
        return False
    if not object_info:
        return False
    try:
        return bool(workflow_readiness(config, entry, object_info)["runnable"])
    except Exception:  # noqa: BLE001 - readiness must never break the registry
        return False


def _checkpoint_options(object_info: dict[str, Any]) -> list[str]:
    spec = (((object_info.get("CheckpointLoaderSimple") or {}).get("input") or {}).get("required") or {}).get("ckpt_name")
    return [str(name) for name in combo_options(spec)]


def _inpaint_checkpoint(config: dict[str, Any], object_info: dict[str, Any]) -> str:
    configured = str(((config.get("models") or {}).get("checkpoints") or {}).get("sdxl_inpaint") or "")
    if configured and configured in _checkpoint_options(object_info):
        return configured
    for name in _checkpoint_options(object_info):
        lowered = name.lower()
        if "inpaint" in lowered and ("xl" in lowered or "sdxl" in lowered):
            return name
    return ""


def _node_names(object_info: dict[str, Any], *keywords: str) -> list[str]:
    lowered = [keyword.lower() for keyword in keywords]
    return sorted(
        name for name in object_info if any(keyword in name.lower() for keyword in lowered)
    )


def _loader_models(
    object_info: dict[str, Any],
    nodes: list[str],
    input_names: tuple[str, ...],
) -> list[str]:
    values: list[str] = []
    for node_name in nodes:
        node = object_info.get(node_name) or {}
        required = (node.get("input") or {}).get("required") or {}
        for input_name, spec in required.items():
            if input_name not in input_names:
                continue
            values.extend(combo_options(spec))
    return sorted(set(values))


def _has_weight(weights: list[str], *needles: str) -> bool:
    lowered = [value.lower() for value in weights]
    return any(any(needle in value for needle in needles) for value in lowered)


def _family(
    *,
    name: str,
    family: str,
    purpose: str,
    nodes: list[str],
    weights: list[str],
    required_nodes: list[str],
    required_weight_hints: tuple[str, ...],
    notes: str,
    license_note: str,
    source: str,
    vram: str,
    commercial: str,
) -> dict[str, Any]:
    nodes_available = bool(nodes)
    weights_available = _has_weight(weights, *required_weight_hints)
    if nodes_available and weights_available:
        status = "ready"
    elif nodes_available:
        status = "partial"
    else:
        status = "blocked"
    return {
        "name": name,
        "family": family,
        "purpose": purpose,
        "nodes_available": nodes_available,
        "weights_installed": weights_available,
        "status": status,
        "nodes": nodes[:20],
        "weight_files": weights[:20],
        "notes": notes,
        "source": source,
        "license": license_note,
        "vram": vram,
        "commercial_use": commercial,
    }


def recommendations() -> list[dict[str, Any]]:
    return [
        {
            "department": "video_generation",
            "name": "Wan 2.2 TI2V-5B",
            "source": "https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B",
            "license": "Apache 2.0 (verify the current model card)",
            "download_size": "~9.3 GB diffusion model + ~6.3 GB text encoder + ~1.3 GB VAE",
            "vram": "6 GB with aggressive offloading; very slow. 12 GB+ preferred.",
            "commercial_use": "Apache 2.0; verify model card",
            "status": "installed",
            "recommendation": "Use for low-resolution image-to-video tests; keep clips short on 6 GB.",
        },
        {
            "department": "video_generation",
            "name": "LTX-Video 0.9.x",
            "source": "https://huggingface.co/Lightricks/LTX-Video",
            "license": "OpenRAIL-M-style / verify exact model card",
            "download_size": "~4–12 GB depending on variant",
            "vram": "6–12 GB with offloading; faster than Wan",
            "commercial_use": "Verify current license terms",
            "status": "not_installed",
            "recommendation": "Best next video candidate for 6 GB experiments; nodes exist, weights missing.",
        },
        {
            "department": "video_generation",
            "name": "HunyuanVideo",
            "source": "https://huggingface.co/tencent/HunyuanVideo",
            "license": "Tencent Hunyuan Community License",
            "download_size": "~15–30 GB depending on precision",
            "vram": "24 GB+ preferred; not practical on 6 GB without heavy quantisation",
            "commercial_use": "License restrictions apply; verify",
            "status": "not_installed",
            "recommendation": "Mark experimental; not recommended for the 6 GB RTX 4050.",
        },
        {
            "department": "video_generation",
            "name": "CogVideoX-2B / 5B",
            "source": "https://huggingface.co/THUDM/CogVideoX-2b",
            "license": "Apache 2.0 (verify current model card)",
            "download_size": "~5–12 GB",
            "vram": "8–16 GB; 6 GB may require quantisation/offloading",
            "commercial_use": "Verify model card",
            "status": "not_installed",
            "recommendation": "Candidate for constrained-hardware experiments if nodes/weights are added.",
        },
        {
            "department": "image_editing",
            "name": "Qwen-Image-Edit",
            "source": "https://huggingface.co/Qwen/Qwen-Image-Edit",
            "license": "Apache 2.0 (verify model card)",
            "download_size": "Large (20B-class); quantised variants vary",
            "vram": "High; use quantised/offloaded variants or external hosting",
            "commercial_use": "Verify model card",
            "status": "not_installed",
            "recommendation": "Nodes exist in ComfyUI, local weights missing. Strong identity-preserving edit candidate.",
        },
        {
            "department": "image_editing",
            "name": "FLUX.1 Kontext [dev]",
            "source": "https://huggingface.co/black-forest-labs/FLUX.1-Kontext-dev",
            "license": "FLUX.1 [dev] Non-Commercial License",
            "download_size": "~12B-class; ~12–24 GB",
            "vram": "High; not practical on 6 GB without quantisation",
            "commercial_use": "Non-commercial; commercial use requires a license/API",
            "status": "not_installed",
            "recommendation": "Do not use for commercial production without a license. Nodes exist, weights missing.",
        },
        {
            "department": "upscaling",
            "name": "Real-ESRGAN x4plus",
            "source": "https://github.com/xinntao/Real-ESRGAN",
            "license": "BSD-3-Clause (code); verify weights",
            "download_size": "~64 MB",
            "vram": "2–4 GB",
            "commercial_use": "BSD-3-Clause code; verify weights",
            "status": "installed",
            "recommendation": "Installed and verified. Select the 'upscale_4x_real_esrgan' workflow to compare against 4x-UltraSharp.",
        },
        {
            "department": "upscaling",
            "name": "SUPIR",
            "source": "https://github.com/Fanghua-Yu/SUPIR",
            "license": "Apache 2.0 (code); verify weights",
            "download_size": "Several GB",
            "vram": "6 GB+ with offloading",
            "commercial_use": "Verify",
            "status": "not_installed",
            "recommendation": "Restoration candidate; may alter cartoon linework—test carefully.",
        },
        {
            "department": "voice_generation",
            "name": "Qwen3-TTS",
            "source": "https://huggingface.co/Qwen (verify exact Qwen3-TTS release)",
            "license": "Apache 2.0 (verify current model card)",
            "download_size": "Model-dependent",
            "vram": "CPU/GPU depending on variant",
            "commercial_use": "Verify",
            "status": "not_installed",
            "recommendation": "Candidate for multilingual character voices; verify exact release/license.",
        },
        {
            "department": "voice_generation",
            "name": "Chatterbox TTS",
            "source": "https://github.com/resemble-ai/chatterbox",
            "license": "MIT (verify current repository/model card)",
            "download_size": "Model-dependent",
            "vram": "CPU/GPU depending on variant",
            "commercial_use": "Verify",
            "status": "not_installed",
            "recommendation": "Expressive TTS candidate; test voice consistency before replacing Kokoro.",
        },
        {
            "department": "voice_generation",
            "name": "CosyVoice",
            "source": "https://github.com/FunAudioLLM/CosyVoice",
            "license": "Apache 2.0 (verify current model card)",
            "download_size": "Model-dependent",
            "vram": "CPU/GPU depending on variant",
            "commercial_use": "Verify",
            "status": "not_installed",
            "recommendation": "Multilingual candidate; more setup than Kokoro.",
        },
        {
            "department": "speech_recognition",
            "name": "faster-whisper",
            "source": "https://github.com/SYSTRAN/faster-whisper",
            "license": "MIT",
            "download_size": "~75 MB (tiny) to ~1.5 GB (medium)",
            "vram": "CPU or small GPU footprint",
            "commercial_use": "MIT",
            "status": "not_installed",
            "recommendation": "Recommended local ASR for subtitles, dialogue timing and lip-sync alignment.",
        },
        {
            "department": "sound_effects",
            "name": "AudioGen",
            "source": "https://github.com/facebookresearch/audiocraft",
            "license": "CC-BY-NC 4.0 weights (verify)",
            "download_size": "Model-dependent (~1–3 GB)",
            "vram": "4–8 GB",
            "commercial_use": "Non-commercial restrictions likely; verify",
            "status": "not_installed",
            "recommendation": "Research candidate; existing local synthesis covers basic SFX without a model download.",
        },
        {
            "department": "music",
            "name": "MusicGen",
            "source": "https://github.com/facebookresearch/audiocraft",
            "license": "CC-BY-NC 4.0 weights (verify)",
            "download_size": "~1–6 GB depending on size",
            "vram": "4–8 GB",
            "commercial_use": "Non-commercial restrictions likely; verify",
            "status": "not_installed",
            "recommendation": "Research candidate; current original local music synth remains the safe default.",
        },
        {
            "department": "music",
            "name": "ACE-Step",
            "source": "https://github.com/ace-step/ACE-Step",
            "license": "Apache 2.0 (verify current model card)",
            "download_size": "Several GB",
            "vram": "6 GB+ with offloading",
            "commercial_use": "Verify",
            "status": "not_installed",
            "recommendation": "Nodes exist in ComfyUI; weights missing. Candidate for longer music beds.",
        },
        {
            "department": "music",
            "name": "Stable Audio Open",
            "source": "https://huggingface.co/stabilityai/stable-audio-open-1.0",
            "license": "Stability AI Community License (verify)",
            "download_size": "~2–4 GB",
            "vram": "4–8 GB",
            "commercial_use": "License thresholds/restrictions apply; verify",
            "status": "not_installed",
            "recommendation": "SFX/music candidate; verify commercial terms.",
        },
        {
            "department": "character_consistency",
            "name": "IP-Adapter (SDXL)",
            "source": "https://github.com/cubiq/ComfyUI_IPAdapter_plus",
            "license": "Apache 2.0 (h94/IP-Adapter weights)",
            "download_size": "0.79 GB adapter + 3.44 GB ViT-H encoder",
            "vram": "Adds 1–2 GB",
            "commercial_use": "Apache 2.0; verify weights",
            "status": "installed",
            "recommendation": "Weights, ViT-H encoder and the ComfyUI_IPAdapter_plus node are installed. Select 'sdxl_ipadapter_identity' explicitly; it is not auto-selected.",
        },
        {
            "department": "character_consistency",
            "name": "ControlNet SDXL OpenPose",
            "source": "https://huggingface.co/xinsir/controlnet-openpose-sdxl-1.0",
            "license": "Apache 2.0",
            "download_size": "2.33 GB",
            "vram": "Adds 1–2 GB",
            "commercial_use": "Apache 2.0",
            "status": "installed",
            "recommendation": "Installed and wired into the SDXL pose path via 'sdxl_controlnet_pose'.",
        },
        {
            "department": "lip_sync",
            "name": "Wav2Lip / SadTalker / Rhubarb",
            "source": "Model-specific official repositories",
            "license": "Varies; several are research/non-commercial",
            "download_size": "Varies",
            "vram": "2–8 GB",
            "commercial_use": "Verify carefully",
            "status": "not_installed",
            "recommendation": "Lip-sync rendering is blocked. A viseme/lip-cue data layer can be built first without a model.",
        },
    ]


def _department(
    *,
    id: str,
    name: str,
    status: str,
    summary: str,
    installed: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": id,
        "name": name,
        "status": status,
        "summary": summary,
        "installed": installed,
        "missing": missing,
        "recommendations": recommendations,
    }


async def registry() -> dict[str, Any]:
    config = load_config()
    client = ComfyClient(
        config["comfyui"]["server_url"],
        timeout=float(config["comfyui"].get("request_timeout_seconds", 120)),
    )
    object_info: dict[str, Any] = {}
    comfy_error: str | None = None
    try:
        object_info = await client.object_info()
    except ComfyError as exc:
        comfy_error = str(exc)

    image_catalog = await model_config_service.catalog()
    resources = await resource_manager.snapshot()
    llm_health = await llm_provider.health()
    tts_status = await tts.detect_engines(config)
    engine_status = detect_engines(object_info) if object_info else {}

    checkpoints = image_catalog["models"].get("checkpoints", [])
    loras = image_catalog["models"].get("loras", [])
    controlnets = image_catalog["models"].get("controlnet", [])
    upscalers = image_catalog["models"].get("upscale_models", [])
    diffusion_weights = [
        entry["name"] for entry in image_catalog["models"].get("checkpoints", [])
    ] + [
        entry["name"]
        for entry in image_catalog["models"].get("upscale_models", [])
        if entry["category"] == "diffusion_models"
    ]
    # ComfyUI diffusion_models is not part of the image catalog; read it from object_info.
    diffusion_weights += _loader_models(object_info, ["UNETLoader"], ("unet_name",))
    all_weights = sorted(
        set(
            [entry["name"] for entry in checkpoints]
            + [entry["name"] for entry in upscalers]
            + diffusion_weights
        )
    )

    video_nodes = {
        "wan": _node_names(object_info, "Wan"),
        "ltx": _node_names(object_info, "LTX"),
        "hunyuan": _node_names(object_info, "Hunyuan"),
        "cogvideo": _node_names(object_info, "CogVideo"),
        "mochi": _node_names(object_info, "Mochi"),
    }
    video_families = [
        _family(
            name="Wan 2.2 TI2V-5B",
            family="Wan",
            purpose="Image-to-video and text-to-video",
            nodes=video_nodes["wan"],
            weights=all_weights,
            required_nodes=["Wan22ImageToVideoLatent", "KSampler", "VAEDecodeTiled", "CreateVideo", "SaveVideo"],
            required_weight_hints=("wan2.2",),
            notes="Installed. Very slow on 6 GB; short clips only.",
            license_note="Apache 2.0 (verify model card)",
            source="https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B",
            vram="6 GB with offloading; 12 GB+ preferred",
            commercial="Verify model card",
        ),
        _family(
            name="LTX-Video",
            family="LTX",
            purpose="Fast image/text-to-video",
            nodes=video_nodes["ltx"],
            weights=all_weights,
            required_nodes=["LTXVImgToVideo", "LTXVConditioning", "LTXVScheduler"],
            required_weight_hints=("ltx",),
            notes="Nodes present, weights not installed.",
            license_note="OpenRAIL-M-style; verify",
            source="https://huggingface.co/Lightricks/LTX-Video",
            vram="6–12 GB with offloading",
            commercial="Verify",
        ),
        _family(
            name="HunyuanVideo",
            family="Hunyuan",
            purpose="High-quality video generation",
            nodes=video_nodes["hunyuan"],
            weights=all_weights,
            required_nodes=["HunyuanImageToVideo", "EmptyHunyuanLatentVideo"],
            required_weight_hints=("hunyuan",),
            notes="Nodes present, weights not installed; too large for 6 GB in normal precision.",
            license_note="Tencent Hunyuan Community License",
            source="https://huggingface.co/tencent/HunyuanVideo",
            vram="24 GB+ preferred",
            commercial="License restrictions apply",
        ),
        _family(
            name="CogVideoX",
            family="CogVideoX",
            purpose="Constrained-hardware video experiments",
            nodes=video_nodes["cogvideo"],
            weights=all_weights,
            required_nodes=[],
            required_weight_hints=("cogvideo",),
            notes="Nodes missing; not installed.",
            license_note="Apache 2.0 (verify)",
            source="https://huggingface.co/THUDM/CogVideoX-2b",
            vram="8–16 GB",
            commercial="Verify",
        ),
        _family(
            name="Mochi 1",
            family="Mochi",
            purpose="High-quality video generation",
            nodes=video_nodes["mochi"],
            weights=all_weights,
            required_nodes=[],
            required_weight_hints=("mochi",),
            notes="Nodes present or optional; weights missing; not practical on 6 GB.",
            license_note="Apache 2.0 (verify)",
            source="https://huggingface.co/genmo/mochi-1-preview",
            vram="High",
            commercial="Verify",
        ),
    ]

    audio_nodes = {
        "ace": _node_names(object_info, "AceStep"),
        "stable": _node_names(object_info, "StableAudio"),
        "musicgen": _node_names(object_info, "MusicGen"),
        "audiogen": _node_names(object_info, "AudioGen"),
        "minimax": _node_names(object_info, "MiniMaxMusic"),
    }
    audio_families = [
        _family(
            name="ACE-Step",
            family="ACE-Step",
            purpose="Music generation",
            nodes=audio_nodes["ace"],
            weights=all_weights,
            required_nodes=["TextEncodeAceStepAudio", "EmptyAceStepLatentAudio"],
            required_weight_hints=("ace",),
            notes="Nodes present, weights missing.",
            license_note="Apache 2.0 (verify)",
            source="https://github.com/ace-step/ACE-Step",
            vram="6 GB+ with offloading",
            commercial="Verify",
        ),
        _family(
            name="Stable Audio",
            family="Stable Audio",
            purpose="SFX/music generation",
            nodes=audio_nodes["stable"],
            weights=all_weights,
            required_nodes=["ConditioningStableAudio", "EmptyLatentAudio"],
            required_weight_hints=("stable", "audio"),
            notes="Nodes present, weights missing.",
            license_note="Stability AI Community License (verify)",
            source="https://huggingface.co/stabilityai/stable-audio-open-1.0",
            vram="4–8 GB",
            commercial="License thresholds/restrictions apply",
        ),
        _family(
            name="MusicGen",
            family="MusicGen",
            purpose="Music generation",
            nodes=audio_nodes["musicgen"],
            weights=all_weights,
            required_nodes=[],
            required_weight_hints=("musicgen",),
            notes="Nodes missing/weights missing.",
            license_note="CC-BY-NC 4.0 weights (verify)",
            source="https://github.com/facebookresearch/audiocraft",
            vram="4–8 GB",
            commercial="Non-commercial restrictions likely",
        ),
        _family(
            name="AudioGen",
            family="AudioGen",
            purpose="Sound effect generation",
            nodes=audio_nodes["audiogen"],
            weights=all_weights,
            required_nodes=[],
            required_weight_hints=("audiogen",),
            notes="Nodes missing/weights missing. Existing local synthesis covers basic SFX.",
            license_note="CC-BY-NC 4.0 weights (verify)",
            source="https://github.com/facebookresearch/audiocraft",
            vram="4–8 GB",
            commercial="Non-commercial restrictions likely",
        ),
    ]

    edit_families = [
        _family(
            name="Qwen-Image-Edit",
            family="Qwen Image Edit",
            purpose="Reference-guided image editing",
            nodes=_node_names(object_info, "QwenImageEdit"),
            weights=all_weights,
            required_nodes=["TextEncodeQwenImageEdit"],
            required_weight_hints=("qwen",),
            notes="Nodes present, local weights missing.",
            license_note="Apache 2.0 (verify)",
            source="https://huggingface.co/Qwen/Qwen-Image-Edit",
            vram="High; quantised/offloaded variants needed",
            commercial="Verify",
        ),
        _family(
            name="FLUX Kontext",
            family="FLUX Kontext",
            purpose="Reference-guided image editing",
            nodes=_node_names(object_info, "Kontext"),
            weights=all_weights,
            required_nodes=["FluxKontextImageScale"],
            required_weight_hints=("flux", "kontext"),
            notes="Nodes present, weights missing; FLUX dev is non-commercial.",
            license_note="FLUX.1 [dev] Non-Commercial License",
            source="https://huggingface.co/black-forest-labs/FLUX.1-Kontext-dev",
            vram="High; not practical on 6 GB without quantisation",
            commercial="Non-commercial unless licensed",
        ),
    ]

    upscale_families = []
    for entry in upscalers:
        upscale_families.append(
            {
                "name": entry["name"],
                "family": "upscaler",
                "purpose": "Image upscaling/restoration",
                "status": "ready" if entry.get("installed_in_comfy") else "partial",
                "weights_installed": bool(entry.get("installed_in_comfy")),
                "size_gb": entry.get("size_gb"),
                "license": "Verify the upscaler model card",
                "vram": "2–4 GB",
                "notes": "4x-UltraSharp preserves line art better than generic photo upscalers; test for identity drift.",
            }
        )

    installed_tts = [
        {
            "name": engine.get("name") or engine.get("id"),
            "family": "TTS",
            "status": "ready" if engine.get("available") else "blocked",
            "notes": engine.get("notes") or "",
            "voices": len(engine.get("voices") or []),
            "executable": engine.get("executable") or "",
        }
        for engine in (tts_status.get("engines") or [])
    ]
    installed_llm = [
        {
            "name": model["name"],
            "family": model.get("family") or "LLM",
            "status": "ready",
            "capabilities": model.get("capabilities") or [],
            "size_gb": model.get("size_gb"),
            "parameter_size": model.get("parameter_size"),
        }
        for model in (llm_health.get("ollama", {}).get("models") or [])
    ]
    vision_models = [
        model for model in installed_llm if "vision" in (model.get("capabilities") or [])
    ]
    text_models = [
        model for model in installed_llm if "completion" in (model.get("capabilities") or [])
    ]

    image_status = "ready" if any(entry.get("architecture") == "sd15" and entry.get("installed_in_comfy") for entry in checkpoints) else "blocked"
    if image_catalog.get("active", {}).get("architecture") == "sdxl":
        image_status = "ready"
    elif any(entry.get("architecture") == "sdxl" and entry.get("installed_in_comfy") for entry in checkpoints):
        image_status = "partial"

    video_ready = [item for item in video_families if item["status"] == "ready"]
    video_partial = [item for item in video_families if item["status"] == "partial"]
    audio_ready = [item for item in audio_families if item["status"] == "ready"]
    audio_partial = [item for item in audio_families if item["status"] == "partial"]
    edit_partial = [item for item in edit_families if item["status"] == "partial"]

    img2img_ready = _workflow_runnable(config, object_info, "sdxl_img2img")
    inpaint_checkpoint = _inpaint_checkpoint(config, object_info)
    inpaint_nodes_ready = bool(object_info) and all(
        name in object_info
        for name in ("LoadImageMask", "VAEEncodeForInpaint", "VAEDecodeTiled")
    )
    inpaint_ready = bool(inpaint_checkpoint) and inpaint_nodes_ready
    vision_ready = bool(vision_models) or bool(llm_health.get("openai", {}).get("configured"))
    consistency_ready = img2img_ready and vision_ready
    speech = speech_service.availability()

    departments = [
        _department(
            id="image_generation",
            name="Image generation",
            status=image_status,
            summary=(
                "SD 1.5 is ready. SDXL is configured as the preferred architecture but no SDXL checkpoint is installed."
                if image_status != "ready"
                else "Image generation is ready."
            ),
            installed=[entry for entry in checkpoints if entry.get("installed_in_comfy")],
            missing=[item for item in image_catalog.get("missing", []) if item.get("kind") in ("checkpoint", "vae")],
            recommendations=image_catalog.get("recommendations", []),
        ),
        _department(
            id="image_editing",
            name="Image editing",
            status="ready" if (img2img_ready or inpaint_ready) else ("partial" if edit_partial else "blocked"),
            summary=(
                (
                    "SDXL whole-image editing is ready and masked editing uses the SDXL inpainting checkpoint. "
                    if inpaint_ready
                    else "SDXL whole-image editing is ready. Masked editing needs an SDXL inpainting checkpoint. "
                )
                + "Qwen-Image-Edit and FLUX Kontext are not installed and are listed as optional semantic editors."
                if (img2img_ready or inpaint_ready)
                else "No runnable edit workflow. Qwen-Image-Edit/FLUX Kontext weights are missing, and the SDXL img2img path is unavailable."
            ),
            installed=(
                [
                    {
                        "name": "SDXL whole-image edit (img2img)",
                        "family": "reference-guided edit",
                        "status": "ready" if img2img_ready else "blocked",
                    }
                ]
                + (
                    [
                        {
                            "name": f"SDXL masked inpainting ({inpaint_checkpoint})",
                            "family": "masked edit",
                            "status": "ready",
                        }
                    ]
                    if inpaint_ready
                    else []
                )
            )
            + [item for item in edit_families if item["status"] == "ready"],
            missing=[item for item in edit_families if item["status"] != "ready"],
            recommendations=[item for item in recommendations() if item["department"] == "image_editing"],
        ),
        _department(
            id="character_consistency",
            name="Character consistency",
            status="ready" if consistency_ready else "partial",
            summary=(
                "Reference-locked SDXL img2img and an automated identity check are available. "
                "SDXL ControlNet OpenPose is wired into the pose path, and IP-Adapter Plus "
                "identity conditioning is available as an explicit workflow."
                if consistency_ready
                else "Reference-locked img2img is available, but an automated identity check needs a local vision model. SDXL ControlNet and IP-Adapter weights are installed; pose conditioning is wired, IP-Adapter needs explicit workflow selection."
            ),
            installed=(
                [
                    {"name": "Canonical reference + img2img", "family": "reference conditioning", "status": "ready"},
                ]
                + (
                    [
                        {
                            "name": "Automated identity check (local VLM)",
                            "family": "visual consistency QA",
                            "status": "ready",
                        }
                    ]
                    if vision_ready
                    else []
                )
                + [
                    {"name": entry["name"], "family": "LoRA", "status": "ready", "size_gb": entry.get("size_gb")}
                    for entry in loras
                    if entry.get("installed_in_comfy")
                ]
                + [
                    {"name": entry["name"], "family": "ControlNet", "status": "ready", "size_gb": entry.get("size_gb")}
                    for entry in controlnets
                    if entry.get("installed_in_comfy")
                ]
            ),
            missing=(
                []
                if consistency_ready
                else [
                    item
                    for item in recommendations()
                    if item["department"] == "character_consistency" and item["status"] != "installed"
                ]
            ),
            recommendations=[item for item in recommendations() if item["department"] == "character_consistency"],
        ),
        _department(
            id="video_generation",
            name="Video generation",
            status="ready" if video_ready else ("partial" if video_partial else "blocked"),
            summary=(
                "Wan 2.2 is installed and usable for short low-resolution shots. "
                "LTX/Hunyuan/CogVideoX weights are not installed. Seven-minute episodes must use shot-based generation."
            ),
            installed=video_ready,
            missing=[item for item in video_families if item["status"] != "ready"],
            recommendations=[item for item in recommendations() if item["department"] == "video_generation"],
        ),
        _department(
            id="voice_generation",
            name="Voice generation",
            status="ready" if any(item["status"] == "ready" for item in installed_tts) else "blocked",
            summary=(
                "Kokoro/SAPI local voices are ready. Qwen3-TTS/Chatterbox/CosyVoice are not installed; "
                "Kokoro remains the production voice engine."
            ),
            installed=installed_tts,
            missing=[item for item in recommendations() if item["department"] == "voice_generation"],
            recommendations=[item for item in recommendations() if item["department"] == "voice_generation"],
        ),
        _department(
            id="speech_recognition",
            name="Speech recognition",
            status="ready" if speech["available"] else ("partial" if (speech["package_installed"] or speech["model_installed"]) else "blocked"),
            summary=(
                f"faster-whisper is installed with {speech['model_name']} "
                f"({speech['device']}/{speech['compute_type']}). Audio transcription, SRT export and "
                "audio-derived subtitle alignment are available."
                if speech["available"]
                else "faster-whisper or its local model is missing. Subtitle generation still works from the dialogue script, but audio transcription is unavailable."
            ),
            installed=(
                [
                    {
                        "name": f"faster-whisper ({speech['model_name']})",
                        "family": "ASR",
                        "status": "ready",
                        "device": speech["device"],
                    }
                ]
                if speech["available"]
                else []
            ),
            missing=(
                []
                if speech["available"]
                else [item for item in recommendations() if item["department"] == "speech_recognition"]
            ),
            recommendations=[item for item in recommendations() if item["department"] == "speech_recognition"],
        ),
        _department(
            id="sound_effects",
            name="Sound effects",
            status="ready",
            summary="Original local SFX synthesis is available (sparkle/chime) without a model download. AudioGen/Stable Audio weights are not installed.",
            installed=[
                {"name": "Local SFX synthesis", "family": "procedural audio", "status": "ready"},
            ],
            missing=[item for item in recommendations() if item["department"] == "sound_effects"],
            recommendations=[item for item in recommendations() if item["department"] == "sound_effects"],
        ),
        _department(
            id="music",
            name="Music",
            status="ready",
            summary="Original local music-bed synthesis is available. MusicGen/ACE-Step/Stable Audio weights are not installed.",
            installed=[
                {"name": "Local music synthesis", "family": "procedural audio", "status": "ready"},
            ],
            missing=[item for item in recommendations() if item["department"] == "music"],
            recommendations=[item for item in recommendations() if item["department"] == "music"],
        ),
        _department(
            id="language_model",
            name="Scriptwriting / LLM",
            status="ready" if text_models or llm_health.get("openai", {}).get("configured") else "blocked",
            summary=(
                "Local Ollama text models are available for story/script generation and continuity checks."
                if text_models
                else "No local text model detected; configure Ollama or OpenAI."
            ),
            installed=text_models,
            missing=[] if text_models else [{"name": "Ollama text model", "status": "blocked"}],
            recommendations=[],
        ),
        _department(
            id="visual_quality_control",
            name="Visual quality control",
            status="ready" if vision_models or llm_health.get("openai", {}).get("configured") else "blocked",
            summary=(
                "Local Qwen-VL models are available for structured visual review. AI review never auto-approves assets."
                if vision_models
                else "No local vision model detected; deterministic QC remains active."
            ),
            installed=vision_models,
            missing=[] if vision_models else [{"name": "Qwen-VL / vision model", "status": "blocked"}],
            recommendations=[],
        ),
        _department(
            id="upscaling",
            name="Upscaling / restoration",
            status="ready" if any(item["status"] == "ready" for item in upscale_families) else "blocked",
            summary="4x-UltraSharp is installed. Real-ESRGAN/SUPIR are not installed.",
            installed=upscale_families,
            missing=[item for item in recommendations() if item["department"] == "upscaling"],
            recommendations=[item for item in recommendations() if item["department"] == "upscaling"],
        ),
    ]

    ready = [department for department in departments if department["status"] == "ready"]
    partial = [department for department in departments if department["status"] == "partial"]
    blocked = [department for department in departments if department["status"] == "blocked"]

    return {
        "departments": departments,
        "summary": {
            "ready": len(ready),
            "partial": len(partial),
            "blocked": len(blocked),
            "total": len(departments),
            "ready_ids": [item["id"] for item in ready],
            "partial_ids": [item["id"] for item in partial],
            "blocked_ids": [item["id"] for item in blocked],
        },
        "resources": resources,
        "llm": llm_health,
        "tts": installed_tts,
        "image_catalog": image_catalog,
        "comfyui_nodes": {
            "video": video_nodes,
            "audio": audio_nodes,
            "engines": engine_status,
        },
        "comfyui_error": comfy_error,
        "recommendations": recommendations() + image_catalog.get("recommendations", []),
        "note": "Registry is read-only. No model is downloaded or installed automatically.",
    }
