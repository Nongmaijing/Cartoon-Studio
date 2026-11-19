"""Build Pip/Ollie vector V2 drafts and comparison sheets.

V1 files are preserved. No registration, canonicalization or model download.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import build_vector_character_drafts as v1  # noqa: E402

OUT = Path(r"D:\bro\CartoonStudio\docs\operations\vector_drafts")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8010"
CANONICAL = {
    "Leo": "40abe63ea726",
    "Mira": "bf635873d12a",
    "Toby": "9b8b72c08301",
    "Bruno": "6c02a5ba1e37",
}
PIP_FUR = v1.PIP_FUR
PIP_LIGHT = v1.PIP_LIGHT
PIP_CREAM = v1.PIP_CREAM
PIP_PINK = v1.PIP_PINK
PIP_ORANGE = v1.PIP_ORANGE
PIP_ORANGE_DARK = v1.PIP_ORANGE_DARK
PIP_BLUSH = v1.PIP_BLUSH
OLLIE_COAT = v1.OLLIE_COAT
OLLIE_CREAM = v1.OLLIE_CREAM
OLLIE_HOOF = v1.OLLIE_HOOF
OLLIE_MANE = v1.OLLIE_MANE
OLLIE_TEAL = v1.OLLIE_TEAL
OLLIE_TEAL_DARK = v1.OLLIE_TEAL_DARK
OUTLINE = v1.OUTLINE
EYE_DARK = v1.EYE_DARK
WHITE = v1.WHITE


def rotated_ellipse(cx, cy, rx, ry, angle_deg, segments=40):
    rad = math.radians(angle_deg)
    points = []
    for index in range(segments):
        theta = 2 * math.pi * index / segments
        x = rx * math.cos(theta)
        y = ry * math.sin(theta)
        points.append(
            (
                cx + x * math.cos(rad) - y * math.sin(rad),
                cy + x * math.sin(rad) + y * math.cos(rad),
            )
        )
    return points


def pip_v2():
    p = []
    p.append(v1.ellipse("shadow", 512, 930, 182, 26, "#C9C9C9"))
    p.append(v1.ellipse("tail", 705, 795, 50, 44, PIP_FUR, OUTLINE, 8))
    p.append(v1.polygon("tail", [(735, 820), (766, 842), (742, 833), (754, 862), (728, 836)], PIP_LIGHT, OUTLINE, 5))
    p.append(v1.polygon("legs", [(430, 760), (470, 760), (478, 890), (455, 920), (425, 918), (420, 890)], PIP_FUR, OUTLINE, 8))
    p.append(v1.polygon("legs", [(594, 760), (554, 760), (546, 890), (569, 920), (599, 918), (604, 890)], PIP_FUR, OUTLINE, 8))
    p.append(v1.ellipse("legs", 445, 928, 78, 34, PIP_CREAM, OUTLINE, 8))
    p.append(v1.ellipse("legs", 579, 928, 78, 34, PIP_CREAM, OUTLINE, 8))
    p.append(
        v1.polygon(
            "body",
            [(512, 520), (600, 540), (640, 620), (650, 760), (600, 860), (512, 890),
             (424, 860), (374, 760), (384, 620), (424, 540)],
            PIP_FUR,
            OUTLINE,
            8,
        )
    )
    p.append(v1.ellipse("body", 512, 742, 95, 128, PIP_CREAM))
    p.append(v1.polygon("arms", [(420, 610), (390, 630), (370, 730), (382, 800), (408, 795), (408, 720), (440, 650)], PIP_FUR, OUTLINE, 8))
    p.append(v1.polygon("arms", [(604, 610), (634, 630), (654, 730), (642, 800), (616, 795), (616, 720), (584, 650)], PIP_FUR, OUTLINE, 8))
    p.append(v1.ellipse("arms", 395, 808, 38, 34, PIP_CREAM, OUTLINE, 8))
    p.append(v1.ellipse("arms", 629, 808, 38, 34, PIP_CREAM, OUTLINE, 8))
    p.append(v1.polygon("ears", rotated_ellipse(398, 185, 54, 150, -7), PIP_FUR, OUTLINE, 8))
    p.append(v1.polygon("ears", rotated_ellipse(626, 185, 54, 150, 7), PIP_FUR, OUTLINE, 8))
    p.append(v1.polygon("ears", rotated_ellipse(398, 185, 30, 110, -7), PIP_PINK))
    p.append(v1.polygon("ears", rotated_ellipse(626, 185, 30, 110, 7), PIP_PINK))
    p.append(v1.polygon("neckerchief", [(390, 610), (634, 610), (646, 650), (512, 690), (378, 650)], PIP_ORANGE, OUTLINE, 8))
    p.append(v1.polygon("neckerchief", [(420, 615), (610, 615), (620, 640), (512, 665), (404, 640)], "#FFB25A"))
    p.append(v1.polygon("neckerchief", [(430, 650), (594, 650), (512, 780)], PIP_ORANGE, OUTLINE, 8))
    p.append(v1.line("neckerchief", [(512, 660), (512, 760)], PIP_ORANGE_DARK, 4))
    p.append(v1.circle("neckerchief", 512, 650, 28, PIP_ORANGE_DARK, OUTLINE, 8))
    p.append(v1.circle("neckerchief", 504, 642, 8, "#FFC06A"))
    p.append(v1.ellipse("head", 512, 400, 185, 170, PIP_FUR, OUTLINE, 8))
    p.append(v1.ellipse("face", 430, 470, 34, 20, PIP_BLUSH))
    p.append(v1.ellipse("face", 594, 470, 34, 20, PIP_BLUSH))
    p.append(v1.ellipse("face", 450, 400, 40, 50, WHITE, OUTLINE, 6))
    p.append(v1.ellipse("face", 574, 400, 40, 50, WHITE, OUTLINE, 6))
    p.append(v1.ellipse("face", 455, 410, 21, 28, EYE_DARK))
    p.append(v1.ellipse("face", 579, 410, 21, 28, EYE_DARK))
    p.append(v1.circle("face", 448, 396, 9, WHITE))
    p.append(v1.circle("face", 572, 396, 9, WHITE))
    p.append(v1.circle("face", 462, 424, 4, WHITE))
    p.append(v1.circle("face", 586, 424, 4, WHITE))
    p.append(v1.line("face", [(425, 365), (450, 352), (475, 365)], OUTLINE, 5))
    p.append(v1.line("face", [(549, 365), (574, 352), (599, 365)], OUTLINE, 5))
    p.append(v1.ellipse("face", 512, 465, 18, 13, PIP_PINK, OUTLINE, 5))
    p.append(v1.line("face", [(512, 478), (512, 494)], OUTLINE, 5))
    p.append(v1.arc("face", (482, 474, 512, 510), 0, 180, OUTLINE, 5))
    p.append(v1.arc("face", (512, 474, 542, 510), 0, 180, OUTLINE, 5))
    for pts in (
        [(400, 462), (332, 452)], [(400, 478), (327, 478)], [(400, 494), (332, 504)],
        [(624, 462), (692, 452)], [(624, 478), (697, 478)], [(624, 494), (692, 504)],
    ):
        p.append(v1.line("face", pts, OUTLINE, 4))
    p.append(v1.polygon("hair", [(490, 238), (503, 204), (514, 233), (529, 199), (540, 238), (521, 254), (500, 254)], PIP_FUR, OUTLINE, 6))
    return p


def ollie_v2():
    p = []
    p.append(v1.ellipse("shadow", 512, 930, 178, 26, "#C9C9C9"))
    p.append(v1.ellipse("tail", 712, 760, 42, 60, OLLIE_COAT, OUTLINE, 8))
    p.append(v1.polygon("tail", [(732, 812), (770, 842), (742, 832), (755, 862), (724, 834)], OLLIE_MANE, OUTLINE, 5))
    p.append(v1.polygon("legs", [(432, 760), (470, 760), (478, 885), (455, 918), (425, 916), (420, 885)], OLLIE_COAT, OUTLINE, 8))
    p.append(v1.polygon("legs", [(592, 760), (554, 760), (546, 885), (569, 918), (599, 916), (604, 885)], OLLIE_COAT, OUTLINE, 8))
    p.append(v1.ellipse("legs", 445, 928, 70, 34, OLLIE_HOOF, OUTLINE, 8))
    p.append(v1.ellipse("legs", 579, 928, 70, 34, OLLIE_HOOF, OUTLINE, 8))
    p.append(v1.ellipse("body", 512, 700, 145, 190, OLLIE_COAT, OUTLINE, 8))
    p.append(v1.ellipse("body", 512, 730, 90, 120, OLLIE_CREAM))
    p.append(v1.polygon("arms", [(420, 610), (390, 630), (372, 730), (384, 792), (410, 787), (410, 720), (442, 650)], OLLIE_COAT, OUTLINE, 8))
    p.append(v1.polygon("arms", [(604, 610), (634, 630), (652, 730), (640, 792), (614, 787), (614, 720), (582, 650)], OLLIE_COAT, OUTLINE, 8))
    p.append(v1.ellipse("arms", 398, 800, 42, 34, OLLIE_HOOF, OUTLINE, 8))
    p.append(v1.ellipse("arms", 626, 800, 42, 34, OLLIE_HOOF, OUTLINE, 8))
    p.append(v1.polygon("ears", rotated_ellipse(382, 160, 50, 152, -27), OLLIE_COAT, OUTLINE, 8))
    p.append(v1.polygon("ears", rotated_ellipse(642, 160, 50, 152, 27), OLLIE_COAT, OUTLINE, 8))
    p.append(v1.polygon("ears", rotated_ellipse(382, 160, 28, 110, -27), "#E8C9A8"))
    p.append(v1.polygon("ears", rotated_ellipse(642, 160, 28, 110, 27), "#E8C9A8"))
    p.append(v1.polygon("neckerchief", [(400, 600), (624, 600), (638, 640), (512, 675), (386, 640)], OLLIE_TEAL, OUTLINE, 8))
    p.append(v1.polygon("neckerchief", [(425, 605), (599, 605), (610, 630), (512, 650), (414, 630)], "#58B8C0"))
    p.append(v1.polygon("neckerchief", [(438, 640), (586, 640), (512, 760)], OLLIE_TEAL, OUTLINE, 8))
    p.append(v1.line("neckerchief", [(512, 650), (512, 742)], OLLIE_TEAL_DARK, 4))
    p.append(v1.circle("neckerchief", 512, 640, 28, OLLIE_TEAL_DARK, OUTLINE, 8))
    p.append(v1.circle("neckerchief", 504, 632, 8, "#7FD0D8"))
    p.append(v1.ellipse("head", 512, 390, 172, 165, OLLIE_COAT, OUTLINE, 8))
    p.append(v1.ellipse("face", 512, 480, 120, 82, OLLIE_CREAM, OUTLINE, 8))
    p.append(v1.ellipse("face", 452, 375, 38, 48, WHITE, OUTLINE, 6))
    p.append(v1.ellipse("face", 572, 375, 38, 48, WHITE, OUTLINE, 6))
    p.append(v1.ellipse("face", 457, 385, 20, 27, EYE_DARK))
    p.append(v1.ellipse("face", 577, 385, 20, 27, EYE_DARK))
    p.append(v1.circle("face", 450, 371, 8, WHITE))
    p.append(v1.circle("face", 570, 371, 8, WHITE))
    p.append(v1.circle("face", 463, 397, 4, WHITE))
    p.append(v1.circle("face", 583, 397, 4, WHITE))
    p.append(v1.line("face", [(425, 340), (452, 328), (478, 340)], OUTLINE, 5))
    p.append(v1.line("face", [(546, 340), (572, 328), (599, 340)], OUTLINE, 5))
    p.append(v1.ellipse("face", 485, 480, 16, 10, OLLIE_HOOF))
    p.append(v1.ellipse("face", 539, 480, 16, 10, OLLIE_HOOF))
    p.append(v1.line("face", [(490, 515), (512, 525), (534, 515)], OUTLINE, 5))
    p.append(
        v1.polygon(
            "hair",
            [(480, 225), (495, 190), (505, 220), (520, 185), (530, 220), (545, 190), (552, 235), (525, 245), (500, 245)],
            OLLIE_MANE,
            OUTLINE,
            6,
        )
    )
    return p


def sha16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def raster_silhouette(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    bg = rgb.getpixel((2, 2))
    mask = Image.new("L", rgb.size, 0)
    mask_px = mask.load()
    src = rgb.load()
    for y in range(rgb.height):
        for x in range(rgb.width):
            px = src[x, y]
            if max(abs(px[i] - bg[i]) for i in range(3)) > 28:
                mask_px[x, y] = 255
    out = Image.new("RGB", rgb.size, (228, 228, 228))
    dark = Image.new("RGB", rgb.size, (59, 42, 32))
    out.paste(dark, (0, 0), mask)
    return out


def comparison_sheet(images: list[tuple[str, Image.Image]], path: Path) -> None:
    cell = 330
    label_h = 26
    cols, rows = 3, 2
    sheet = Image.new("RGB", (cols * cell, rows * (cell + label_h)), (228, 228, 228))
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(images):
        x = (index % cols) * cell
        y = (index // cols) * (cell + label_h)
        image = image.convert("RGB")
        image.thumbnail((cell - 12, cell - 12))
        sheet.paste(image, (x + (cell - image.width) // 2, y + label_h + (cell - image.height) // 2))
        draw.text((x + 8, y + 5), label, fill=(40, 40, 40))
    sheet.save(path)


def fetch_canonical(client: httpx.Client, asset_id: str) -> Image.Image:
    response = client.get(f"{BASE}/api/assets/{asset_id}/file", timeout=60)
    response.raise_for_status()
    from io import BytesIO
    return Image.open(BytesIO(response.content)).convert("RGB")


def main() -> None:
    manifest = {
        "version": "v2",
        "canvas": [v1.W, v1.H],
        "background": v1.BG,
        "status": "exploratory vector draft v2; not registered; not canonical",
        "characters": {},
    }
    for name, builder in (("pip", pip_v2), ("ollie", ollie_v2)):
        prims = builder()
        svg = OUT / f"{name}_v2.svg"
        png = OUT / f"{name}_v2.png"
        sil_svg = OUT / f"{name}_v2_silhouette.svg"
        sil_png = OUT / f"{name}_v2_silhouette.png"
        v1.render_svg(prims, svg)
        v1.render_png(prims, png)
        v1.render_svg(prims, sil_svg, silhouette=True)
        v1.render_png(prims, sil_png, silhouette=True)
        manifest["characters"][name] = {
            "svg": svg.name,
            "png": png.name,
            "silhouette_svg": sil_svg.name,
            "silhouette_png": sil_png.name,
            "shapes": len(prims),
            "svg_sha256_16": sha16(svg),
            "png_sha256_16": sha16(png),
        }
        print(name, "shapes", len(prims), "->", png)

    client = httpx.Client()
    try:
        canonical = {name: fetch_canonical(client, asset_id) for name, asset_id in CANONICAL.items()}
    finally:
        client.close()

    pip_png = Image.open(OUT / "pip_v2.png")
    ollie_png = Image.open(OUT / "ollie_v2.png")
    lineup = [
        (f"Leo - canonical {CANONICAL['Leo']}", canonical["Leo"]),
        (f"Mira - canonical {CANONICAL['Mira']}", canonical["Mira"]),
        (f"Toby - canonical {CANONICAL['Toby']}", canonical["Toby"]),
        (f"Bruno - canonical {CANONICAL['Bruno']}", canonical["Bruno"]),
        ("Pip - vector V2 draft", pip_png),
        ("Ollie - vector V2 draft", ollie_png),
    ]
    comparison_sheet(lineup, OUT / "lineup_v2.png")

    silhouettes = [
        (f"Leo - silhouette", raster_silhouette(canonical["Leo"])),
        (f"Mira - silhouette", raster_silhouette(canonical["Mira"])),
        (f"Toby - silhouette", raster_silhouette(canonical["Toby"])),
        (f"Bruno - silhouette", raster_silhouette(canonical["Bruno"])),
        ("Pip - vector silhouette V2", Image.open(OUT / "pip_v2_silhouette.png")),
        ("Ollie - vector silhouette V2", Image.open(OUT / "ollie_v2_silhouette.png")),
    ]
    comparison_sheet(silhouettes, OUT / "silhouette_compare_v2.png")

    manifest["comparison"] = {
        "lineup": "lineup_v2.png",
        "silhouette": "silhouette_compare_v2.png",
    }
    (OUT / "manifest_v2.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("WROTE", OUT / "manifest_v2.json")


if __name__ == "__main__":
    main()
