"""Cutout and 2.5D parallax rendering for limited animation.

Two operations:

1. ``key_plain_background`` turns a character rendered on a plain studio
   backdrop into an RGBA cutout. It samples the border colour, keeps only
   background regions connected to the border, feathers the edge and crops to
   the character.
2. ``render_parallax`` composites a cutout over a background plate and writes a
   short H.264 clip with a moving camera and a gently bobbing subject.

No generative model is involved, so a clip costs seconds of CPU time and the
character stays pixel-identical across frames.
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile
import threading
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ..config import load_config
from ..db import query_one
from ..logging_setup import logger
from .assets import asset_file, store_asset_from_path
from .media import link_asset

CAMERA_PRESETS: dict[str, dict[str, float]] = {
    "static": {"zoom_start": 1.0, "zoom_end": 1.0, "pan_x": 0.0, "pan_y": 0.0},
    "push_in": {"zoom_start": 1.0, "zoom_end": 1.07, "pan_x": 0.0, "pan_y": 0.0},
    "pull_out": {"zoom_start": 1.07, "zoom_end": 1.0, "pan_x": 0.0, "pan_y": 0.0},
    "pan_left": {"zoom_start": 1.04, "zoom_end": 1.04, "pan_x": 0.55, "pan_y": 0.0},
    "pan_right": {"zoom_start": 1.04, "zoom_end": 1.04, "pan_x": -0.55, "pan_y": 0.0},
    "drift": {"zoom_start": 1.0, "zoom_end": 1.05, "pan_x": -0.35, "pan_y": 0.25},
}

_OVERSCAN = 1.18


def _smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def _creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def _ffmpeg(config: dict[str, Any]) -> str:
    configured = str((config.get("ffmpeg") or {}).get("path") or "").strip()
    if configured and Path(configured).exists():
        return configured
    found = shutil.which("ffmpeg")
    if not found:
        raise RuntimeError("FFmpeg was not found. Set its path in Settings.")
    return found


def _border_reachable(mask: np.ndarray) -> np.ndarray:
    """Return the part of a binary mask connected to the image border.

    The flood fill runs on a downscaled copy for speed; the result is scaled
    back up and used only to decide which near-background colours to remove.
    """
    height, width = mask.shape
    source = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    factor = max(1, int(max(height, width) / 256))
    small = source.resize((max(1, width // factor), max(1, height // factor)), Image.NEAREST)
    grid = np.asarray(small) > 127
    rows, cols = grid.shape
    reached = np.zeros_like(grid, dtype=bool)
    queue: deque[tuple[int, int]] = deque()

    for x in range(cols):
        for y in (0, rows - 1):
            if grid[y, x] and not reached[y, x]:
                reached[y, x] = True
                queue.append((y, x))
    for y in range(rows):
        for x in (0, cols - 1):
            if grid[y, x] and not reached[y, x]:
                reached[y, x] = True
                queue.append((y, x))

    while queue:
        y, x = queue.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < rows and 0 <= nx < cols and grid[ny, nx] and not reached[ny, nx]:
                reached[ny, nx] = True
                queue.append((ny, nx))

    upscaled = Image.fromarray((reached.astype(np.uint8) * 255), mode="L").resize(
        (width, height), Image.NEAREST
    )
    return np.asarray(upscaled) > 127


def key_plain_background(
    image: Image.Image,
    *,
    tolerance: int = 26,
    feather: int = 10,
    padding: int = 8,
) -> Image.Image:
    """Remove a plain studio backdrop and return a cropped RGBA cutout."""
    rgba = image.convert("RGBA")
    array = np.asarray(rgba)
    alpha_channel = array[..., 3]
    if (alpha_channel < 250).mean() > 0.005:
        return rgba.crop(rgba.getbbox() or (0, 0, rgba.width, rgba.height))

    rgb = array[..., :3].astype(np.int16)
    height, width = rgb.shape[:2]
    edge = max(2, min(height, width) // 40)
    samples = np.concatenate(
        [
            rgb[:edge, :, :].reshape(-1, 3),
            rgb[-edge:, :, :].reshape(-1, 3),
            rgb[:, :edge, :].reshape(-1, 3),
            rgb[:, -edge:, :].reshape(-1, 3),
        ]
    )
    background = np.median(samples, axis=0)
    distance = np.linalg.norm(rgb - background, axis=-1)
    chroma_green = (
        background[1] > 90
        and background[1] > background[0] * 1.35
        and background[1] > background[2] * 1.35
    )

    low = float(max(0, tolerance))
    high = float(max(low + 1.0, low + max(1, feather)))
    alpha = np.clip((distance - low) / (high - low), 0.0, 1.0)

    near_background = distance <= high
    reachable = _border_reachable(near_background)
    protected = Image.fromarray((reachable.astype(np.uint8) * 255), mode="L").filter(
        ImageFilter.MinFilter(3)
    )
    reachable = np.asarray(protected) > 127
    # Near-background colours enclosed by the subject are interior detail, not backdrop.
    alpha[near_background & ~reachable] = 1.0
    alpha[reachable] = 0.0

    alpha_image = Image.fromarray((alpha * 255).astype(np.uint8), mode="L")
    if feather > 0:
        alpha_image = alpha_image.filter(ImageFilter.GaussianBlur(radius=max(0.6, feather / 3.0)))

    result = rgba.copy()
    result.putalpha(alpha_image)
    if chroma_green:
        # Remove green spill on semi-transparent edges.
        pixels = np.asarray(result).copy()
        alpha_values = pixels[..., 3].astype(np.float32) / 255.0
        red, green, blue = (
            pixels[..., 0].astype(np.int16),
            pixels[..., 1].astype(np.int16),
            pixels[..., 2].astype(np.int16),
        )
        limit = np.maximum(red, blue)
        spill = (alpha_values < 0.98) & (green > limit)
        pixels[..., 1] = np.where(spill, limit, green)
        result = Image.fromarray(pixels, mode="RGBA")
    bbox = result.getbbox()
    if not bbox:
        raise ValueError("Nothing remained after keying; check the tolerance.")
    left, top, right, bottom = bbox
    return result.crop(
        (
            max(0, left - padding),
            max(0, top - padding),
            min(width, right + padding),
            min(height, bottom + padding),
        )
    )


def _cover(image: Image.Image, width: int, height: int, overscan: float) -> Image.Image:
    scale = max(width / image.width, height / image.height) * overscan
    size = (max(width, int(math.ceil(image.width * scale))), max(height, int(math.ceil(image.height * scale))))
    return image.resize(size, Image.LANCZOS)


def _camera(preset: dict[str, float], progress: float) -> tuple[float, float, float]:
    eased = _smoothstep(progress)
    zoom = preset["zoom_start"] + (preset["zoom_end"] - preset["zoom_start"]) * eased
    pan_x = preset.get("pan_x", 0.0) * (eased * 2.0 - 1.0)
    pan_y = preset.get("pan_y", 0.0) * (eased * 2.0 - 1.0)
    return zoom, pan_x, pan_y


def _shadow(foreground_width: int, foreground_height: int) -> Image.Image:
    width = max(8, int(foreground_width * 0.72))
    height = max(6, int(foreground_height * 0.09))
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.ellipse((0, 0, width - 1, height - 1), fill=(24, 18, 12, 80))
    return layer.filter(ImageFilter.GaussianBlur(radius=max(2.0, height / 3.0)))


def render_parallax(
    *,
    background_path: Path,
    foreground_path: Path,
    output_path: Path,
    duration: float = 6.0,
    fps: int = 24,
    width: int = 1280,
    height: int = 720,
    camera: str = "push_in",
    subject_height: float = 0.62,
    subject_x: float = 0.5,
    subject_y: float = 0.94,
    motion_strength: float = 1.0,
    bob_period: float = 2.6,
    shadow: bool = True,
) -> dict[str, Any]:
    """Render a layered 2.5D clip and return render metadata."""
    if camera not in CAMERA_PRESETS:
        raise ValueError(f"Unknown camera preset '{camera}'. Choose one of: {', '.join(CAMERA_PRESETS)}.")
    if not 1 <= duration <= 30:
        raise ValueError("Duration must be between 1 and 30 seconds.")
    if not 12 <= fps <= 30:
        raise ValueError("FPS must be between 12 and 30.")
    width -= width % 2
    height -= height % 2

    background = Image.open(background_path).convert("RGB")
    foreground = Image.open(foreground_path).convert("RGBA")

    plate = _cover(background, width, height, _OVERSCAN)
    foreground_height = max(8, int(subject_height * height))
    foreground_width = max(8, int(foreground.width * foreground_height / foreground.height))
    subject = foreground.resize((foreground_width, foreground_height), Image.LANCZOS)
    shadow_layer = _shadow(foreground_width, foreground_height) if shadow else None

    config = load_config()
    ffmpeg = _ffmpeg(config)
    frames = max(1, int(round(duration * fps)))
    amplitude = max(0.0, motion_strength) * height * 0.004
    command = [
        ffmpeg,
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-r",
        str(fps),
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        creationflags=_creation_flags(),
    )
    assert process.stdin is not None

    preset = CAMERA_PRESETS[camera]
    for index in range(frames):
        progress = index / max(1, frames - 1)
        zoom, pan_x, pan_y = _camera(preset, progress)

        crop_width = max(2, int(width / zoom))
        crop_height = max(2, int(height / zoom))
        available_x = max(0, plate.width - crop_width)
        available_y = max(0, plate.height - crop_height)
        center_x = plate.width / 2 + pan_x * available_x / 2
        center_y = plate.height / 2 + pan_y * available_y / 2
        center_x = min(plate.width - crop_width / 2, max(crop_width / 2, center_x))
        center_y = min(plate.height - crop_height / 2, max(crop_height / 2, center_y))
        box = (
            int(center_x - crop_width / 2),
            int(center_y - crop_height / 2),
            int(center_x + crop_width / 2),
            int(center_y + crop_height / 2),
        )
        frame = plate.crop(box).resize((width, height), Image.LANCZOS).convert("RGBA")

        seconds = index / fps
        bob = amplitude * math.sin(2 * math.pi * seconds / max(0.5, bob_period))
        sway = amplitude * 0.55 * math.sin(2 * math.pi * seconds / max(0.5, bob_period * 1.7) + 0.8)
        base_x = subject_x * width - foreground_width / 2 + sway
        base_y = subject_y * height - foreground_height + bob

        if shadow_layer is not None:
            frame.alpha_composite(
                shadow_layer,
                (
                    int(base_x + (foreground_width - shadow_layer.width) / 2),
                    int(subject_y * height - shadow_layer.height / 2 + bob * 0.4),
                ),
            )
        frame.alpha_composite(subject, (int(base_x), int(base_y)))
        process.stdin.write(frame.convert("RGB").tobytes())

    process.stdin.close()
    error = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
    code = process.wait()
    if code != 0:
        raise RuntimeError(f"FFmpeg failed ({code}): {error.strip()[-500:]}")

    return {
        "width": width,
        "height": height,
        "fps": fps,
        "duration": round(frames / fps, 3),
        "frames": frames,
        "camera": camera,
        "subject_height": subject_height,
        "motion_strength": motion_strength,
    }


def _crop_padding(image: Image.Image, padding: int) -> Image.Image:
    bbox = image.getbbox()
    if not bbox:
        raise ValueError("Nothing remained after keying; check the tolerance.")
    left, top, right, bottom = bbox
    return image.crop(
        (
            max(0, left - padding),
            max(0, top - padding),
            min(image.width, right + padding),
            min(image.height, bottom + padding),
        )
    )


_REMBG_SESSION: Any = None
_REMBG_LOCK = threading.Lock()


def _rembg_session() -> Any:
    global _REMBG_SESSION
    if _REMBG_SESSION is None:
        from rembg import new_session

        _REMBG_SESSION = new_session("u2net")
    return _REMBG_SESSION


def cutout_image(
    image: Image.Image,
    *,
    engine: str = "auto",
    tolerance: int = 26,
    feather: int = 10,
    padding: int = 8,
) -> tuple[Image.Image, str]:
    """Cut a character out of its backdrop.

    ``rembg`` (U²-Net) is the production path: it handles grey, green or
    painterly backdrops and removes the painted floor shadow. Colour keying
    stays as a fast fallback when rembg is not installed.
    """
    if engine not in {"auto", "rembg", "chroma"}:
        raise ValueError("Engine must be 'auto', 'rembg' or 'chroma'.")

    if engine in {"auto", "rembg"}:
        try:
            from rembg import remove
        except ImportError:
            if engine == "rembg":
                raise ValueError(
                    "rembg is not installed. Run 'pip install rembg' in the backend venv."
                ) from None
        else:
            with _REMBG_LOCK:
                result = remove(
                    image.convert("RGB"),
                    session=_rembg_session(),
                    alpha_matting=True,
                    alpha_matting_foreground_threshold=240,
                    alpha_matting_background_threshold=15,
                    alpha_matting_erode_size=8,
                ).convert("RGBA")
            return _crop_padding(result, padding), "rembg"

    return (
        key_plain_background(image, tolerance=tolerance, feather=feather, padding=padding),
        "chroma",
    )


def _project_asset(project_id: str, asset_id: str) -> tuple[Path, dict[str, Any]]:
    found = asset_file(asset_id)
    if not found:
        raise ValueError(f"Asset '{asset_id}' does not exist.")
    path, asset = found
    if asset["project_id"] != project_id:
        raise ValueError("Asset does not belong to this project.")
    return path, asset


def cutout_asset(
    project_id: str,
    asset_id: str,
    *,
    engine: str = "auto",
    tolerance: int = 26,
    feather: int = 10,
    padding: int = 8,
) -> dict[str, Any]:
    """Create a transparent PNG cutout from a character image."""
    path, asset = _project_asset(project_id, asset_id)
    if not str(asset.get("mime", "")).startswith("image/"):
        raise ValueError("The source asset is not an image.")
    with Image.open(path) as image:
        cutout, used_engine = cutout_image(
            image,
            engine=engine,
            tolerance=tolerance,
            feather=feather,
            padding=padding,
        )

    output_dir = Path(load_config()["paths"]["output_dir"]) / project_id / "motion" / "cutouts"
    output_dir.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(suffix=".png", dir=output_dir)
    os.close(handle)
    temp_path = Path(temp_name)
    cutout.save(temp_path, format="PNG")

    stored = store_asset_from_path(
        project_id=project_id,
        subdir="motion/cutouts",
        filename=f"{asset_id}_cutout.png",
        source_path=temp_path,
        kind="image",
        mime="image/png",
        meta={
            "kind": "image",
            "width": cutout.width,
            "height": cutout.height,
            "source_asset_id": asset_id,
            "operation": "cutout",
            "engine": used_engine,
            "tolerance": tolerance,
            "feather": feather,
        },
    )
    logger.info("Cutout %s from asset %s", stored["id"], asset_id)
    return stored


def parallax_asset(
    project_id: str,
    background_asset_id: str,
    foreground_asset_id: str,
    *,
    duration: float = 6.0,
    fps: int = 24,
    width: int = 1280,
    height: int = 720,
    camera: str = "push_in",
    subject_height: float = 0.62,
    subject_x: float = 0.5,
    subject_y: float = 0.94,
    motion_strength: float = 1.0,
    bob_period: float = 2.6,
    shadow: bool = True,
    scene_id: str | None = None,
) -> dict[str, Any]:
    """Render a parallax clip from a background plate and an RGBA cutout."""
    background_path, background_asset = _project_asset(project_id, background_asset_id)
    foreground_path, foreground_asset = _project_asset(project_id, foreground_asset_id)
    for asset in (background_asset, foreground_asset):
        if not str(asset.get("mime", "")).startswith("image/"):
            raise ValueError("Both parallax inputs must be images.")

    output_dir = Path(load_config()["paths"]["output_dir"]) / project_id / "motion" / "parallax"
    output_dir.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(suffix=".mp4", dir=output_dir)
    os.close(handle)
    temp_path = Path(temp_name)
    try:
        meta = render_parallax(
            background_path=background_path,
            foreground_path=foreground_path,
            output_path=temp_path,
            duration=duration,
            fps=fps,
            width=width,
            height=height,
            camera=camera,
            subject_height=subject_height,
            subject_x=subject_x,
            subject_y=subject_y,
            motion_strength=motion_strength,
            bob_period=bob_period,
            shadow=shadow,
        )
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    stored = store_asset_from_path(
        project_id=project_id,
        subdir="motion/parallax",
        filename=f"{background_asset_id}_{foreground_asset_id}_parallax.mp4",
        source_path=temp_path,
        kind="video",
        mime="video/mp4",
        meta={
            "kind": "video",
            "operation": "parallax",
            "background_asset_id": background_asset_id,
            "foreground_asset_id": foreground_asset_id,
            **meta,
        },
    )
    if scene_id:
        if not query_one(
            "SELECT id FROM scenes WHERE id = ? AND project_id = ?", (scene_id, project_id)
        ):
            raise ValueError("Scene does not belong to this project.")
        link_asset("scene", scene_id, stored["id"], role="video", label=f"parallax {camera}")
    logger.info("Parallax clip %s rendered from %s + %s", stored["id"], background_asset_id, foreground_asset_id)
    return stored
