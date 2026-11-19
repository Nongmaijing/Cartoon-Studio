from __future__ import annotations

from app.config import load_config
from app.services.conditioning import (
    controlnet_model,
    controlnet_workflow_id,
    ipadapter_workflow_id,
    prefer_ipadapter,
    resolve_image_mode,
)
from app.workflows.registry import find_workflow, load_workflow


def _runnable(workflow_id: str) -> dict:
    config = load_config()
    entry = find_workflow(config, workflow_id)
    assert entry is not None, f"{workflow_id} is missing"
    assert entry["format"] == "api"
    assert entry["valid"], entry["errors"]
    return entry


def test_sdxl_controlnet_workflow_matches_architecture():
    entry = _runnable("sdxl_controlnet_pose")
    assert entry["engine"] == "sdxl"
    assert entry["kind"] == "image"
    assert {"input_image", "control_net_name", "control_strength"} <= set(entry["roles"])


def test_sdxl_controlnet_graph_uses_loader_and_apply_nodes():
    loaded = load_workflow(load_config(), "sdxl_controlnet_pose")
    classes = {node["class_type"] for node in loaded["api"].values()}
    assert {"ControlNetLoader", "ControlNetApplyAdvanced", "CheckpointLoaderSimple"} <= classes
    assert loaded["mapping"]["engine"] == "sdxl"


def test_ipadapter_workflow_is_valid_and_uses_adapter_nodes():
    entry = _runnable("sdxl_ipadapter_identity")
    assert entry["engine"] == "sdxl"
    assert "input_image" in entry["roles"]
    loaded = load_workflow(load_config(), "sdxl_ipadapter_identity")
    classes = {node["class_type"] for node in loaded["api"].values()}
    assert {"IPAdapterUnifiedLoader", "IPAdapterAdvanced"} <= classes


def test_real_esrgan_upscale_workflow_is_valid():
    entry = _runnable("upscale_4x_real_esrgan")
    assert entry["kind"] == "image"
    assert {"input_image", "upscale_model"} <= set(entry["roles"])
    loaded = load_workflow(load_config(), "upscale_4x_real_esrgan")
    loader = next(
        node for node in loaded["api"].values() if node["class_type"] == "UpscaleModelLoader"
    )
    assert loader["inputs"]["model_name"] == "RealESRGAN_x4plus.pth"


def test_controlnet_workflow_selection_follows_architecture():
    config = load_config()
    assert controlnet_workflow_id(config, "sdxl") == "sdxl_controlnet_pose"
    assert controlnet_workflow_id(config, "sd15") == "sd15_controlnet_pose"


def test_controlnet_workflow_selection_falls_back_to_conventional_id():
    config = load_config()
    broken = {
        **config,
        "models": {
            **(config.get("models") or {}),
            "workflows": {
                **((config.get("models") or {}).get("workflows") or {}),
                "controlnet_pose_sdxl": "does_not_exist",
            },
        },
    }
    assert controlnet_workflow_id(broken, "sdxl") == "sdxl_controlnet_pose"


def test_controlnet_workflow_selection_returns_none_without_workflows(tmp_path):
    config = load_config()
    empty = {**config, "paths": {**config["paths"], "workflow_dir": str(tmp_path)}}
    assert controlnet_workflow_id(empty, "sdxl") is None


def _object_info(names: list[str]) -> dict:
    return {
        "ControlNetLoader": {"input": {"required": {"control_net_name": [names]}}},
        "ControlNetApplyAdvanced": {"input": {"required": {}}},
    }


def test_controlnet_model_filters_by_architecture():
    object_info = _object_info(
        ["control_v11p_sd15_openpose.pth", "controlnet-openpose-sdxl-1.0.safetensors"]
    )
    assert controlnet_model(object_info, "sdxl") == "controlnet-openpose-sdxl-1.0.safetensors"
    assert controlnet_model(object_info, "sd15") == "control_v11p_sd15_openpose.pth"


def test_controlnet_model_returns_none_when_no_compatible_file():
    object_info = _object_info(["control_v11p_sd15_openpose.pth"])
    assert controlnet_model(object_info, "sdxl") is None


def test_controlnet_model_without_architecture_keeps_first_file():
    object_info = _object_info(
        ["control_v11p_sd15_openpose.pth", "controlnet-openpose-sdxl-1.0.safetensors"]
    )
    assert controlnet_model(object_info) == "control_v11p_sd15_openpose.pth"


def _ipadapter_info() -> dict:
    return {
        "IPAdapterUnifiedLoader": {
            "input": {"required": {"preset": [["PLUS (high strength)"]]}}
        },
        "IPAdapterAdvanced": {
            "input": {
                "required": {
                    "ipadapter": [["ip-adapter-plus_sdxl_vit-h.safetensors"]],
                }
            }
        },
    }


def test_ipadapter_workflow_selection_follows_architecture():
    config = load_config()
    assert ipadapter_workflow_id(config, "sdxl") == "sdxl_ipadapter_identity"
    assert ipadapter_workflow_id(config, "sd15") is None


def test_resolve_image_mode_prefers_ipadapter_for_identity():
    info = _ipadapter_info()
    assert resolve_image_mode(info, "identity", True) == "ipadapter-identity"
    assert resolve_image_mode(info, "pose", True) == "image-to-image"
    assert resolve_image_mode(info, "identity", False) == "text-to-image"
    assert resolve_image_mode({}, "identity", True) == "image-to-image"


def test_prefer_ipadapter_only_replaces_plain_img2img():
    assert prefer_ipadapter(None) is True
    assert prefer_ipadapter("sdxl_img2img") is True
    assert prefer_ipadapter("sd15_img2img") is True
    assert prefer_ipadapter("sdxl_controlnet_pose") is False
    assert prefer_ipadapter("sdxl_ipadapter_identity") is False
