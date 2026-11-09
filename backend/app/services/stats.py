from __future__ import annotations

import shutil
import subprocess
from typing import Any

import psutil


def _nvidia_smi() -> dict[str, Any] | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        output = subprocess.run(
            [
                exe,
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=6,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if output.returncode != 0 or not output.stdout.strip():
            return None
        name, util, used, total, temp = [part.strip() for part in output.stdout.splitlines()[0].split(",")]
        return {
            "name": name,
            "utilization_percent": float(util),
            "vram_used_mb": float(used),
            "vram_total_mb": float(total),
            "temperature_c": float(temp),
        }
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def system_stats() -> dict[str, Any]:
    memory = psutil.virtual_memory()
    gpu = _nvidia_smi()
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_total_gb": round(memory.total / (1024**3), 1),
        "ram_used_gb": round((memory.total - memory.available) / (1024**3), 1),
        "ram_percent": memory.percent,
        "gpu": gpu,
    }
