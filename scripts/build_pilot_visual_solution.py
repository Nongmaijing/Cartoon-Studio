"""Build pilot-only Pip/Ollie boards and a 16-shot storyboard.

Uses existing backgrounds, canonical character rasters and vector V2 drafts.
Registers only pilot-only assets; never links them as canonical or approved.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.db import query_one  # noqa: E402
from app.services.assets import store_asset_from_path  # noqa: E402

ROOT = Path(r"D:\bro\CartoonStudio")
VEC = ROOT / "docs" / "operations" / "vector_drafts"
SHOTS = ROOT / "docs" / "operations" / "S01E01_SHOT_PLAN_V1.json"
SCRIPT = ROOT / "docs" / "operations" / "S01E01_SCRIPT_V3.json"
BASE = "http://127.0.0.1:8010"
PROJECT = "16556b67d331"
TMP = Path(r"C:\Users\pagau\AppData\Local\Temp\opencode\pilot_assets")
TMP.mkdir(parents=True, exist_ok=True)
BG = (228, 228, 228)
OUTLINE = (59, 42, 32)
WHITE = (255, 255, 255)

CANON = {
    "Leo": "40abe63ea726",
    "Mira": "bf635873d12a",
    "Toby": "9b8b72c08301",
    "Bruno": "6c02a5ba1e37",
}
PILOT = {"Pip": "pip_v2.png", "Ollie": "ollie_v2.png"}
CHAR_CONFIG = {
    "Pip": {
        "fur": (201, 139, 94),
        "cream": (245, 227, 200),
        "cover": (370, 235, 660, 565),
        "inner_ears": [(398, 185, 30, 110), (626, 185, 30, 110)],
        "mouth": (462, 458, 565, 525),
        "mouth_fill": (201, 139, 94),
        "neckerchief": (240, 138, 40),
        "band": [(390, 610), (634, 610), (646, 650), (512, 680), (378, 650)],
    },
    "Ollie": {
        "fur": (200, 169, 138),
        "cream": (242, 226, 200),
        "cover": (350, 245, 680, 570),
        "inner_ears": [(382, 160, 28, 110), (642, 160, 28, 110)],
        "mouth": (460, 490, 565, 545),
        "mouth_fill": (242, 226, 200),
        "neckerchief": (44, 140, 150),
        "band": [(400, 600), (624, 600), (638, 640), (512, 675), (386, 640)],
    },
}


def fetch(client: httpx.Client, asset_id: str) -> Image.Image:
    response = client.get(f"{BASE}/api/assets/{asset_id}/file", timeout=60)
    response.raise_for_status()
    from io import BytesIO
    return Image.open(BytesIO(response.content)).convert("RGB")


def cutout(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    work = rgb.copy()
    key = (255, 0, 255)
    seeds = []
    for x in range(0, rgb.width, 16):
        seeds.append((x, 0))
        seeds.append((x, rgb.height - 1))
    for y in range(0, rgb.height, 16):
        seeds.append((0, y))
        seeds.append((rgb.width - 1, y))
    for seed in seeds:
        ImageDraw.floodfill(work, seed, key, thresh=120)
    alpha = Image.new("L", rgb.size, 255)
    alpha_px = alpha.load()
    work_px = work.load()
    for y in range(rgb.height):
        for x in range(rgb.width):
            r, g, b = work_px[x, y]
            if r > 240 and g < 30 and b > 240:
                alpha_px[x, y] = 0
    rgba = rgb.convert("RGBA")
    rgba.putalpha(alpha)
    bbox = rgba.getbbox()
    cropped = rgba.crop(bbox) if bbox else rgba
    bg = rgb.getpixel((2, 2))
    px = cropped.load()
    for y in range(int(cropped.height * 0.72), cropped.height):
        for x in range(cropped.width):
            r, g, b, a = px[x, y]
            if a and max(abs(r - bg[0]), abs(g - bg[1]), abs(b - bg[2])) <= 12:
                px[x, y] = (r, g, b, 0)
    return cropped


def three_quarter(front: Image.Image) -> Image.Image:
    width = 870
    resized = front.resize((width, front.height), Image.LANCZOS)
    canvas = Image.new("RGB", front.size, BG)
    canvas.paste(resized, ((front.width - width) // 2, 0))
    return canvas


def side(front: Image.Image) -> Image.Image:
    width = 560
    resized = front.resize((width, front.height), Image.LANCZOS)
    canvas = Image.new("RGB", front.size, BG)
    canvas.paste(resized, ((front.width - width) // 2, 0))
    return canvas


def back_view(front: Image.Image, cfg: dict) -> Image.Image:
    image = front.copy()
    draw = ImageDraw.Draw(image)
    draw.ellipse(cfg["cover"], fill=cfg["fur"])
    for x, y, rx, ry in cfg["inner_ears"]:
        draw.ellipse((x - rx, y - ry, x + rx, y + ry), fill=cfg["fur"])
    draw.polygon(cfg["band"], fill=cfg["neckerchief"], outline=OUTLINE)
    draw.line(cfg["band"] + [cfg["band"][0]], fill=OUTLINE, width=4)
    draw.ellipse((496, 642, 528, 674), fill=cfg["neckerchief"], outline=OUTLINE, width=4)
    return image


def expression(front: Image.Image, cfg: dict, kind: str) -> Image.Image:
    image = front.copy()
    draw = ImageDraw.Draw(image)
    if kind == "neutral":
        return image
    draw.ellipse(cfg["mouth"], fill=cfg["mouth_fill"])
    if kind == "happy":
        draw.arc(cfg["mouth"], start=0, end=180, fill=OUTLINE, width=6)
        draw.arc((cfg["mouth"][0] - 20, cfg["mouth"][1] - 20, cfg["mouth"][2] + 20, cfg["mouth"][3] + 20), start=200, end=340, fill=OUTLINE, width=4)
    else:
        cx = (cfg["mouth"][0] + cfg["mouth"][2]) // 2
        cy = (cfg["mouth"][1] + cfg["mouth"][3]) // 2
        draw.ellipse((cx - 11, cy - 12, cx + 11, cy + 12), fill=(120, 60, 45), outline=OUTLINE, width=4)
        draw.line([(cx - 55, cy - 70), (cx - 20, cy - 82), (cx + 10, cy - 70)], fill=OUTLINE, width=4)
    return image


def board(front: Image.Image, cfg: dict, path: Path) -> None:
    views = [
        ("Front", front),
        ("3/4 (approx.)", three_quarter(front)),
        ("Side (approx.)", side(front)),
        ("Back (approx.)", back_view(front, cfg)),
    ]
    expressions = [
        ("Neutral", expression(front, cfg, "neutral")),
        ("Happy", expression(front, cfg, "happy")),
        ("Curious", expression(front, cfg, "curious")),
        ("PILOT-ONLY", None),
    ]
    cell_w, cell_h, label_h = 300, 330, 24
    sheet = Image.new("RGB", (4 * cell_w, 2 * (cell_h + label_h)), BG)
    draw = ImageDraw.Draw(sheet)
    for row, items in enumerate((views, expressions)):
        for col, (label, image) in enumerate(items):
            x = col * cell_w
            y = row * (cell_h + label_h)
            draw.text((x + 8, y + 4), label, fill=(40, 40, 40))
            if image is None:
                draw.text((x + 12, y + 60), "Pilot-only working\ndesign. Not series\ncanon. Not approved.", fill=(120, 50, 40))
                continue
            thumb = image.copy()
            thumb.thumbnail((cell_w - 12, cell_h - 12))
            sheet.paste(thumb, (x + (cell_w - thumb.width) // 2, y + label_h + (cell_h - thumb.height) // 2))
    sheet.save(path)


def cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    ratio = max(size[0] / image.width, size[1] / image.height)
    resized = image.resize((int(image.width * ratio) + 1, int(image.height * ratio) + 1), Image.LANCZOS)
    left = (resized.width - size[0]) // 2
    top = (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1]))


def background_asset(client: httpx.Client, background_id: str) -> Image.Image:
    row = query_one(
        "SELECT asset_id FROM media_links WHERE owner_type='background' AND owner_id=? AND role='background' ORDER BY created_at DESC LIMIT 1",
        (background_id,),
    )
    if not row:
        raise RuntimeError(f"No background image for {background_id}")
    return fetch(client, row["asset_id"])


def make_panel(
    shot: dict,
    background: Image.Image,
    characters: dict[str, Image.Image],
    size: tuple[int, int] = (480, 270),
    big: bool = False,
) -> Image.Image:
    panel = cover(background, size)
    draw = ImageDraw.Draw(panel)
    names = shot["characters_on_screen"]
    cutouts = [characters[name] for name in names if name in characters]
    count = max(1, len(cutouts))
    height = int(size[1] * (0.72 if count == 1 else 0.62 if count <= 3 else 0.52))
    if big:
        height = int(size[1] * (0.74 if count == 1 else 0.66 if count <= 3 else 0.58))
    scaled = []
    for cut in cutouts:
        ratio = height / cut.height
        scaled.append(cut.resize((max(1, int(cut.width * ratio)), height), Image.LANCZOS))
    gap = max(4, int(size[0] * 0.01))
    total_width = sum(char.width for char in scaled) + gap * max(0, len(scaled) - 1)
    max_width = int(size[0] * 0.94)
    if total_width > max_width:
        factor = max_width / total_width
        scaled = [
            char.resize((max(1, int(char.width * factor)), max(1, int(char.height * factor))), Image.LANCZOS)
            for char in scaled
        ]
        total_width = sum(char.width for char in scaled) + gap * max(0, len(scaled) - 1)
    x = (size[0] - total_width) // 2
    for char in scaled:
        y = size[1] - char.height - int(size[1] * 0.06)
        panel.paste(char, (x, y), char)
        x += char.width + gap
    banner = Image.new("RGBA", (size[0], 30), (30, 30, 30, 190))
    panel.paste(banner, (0, 0), banner)
    draw = ImageDraw.Draw(panel)
    label = f"Shot {shot['number']} - {shot['scene_title']} - {shot['duration_seconds']}s"
    draw.text((8, 7), label, fill=WHITE)
    if big:
        draw.text((8, size[1] - 22), "PILOT SCENE BOARD - NOT FINAL KEYFRAME", fill=WHITE)
    return panel


def main() -> None:
    client = httpx.Client(timeout=httpx.Timeout(120.0, read=300.0))
    pilot_images = {name: Image.open(VEC / filename).convert("RGB") for name, filename in PILOT.items()}
    for name, image in pilot_images.items():
        board(image, CHAR_CONFIG[name], VEC / f"{name.lower()}_pilot_board_v1.png")
        print("BOARD", name)

    shot_plan = json.loads(SHOTS.read_text(encoding="utf-8"))
    shots = shot_plan["shots"]
    characters = {name: cutout(fetch(client, asset_id)) for name, asset_id in CANON.items()}
    characters.update({name: cutout(image) for name, image in pilot_images.items()})
    backgrounds = {
        shot["background_id"]: background_asset(client, shot["background_id"])
        for shot in shots
    }

    panels = [make_panel(shot, backgrounds[shot["background_id"]], characters) for shot in shots]
    sheet = Image.new("RGB", (4 * 480, 4 * 300), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    for index, panel in enumerate(panels):
        x = (index % 4) * 480
        y = (index // 4) * 300
        sheet.paste(panel, (x, y + 20))
        draw.text((x + 8, y + 4), f"Shot {shots[index]['number']}", fill=WHITE)
    storyboard_path = ROOT / "docs" / "operations" / "pilot_storyboard_v4.png"
    sheet.save(storyboard_path)
    print("STORYBOARD", storyboard_path)

    scene_shots = [1, 6, 9, 16]
    scene_paths = []
    for scene_index, shot_number in enumerate(scene_shots, start=1):
        shot = next(item for item in shots if item["number"] == shot_number)
        panel = make_panel(shot, backgrounds[shot["background_id"]], characters, size=(960, 540), big=True)
        path = ROOT / "docs" / "operations" / f"pilot_scene_{scene_index:02d}_v4.png"
        panel.save(path)
        scene_paths.append(path)
        print("SCENE", scene_index, path)

    manifest = {
        "pilot_only": True,
        "not_canonical": True,
        "board_assets": [
            {"label": "Pip pilot-only board", "asset_id": "d00f22ae4c5e"},
            {"label": "Ollie pilot-only board", "asset_id": "1ea0635c1b30"},
        ],
        "assets": [],
    }
    files = [
        ("pilot_storyboard_v4.png", storyboard_path, "16-shot pilot storyboard v4"),
    ]
    for index, path in enumerate(scene_paths, start=1):
        files.append((f"pilot_scene_{index:02d}_v4.png", path, f"Pilot scene board v4 - scene {index}"))
    for filename, path, label in files:
        copy_path = TMP / filename
        shutil.copy2(path, copy_path)
        asset = store_asset_from_path(
            project_id=PROJECT,
            subdir="pilot_only",
            filename=filename,
            source_path=copy_path,
            kind="image",
            mime="image/png",
            meta={"pilot_only": True, "not_canonical": True, "label": label},
        )
        manifest["assets"].append({"path": str(path), "asset_id": asset["id"], "label": label})
        print("ASSET", asset["id"], filename)

    (ROOT / "docs" / "operations" / "pilot_visual_solution_v4.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print("WROTE pilot_visual_solution_v4.json")


if __name__ == "__main__":
    main()
