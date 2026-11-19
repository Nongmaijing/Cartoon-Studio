"""Build editable SVG drafts and matching PNG previews for Pip and Ollie.

No external SVG renderer or model download is used. The SVG and PNG are both
generated from one shared primitive list, so the preview matches the editable
vector groups. Nothing is registered in Cartoon Studio.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(r"D:\bro\CartoonStudio\docs\operations\vector_drafts")
OUT.mkdir(parents=True, exist_ok=True)
W = H = 1024
BG = "#E4E4E4"
OUTLINE = "#3B2A20"


def P(kind: str, group: str, **kwargs) -> dict:
    return {"kind": kind, "group": group, **kwargs}


def ellipse(group, cx, cy, rx, ry, fill, stroke=None, width=0) -> dict:
    return P("ellipse", group, cx=cx, cy=cy, rx=rx, ry=ry, fill=fill, stroke=stroke, width=width)


def circle(group, cx, cy, r, fill, stroke=None, width=0) -> dict:
    return P("circle", group, cx=cx, cy=cy, r=r, fill=fill, stroke=stroke, width=width)


def polygon(group, points, fill, stroke=None, width=0) -> dict:
    return P("polygon", group, points=points, fill=fill, stroke=stroke, width=width)


def line(group, points, stroke, width) -> dict:
    return P("line", group, points=points, stroke=stroke, width=width)


def arc(group, box, start, end, stroke, width) -> dict:
    return P("arc", group, box=box, start=start, end=end, stroke=stroke, width=width)


def rect(group, x, y, w, h, r, fill, stroke=None, width=0) -> dict:
    return P("rect", group, x=x, y=y, w=w, h=h, r=r, fill=fill, stroke=stroke, width=width)


# Palette shared with the canonical 2D series.
PIP_FUR = "#C98B5E"
PIP_LIGHT = "#E0AE7E"
PIP_CREAM = "#F5E3C8"
PIP_PINK = "#E8A0A0"
PIP_ORANGE = "#F08A28"
PIP_ORANGE_DARK = "#CC6A16"
PIP_BLUSH = "#F0B8B0"

OLLIE_COAT = "#C8A98A"
OLLIE_DARK = "#A98463"
OLLIE_CREAM = "#F2E2C8"
OLLIE_HOOF = "#5A3E2B"
OLLIE_MANE = "#6B4A2E"
OLLIE_TEAL = "#2C8C96"
OLLIE_TEAL_DARK = "#1E6B74"

EYE_DARK = "#2B1B12"
WHITE = "#FFFFFF"


def pip() -> list[dict]:
    p: list[dict] = []
    p.append(ellipse("shadow", 512, 930, 185, 26, "#C9C9C9"))
    p.append(ellipse("tail", 710, 800, 55, 50, PIP_FUR, OUTLINE, 8))
    p.append(ellipse("legs", 445, 850, 55, 90, PIP_FUR, OUTLINE, 8))
    p.append(ellipse("legs", 575, 850, 55, 90, PIP_FUR, OUTLINE, 8))
    p.append(ellipse("legs", 445, 930, 78, 38, PIP_CREAM, OUTLINE, 8))
    p.append(ellipse("legs", 575, 930, 78, 38, PIP_CREAM, OUTLINE, 8))
    p.append(ellipse("body", 512, 700, 150, 195, PIP_FUR, OUTLINE, 8))
    p.append(ellipse("body", 512, 740, 100, 135, PIP_CREAM))
    p.append(ellipse("arms", 365, 690, 42, 105, PIP_FUR, OUTLINE, 8))
    p.append(ellipse("arms", 659, 690, 42, 105, PIP_FUR, OUTLINE, 8))
    p.append(ellipse("arms", 360, 800, 45, 40, PIP_CREAM, OUTLINE, 8))
    p.append(ellipse("arms", 664, 800, 45, 40, PIP_CREAM, OUTLINE, 8))
    p.append(ellipse("ears", 395, 190, 58, 160, PIP_FUR, OUTLINE, 8))
    p.append(ellipse("ears", 629, 190, 58, 160, PIP_FUR, OUTLINE, 8))
    p.append(ellipse("ears", 395, 190, 32, 120, PIP_PINK))
    p.append(ellipse("ears", 629, 190, 32, 120, PIP_PINK))
    p.append(
        polygon(
            "neckerchief",
            [(390, 620), (634, 620), (646, 660), (512, 700), (378, 660)],
            PIP_ORANGE,
            OUTLINE,
            8,
        )
    )
    p.append(polygon("neckerchief", [(430, 660), (594, 660), (512, 790)], PIP_ORANGE, OUTLINE, 8))
    p.append(circle("neckerchief", 512, 660, 30, PIP_ORANGE_DARK, OUTLINE, 8))
    p.append(circle("neckerchief", 504, 650, 9, "#FFC06A"))
    p.append(ellipse("head", 512, 405, 190, 175, PIP_FUR, OUTLINE, 8))
    p.append(ellipse("face", 430, 475, 36, 22, PIP_BLUSH))
    p.append(ellipse("face", 594, 475, 36, 22, PIP_BLUSH))
    p.append(ellipse("face", 450, 405, 42, 52, WHITE, OUTLINE, 6))
    p.append(ellipse("face", 574, 405, 42, 52, WHITE, OUTLINE, 6))
    p.append(ellipse("face", 455, 415, 22, 30, EYE_DARK))
    p.append(ellipse("face", 579, 415, 22, 30, EYE_DARK))
    p.append(circle("face", 448, 400, 9, WHITE))
    p.append(circle("face", 572, 400, 9, WHITE))
    p.append(circle("face", 462, 428, 4, WHITE))
    p.append(circle("face", 586, 428, 4, WHITE))
    p.append(ellipse("face", 512, 470, 20, 14, PIP_PINK, OUTLINE, 5))
    p.append(line("face", [(512, 484), (512, 500)], OUTLINE, 5))
    p.append(arc("face", (480, 478, 512, 515), 0, 180, OUTLINE, 5))
    p.append(arc("face", (512, 478, 544, 515), 0, 180, OUTLINE, 5))
    for pts in (
        [(400, 468), (330, 458)],
        [(400, 485), (325, 485)],
        [(400, 502), (330, 512)],
        [(624, 468), (694, 458)],
        [(624, 485), (699, 485)],
        [(624, 502), (694, 512)],
    ):
        p.append(line("face", pts, OUTLINE, 4))
    p.append(
        polygon(
            "hair",
            [(490, 240), (503, 205), (514, 235), (529, 200), (540, 240), (521, 256), (500, 256)],
            PIP_FUR,
            OUTLINE,
            6,
        )
    )
    return p


def ollie() -> list[dict]:
    p: list[dict] = []
    p.append(ellipse("shadow", 512, 930, 180, 26, "#C9C9C9"))
    p.append(ellipse("tail", 715, 770, 45, 65, OLLIE_COAT, OUTLINE, 8))
    p.append(polygon("tail", [(735, 825), (770, 850), (742, 840), (752, 870), (725, 842)], OLLIE_MANE, OUTLINE, 6))
    p.append(ellipse("legs", 445, 850, 52, 88, OLLIE_COAT, OUTLINE, 8))
    p.append(ellipse("legs", 575, 850, 52, 88, OLLIE_COAT, OUTLINE, 8))
    p.append(ellipse("legs", 445, 930, 70, 34, OLLIE_HOOF, OUTLINE, 8))
    p.append(ellipse("legs", 575, 930, 70, 34, OLLIE_HOOF, OUTLINE, 8))
    p.append(ellipse("body", 512, 700, 145, 190, OLLIE_COAT, OUTLINE, 8))
    p.append(ellipse("body", 512, 730, 95, 125, OLLIE_CREAM))
    p.append(ellipse("arms", 370, 680, 40, 100, OLLIE_COAT, OUTLINE, 8))
    p.append(ellipse("arms", 654, 680, 40, 100, OLLIE_COAT, OUTLINE, 8))
    p.append(ellipse("arms", 360, 780, 44, 38, OLLIE_HOOF, OUTLINE, 8))
    p.append(ellipse("arms", 664, 780, 44, 38, OLLIE_HOOF, OUTLINE, 8))
    p.append(ellipse("ears", 390, 175, 52, 160, OLLIE_COAT, OUTLINE, 8))
    p.append(ellipse("ears", 634, 175, 52, 160, OLLIE_COAT, OUTLINE, 8))
    p.append(ellipse("ears", 390, 175, 30, 120, "#E8C9A8"))
    p.append(ellipse("ears", 634, 175, 30, 120, "#E8C9A8"))
    p.append(
        polygon(
            "neckerchief",
            [(400, 600), (624, 600), (638, 640), (512, 675), (386, 640)],
            OLLIE_TEAL,
            OUTLINE,
            8,
        )
    )
    p.append(polygon("neckerchief", [(438, 640), (586, 640), (512, 760)], OLLIE_TEAL, OUTLINE, 8))
    p.append(circle("neckerchief", 512, 640, 30, OLLIE_TEAL_DARK, OUTLINE, 8))
    p.append(circle("neckerchief", 504, 630, 9, "#7FD0D8"))
    p.append(ellipse("head", 512, 390, 175, 170, OLLIE_COAT, OUTLINE, 8))
    p.append(ellipse("face", 512, 480, 110, 78, OLLIE_CREAM, OUTLINE, 8))
    p.append(ellipse("face", 452, 380, 40, 50, WHITE, OUTLINE, 6))
    p.append(ellipse("face", 572, 380, 40, 50, WHITE, OUTLINE, 6))
    p.append(ellipse("face", 457, 390, 21, 28, EYE_DARK))
    p.append(ellipse("face", 577, 390, 21, 28, EYE_DARK))
    p.append(circle("face", 450, 376, 8, WHITE))
    p.append(circle("face", 570, 376, 8, WHITE))
    p.append(circle("face", 463, 402, 4, WHITE))
    p.append(circle("face", 583, 402, 4, WHITE))
    p.append(ellipse("face", 485, 480, 16, 10, OLLIE_HOOF))
    p.append(ellipse("face", 539, 480, 16, 10, OLLIE_HOOF))
    p.append(line("face", [(490, 515), (512, 525), (534, 515)], OUTLINE, 5))
    p.append(
        polygon(
            "hair",
            [
                (480, 225),
                (495, 190),
                (505, 220),
                (520, 185),
                (530, 220),
                (545, 190),
                (552, 235),
                (525, 245),
                (500, 245),
            ],
            OLLIE_MANE,
            OUTLINE,
            6,
        )
    )
    return p


def svg_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_svg(prims: list[dict], path: Path, silhouette: bool = False) -> None:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'  <rect width="{W}" height="{H}" fill="{BG}"/>',
    ]
    current = None
    for prim in prims:
        group = prim["group"]
        if silhouette and group == "face":
            continue
        if silhouette and group == "shadow":
            continue
        if group != current:
            if current is not None:
                parts.append("  </g>")
            parts.append(f'  <g id="{group}">')
            current = group
        fill = OUTLINE if silhouette else prim.get("fill")
        stroke = OUTLINE if silhouette else prim.get("stroke")
        width = prim.get("width", 0)
        kind = prim["kind"]
        if kind == "ellipse":
            parts.append(
                f'    <ellipse cx="{prim["cx"]}" cy="{prim["cy"]}" rx="{prim["rx"]}" ry="{prim["ry"]}" '
                f'fill="{fill}" stroke="{stroke or "none"}" stroke-width="{width}"/>'
            )
        elif kind == "circle":
            parts.append(
                f'    <circle cx="{prim["cx"]}" cy="{prim["cy"]}" r="{prim["r"]}" '
                f'fill="{fill}" stroke="{stroke or "none"}" stroke-width="{width}"/>'
            )
        elif kind == "polygon":
            points = " ".join(f"{x},{y}" for x, y in prim["points"])
            parts.append(
                f'    <polygon points="{points}" fill="{fill}" stroke="{stroke or "none"}" '
                f'stroke-width="{width}" stroke-linejoin="round"/>'
            )
        elif kind == "line":
            points = " ".join(f"{x},{y}" for x, y in prim["points"])
            parts.append(
                f'    <polyline points="{points}" fill="none" stroke="{stroke}" '
                f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'
            )
        elif kind == "rect":
            parts.append(
                f'    <rect x="{prim["x"]}" y="{prim["y"]}" width="{prim["w"]}" height="{prim["h"]}" '
                f'rx="{prim["r"]}" fill="{fill}" stroke="{stroke or "none"}" stroke-width="{width}"/>'
            )
        elif kind == "arc":
            x0, y0, x1, y1 = prim["box"]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
            a0, a1 = math.radians(prim["start"]), math.radians(prim["end"])
            sx, sy = cx + rx * math.cos(a0), cy + ry * math.sin(a0)
            ex, ey = cx + rx * math.cos(a1), cy + ry * math.sin(a1)
            large = 1 if abs(prim["end"] - prim["start"]) > 180 else 0
            sweep = 1 if prim["end"] >= prim["start"] else 0
            parts.append(
                f'    <path d="M {sx:.2f} {sy:.2f} A {rx:.2f} {ry:.2f} 0 {large} {sweep} {ex:.2f} {ey:.2f}" '
                f'fill="none" stroke="{stroke}" stroke-width="{width}" stroke-linecap="round"/>'
            )
    if current is not None:
        parts.append("  </g>")
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def render_png(prims: list[dict], path: Path, silhouette: bool = False) -> None:
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    for prim in prims:
        group = prim["group"]
        if silhouette and group in {"face", "shadow"}:
            continue
        fill = OUTLINE if silhouette else prim.get("fill")
        stroke = OUTLINE if silhouette else prim.get("stroke")
        width = max(1, int(prim.get("width", 0)))
        kind = prim["kind"]
        if kind == "ellipse":
            box = [prim["cx"] - prim["rx"], prim["cy"] - prim["ry"], prim["cx"] + prim["rx"], prim["cy"] + prim["ry"]]
            draw.ellipse(box, fill=fill, outline=stroke, width=width if stroke else 0)
        elif kind == "circle":
            box = [prim["cx"] - prim["r"], prim["cy"] - prim["r"], prim["cx"] + prim["r"], prim["cy"] + prim["r"]]
            draw.ellipse(box, fill=fill, outline=stroke, width=width if stroke else 0)
        elif kind == "polygon":
            draw.polygon(prim["points"], fill=fill)
            if stroke:
                draw.line(prim["points"] + [prim["points"][0]], fill=stroke, width=width, joint="curve")
        elif kind == "line":
            draw.line(prim["points"], fill=stroke, width=width, joint="curve")
        elif kind == "rect":
            draw.rounded_rectangle(
                [prim["x"], prim["y"], prim["x"] + prim["w"], prim["y"] + prim["h"]],
                radius=prim["r"],
                fill=fill,
                outline=stroke,
                width=width if stroke else 0,
            )
        elif kind == "arc":
            draw.arc(prim["box"], start=prim["start"], end=prim["end"], fill=stroke, width=width)
    image.save(path)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main() -> None:
    manifest = {"canvas": [W, H], "background": BG, "status": "exploratory vector draft; not registered; not canonical", "characters": {}}
    for name, builder in (("pip", pip), ("ollie", ollie)):
        prims = builder()
        svg = OUT / f"{name}_v1.svg"
        png = OUT / f"{name}_v1.png"
        sil_svg = OUT / f"{name}_v1_silhouette.svg"
        sil_png = OUT / f"{name}_v1_silhouette.png"
        render_svg(prims, svg)
        render_png(prims, png)
        render_svg(prims, sil_svg, silhouette=True)
        render_png(prims, sil_png, silhouette=True)
        manifest["characters"][name] = {
            "svg": svg.name,
            "png": png.name,
            "silhouette_svg": sil_svg.name,
            "silhouette_png": sil_png.name,
            "shapes": len(prims),
            "svg_sha256_16": sha(svg),
            "png_sha256_16": sha(png),
        }
        print(name, "shapes", len(prims), "->", png)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("WROTE", OUT / "manifest.json")


if __name__ == "__main__":
    main()
