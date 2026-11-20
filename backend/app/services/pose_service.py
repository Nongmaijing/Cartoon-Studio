"""Deterministic OpenPose skeletons for character turnaround views.

Text prompts alone do not rotate an SDXL character away from the pose implied
by an IP-Adapter reference. ControlNet OpenPose does. These skeletons are
generated programmatically so the app can request a front, three-quarter, side
or back view without needing a photographed pose.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from ..config import load_config
from .assets import store_asset_from_path

# OpenPose 18-keypoint order:
# 0 nose, 1 neck, 2 R shoulder, 3 R elbow, 4 R wrist,
# 5 L shoulder, 6 L elbow, 7 L wrist,
# 8 R hip, 9 R knee, 10 R ankle, 11 L hip, 12 L knee, 13 L ankle,
# 14 R eye, 15 L eye, 16 R ear, 17 L ear.
POINT_COLORS = {
    0: (255, 0, 0),
    1: (255, 0, 0),
    2: (255, 85, 0),
    3: (255, 170, 0),
    4: (255, 255, 0),
    5: (170, 0, 255),
    6: (85, 0, 255),
    7: (0, 0, 255),
    8: (255, 0, 170),
    9: (255, 0, 85),
    10: (255, 0, 255),
    11: (170, 255, 0),
    12: (85, 255, 0),
    13: (0, 255, 0),
    14: (255, 255, 0),
    15: (0, 255, 255),
    16: (255, 0, 255),
    17: (0, 255, 255),
}

LIMBS = (
    (1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7),
    (1, 8), (8, 9), (9, 10), (1, 11), (11, 12), (12, 13),
    (8, 11), (2, 5), (8, 11),
)

# Normalised coordinates (x, y). The canvas is portrait.
_LAYOUTS: dict[str, dict[int, tuple[float, float]]] = {
    "front": {
        0: (0.500, 0.145), 1: (0.500, 0.225),
        2: (0.420, 0.265), 3: (0.385, 0.395), 4: (0.365, 0.515),
        5: (0.580, 0.265), 6: (0.615, 0.395), 7: (0.635, 0.515),
        8: (0.445, 0.545), 9: (0.445, 0.725), 10: (0.445, 0.915),
        11: (0.555, 0.545), 12: (0.555, 0.725), 13: (0.555, 0.915),
        14: (0.482, 0.138), 15: (0.518, 0.138),
        16: (0.455, 0.155), 17: (0.545, 0.155),
    },
    "three_quarter": {
        0: (0.525, 0.145), 1: (0.500, 0.225),
        2: (0.435, 0.265), 3: (0.405, 0.395), 4: (0.390, 0.515),
        5: (0.565, 0.265), 6: (0.600, 0.395), 7: (0.620, 0.515),
        8: (0.445, 0.545), 9: (0.445, 0.725), 10: (0.445, 0.915),
        11: (0.555, 0.545), 12: (0.555, 0.725), 13: (0.555, 0.915),
        14: (0.488, 0.138), 15: (0.522, 0.140),
        16: (0.458, 0.155), 17: (0.548, 0.153),
    },
    "side": {
        0: (0.565, 0.145), 1: (0.500, 0.225),
        2: (0.520, 0.265), 3: (0.545, 0.395), 4: (0.560, 0.515),
        5: (0.485, 0.270), 6: (0.475, 0.400), 7: (0.470, 0.520),
        8: (0.520, 0.545), 9: (0.525, 0.725), 10: (0.535, 0.915),
        11: (0.485, 0.550), 12: (0.480, 0.730), 13: (0.472, 0.915),
        14: (0.535, 0.140), 15: (0.525, 0.145),
        16: (0.512, 0.155), 17: (0.505, 0.160),
    },
    "back": {
        0: (0.500, 0.150), 1: (0.500, 0.225),
        2: (0.420, 0.265), 3: (0.385, 0.395), 4: (0.365, 0.515),
        5: (0.580, 0.265), 6: (0.615, 0.395), 7: (0.635, 0.515),
        8: (0.445, 0.545), 9: (0.445, 0.725), 10: (0.445, 0.915),
        11: (0.555, 0.545), 12: (0.555, 0.725), 13: (0.555, 0.915),
    },
}


def view_key(value: str) -> str:
    """Map a free-form label to one of the skeleton layouts."""
    text = re.sub(r"back\s*pack", "", (value or "").lower())
    text = re.sub(r"backpack", "", text).replace("-", " ").replace("_", " ")
    if "side" in text or "profile" in text:
        return "side"
    if "three" in text or "quarter" in text or "3/4" in text or "3 4" in text:
        return "three_quarter"
    if re.search(r"\b(back|rear)\b", text):
        return "back"
    return "front"


def render_pose_skeleton(view: str = "front", width: int = 832, height: int = 1216) -> Image.Image:
    """Draw an OpenPose-style skeleton on a black canvas."""
    layout = _LAYOUTS.get(view) or _LAYOUTS["front"]
    scale = 2
    canvas_width, canvas_height = width * scale, height * scale
    image = Image.new("RGB", (canvas_width, canvas_height), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    points = {
        index: (int(x * canvas_width), int(y * canvas_height))
        for index, (x, y) in layout.items()
    }

    line_width = max(6, canvas_width // 110)
    for start, end in LIMBS:
        if start not in points or end not in points:
            continue
        draw.line((points[start], points[end]), fill=POINT_COLORS.get(end, (255, 255, 255)), width=line_width)

    radius = max(5, canvas_width // 150)
    for index, point in points.items():
        draw.ellipse(
            (point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius),
            fill=POINT_COLORS.get(index, (255, 255, 255)),
        )

    return image.resize((width, height), Image.LANCZOS)


def store_pose_skeleton(
    project_id: str,
    view: str,
    width: int = 832,
    height: int = 1216,
) -> dict[str, Any]:
    """Render a skeleton and register it as a reusable project image asset."""
    skeleton = render_pose_skeleton(view, width, height)
    output_dir = Path(load_config()["paths"]["output_dir"]) / project_id / "motion" / "poses"
    output_dir.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(suffix=".png", dir=output_dir)
    os.close(handle)
    temp_path = Path(temp_name)
    skeleton.save(temp_path, format="PNG")
    return store_asset_from_path(
        project_id=project_id,
        subdir="motion/poses",
        filename=f"pose_{view}.png",
        source_path=temp_path,
        kind="image",
        mime="image/png",
        meta={
            "kind": "image",
            "operation": "pose_skeleton",
            "view": view,
            "width": width,
            "height": height,
        },
    )
