from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psutil

from ..logging_setup import logger


def _safe_cmdline(proc: psutil.Process) -> list[str]:
    try:
        return proc.cmdline()
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        return []


def _safe_cwd(proc: psutil.Process) -> str:
    try:
        return proc.cwd()
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        return ""


def _find_comfy_process() -> dict[str, Any] | None:
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            cmdline = _safe_cmdline(proc)
            if not cmdline:
                continue
            joined = " ".join(cmdline)
            if "main.py" not in joined or "ComfyUI" not in joined:
                continue
            cwd = _safe_cwd(proc)
            main_arg = next((part for part in cmdline if part.endswith("main.py")), "")
            install = ""
            if cwd and (Path(cwd) / "main.py").exists():
                install = cwd
            elif main_arg:
                candidate = Path(main_arg)
                if not candidate.is_absolute():
                    candidate = Path(cwd) / candidate
                install = str(candidate.parent)
            return {
                "pid": proc.pid,
                "argv": cmdline,
                "cwd": cwd,
                "install_path": install,
            }
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return None


def _parse_arg(argv: list[str], flag: str) -> str:
    try:
        index = argv.index(flag)
        return argv[index + 1] if index + 1 < len(argv) else ""
    except ValueError:
        return ""


def _parse_model_paths(yaml_path: str) -> tuple[list[str], dict[str, list[str]]]:
    base_paths: list[str] = []
    folder_paths: dict[str, list[str]] = {}
    if not yaml_path or not Path(yaml_path).exists():
        return base_paths, folder_paths
    try:
        import yaml

        data = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001 - discovery must never crash the app
        logger.warning("Could not parse model paths YAML %s: %s", yaml_path, exc)
        return base_paths, folder_paths

    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        base = entry.get("base_path")
        if not base:
            continue
        base_paths.append(base)
        for folder, value in entry.items():
            if folder in {"base_path", "is_default", "all_model_folders"}:
                continue
            values = value if isinstance(value, list) else str(value).splitlines()
            for rel in values:
                rel = str(rel).strip()
                if rel:
                    folder_paths.setdefault(folder, []).append(str(Path(base) / rel))
    return base_paths, folder_paths


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = os.path.normcase(os.path.normpath(value))
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def discover_comfy(config: dict[str, Any]) -> dict[str, Any]:
    """Discover the live ComfyUI installation and its model paths.

    Order of truth:
    1. The running ComfyUI process (most reliable).
    2. Explicit values in Cartoon Studio's config.
    3. Filesystem fallbacks next to the discovered install.
    """
    comfy_cfg = config["comfyui"]
    process = _find_comfy_process()

    install_path = comfy_cfg.get("install_path") or ""
    argv: list[str] = []
    output_dir = comfy_cfg.get("output_dir") or ""
    input_dir = ""
    extra_model_paths = ""

    if process:
        argv = process["argv"]
        install_path = install_path or process["install_path"]
        output_dir = output_dir or _parse_arg(argv, "--output-directory")
        input_dir = _parse_arg(argv, "--input-directory")
        extra_model_paths = _parse_arg(argv, "--extra-model-paths-config")

    if not install_path:
        # Last-resort: locate a ComfyUI folder under the known Desktop locations.
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Comfy-Desktop",
            Path("C:/ComfyUI"),
            Path("D:/ComfyUI"),
        ]
        for candidate in candidates:
            if candidate.exists():
                for main in candidate.rglob("main.py"):
                    if (main.parent / "comfy").exists():
                        install_path = str(main.parent)
                        break
            if install_path:
                break

    base_paths, folder_paths = _parse_model_paths(extra_model_paths)

    model_dirs = _dedupe(
        list(comfy_cfg.get("models_dirs") or [])
        + base_paths
        + ([str(Path(install_path) / "models")] if install_path else [])
    )

    user_workflows_dir = ""
    if install_path:
        user_workflows_dir = str(Path(install_path) / "user" / "default" / "workflows")

    return {
        "process_pid": process["pid"] if process else None,
        "argv": argv,
        "install_path": install_path,
        "output_dir": output_dir,
        "input_dir": input_dir,
        "extra_model_paths": extra_model_paths,
        "model_dirs": model_dirs,
        "model_folder_paths": folder_paths,
        "user_workflows_dir": user_workflows_dir,
        "server_url": comfy_cfg.get("server_url"),
        "discovered_from_process": bool(process),
    }
