"""Build CHARACTER LOCK PACK V3.

Deterministic vector art for Pip/Ollie plus a Leo no-backpack star-patch draft.
Reads the live DB read-only. Writes only new files under
docs/operations/character_lock_v3/. No registration, approval, canonicalization,
model generation, audio, video or service changes.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import build_vector_character_drafts as v1  # noqa: E402

ROOT = SCRIPTS.parent
OUT = ROOT / "docs" / "operations" / "character_lock_v3"
DB = ROOT / "data" / "cartoon_studio.db"
V4 = ROOT / "outputs" / "16556b67d331" / "e0012667d951" / "e0012667d951_00001_.png"
CANONICAL = {"Leo": "40abe63ea726", "Mira": "bf635873d12a", "Toby": "9b8b72c08301", "Bruno": "6c02a5ba1e37"}
FONT = r"C:\Windows\Fonts\segoeui.ttf"
FONT_B = r"C:\Windows\Fonts\segoeuib.ttf"

OUTLINE = v1.OUTLINE
WHITE = v1.WHITE
EYE = v1.EYE_DARK
BG = v1.BG

PIP = dict(fur="#C98B5E", fur_d="#AE7146", fur_l="#E0AE7E", cream="#F5E3C8", cream_d="#E6CDA9",
           pink="#E8A0A0", pink_d="#CE8585", orange="#F08A28", orange_d="#C96A14",
           orange_l="#FFB25A", blush="#F0B8B0")
OLLIE = dict(coat="#C8A98A", coat_d="#A98463", coat_l="#DDC3A6", cream="#F2E2C8",
             cream_d="#E0CBA9", hoof="#5A3E2B", mane="#6B4A2E", mane_d="#51351F",
             mane_l="#8A6440", teal="#2C8C96", teal_d="#1E6B74", teal_l="#58B8C0",
             blush="#E7B79E")


def ell(group, cx, cy, rx, ry, fill, stroke=None, width=0):
    return v1.ellipse(group, cx, cy, rx, ry, fill, stroke, width)


def circ(group, cx, cy, r, fill, stroke=None, width=0):
    return v1.circle(group, cx, cy, r, fill, stroke, width)


def poly(group, pts, fill, stroke=None, width=0):
    return v1.polygon(group, pts, fill, stroke, width)


def line(group, pts, stroke=OUTLINE, width=4):
    return v1.line(group, pts, stroke, width)


def arc(group, box, start, end, stroke=OUTLINE, width=4):
    return v1.arc(group, box, start, end, stroke, width)


def rot_ellipse(cx, cy, rx, ry, angle, segments=44):
    rad = math.radians(angle)
    pts = []
    for i in range(segments):
        t = 2 * math.pi * i / segments
        x, y = rx * math.cos(t), ry * math.sin(t)
        pts.append((cx + x * math.cos(rad) - y * math.sin(rad),
                    cy + x * math.sin(rad) + y * math.cos(rad)))
    return pts


def star_pts(cx, cy, ro, ri, points=5, rot=-90):
    pts = []
    for i in range(points * 2):
        r = ro if i % 2 == 0 else ri
        a = math.radians(rot + i * 180 / points)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def shadow(y=930, rx=170):
    return [ell("shadow", 512, y, rx, 24, "#CFCFCF")]


def hit(pts, dx=0, dy=0):
    return [(x + dx, y + dy) for x, y in pts]


def scale_groups(prims, groups, cx, cy, factor, dy=0.0):
    """Scale selected primitive groups about a pivot (used to de-chibi the head)."""
    out = []
    for prim in prims:
        if prim["group"] not in groups:
            out.append(prim)
            continue
        p = dict(prim)
        kind = p["kind"]
        if kind in ("ellipse",):
            p["cx"] = cx + (p["cx"] - cx) * factor
            p["cy"] = cy + (p["cy"] - cy) * factor + dy
            p["rx"] *= factor
            p["ry"] *= factor
        elif kind == "circle":
            p["cx"] = cx + (p["cx"] - cx) * factor
            p["cy"] = cy + (p["cy"] - cy) * factor + dy
            p["r"] *= factor
        elif kind in ("polygon", "line"):
            p["points"] = [(cx + (x - cx) * factor, cy + (y - cy) * factor + dy) for x, y in p["points"]]
        elif kind == "rect":
            p["x"] = cx + (p["x"] - cx) * factor
            p["y"] = cy + (p["y"] - cy) * factor + dy
            p["w"] *= factor
            p["h"] *= factor
        elif kind == "arc":
            x0, y0, x1, y1 = p["box"]
            p["box"] = (cx + (x0 - cx) * factor, cy + (y0 - cy) * factor + dy,
                        cx + (x1 - cx) * factor, cy + (y1 - cy) * factor + dy)
        out.append(p)
    return out


HEAD_PIVOT = {
    ("pip", "front"): (512, 352), ("pip", "three_quarter"): (548, 350),
    ("pip", "side"): (548, 348), ("pip", "back"): (512, 352),
    ("ollie", "front"): (512, 336), ("ollie", "three_quarter"): (548, 334),
    ("ollie", "side"): (552, 332), ("ollie", "back"): (512, 336),
}
HEAD_GROUPS = {"head", "ears", "face", "hair", "shade_head"}


def drape_front(cx, y, color, dark, light, scale=1.0):
    p = []
    w = 92 * scale
    p.append(poly("neckerchief", [(cx - w, y), (cx + w, y), (cx + w - 10, y + 28),
                                  (cx, y + 46), (cx - w + 10, y + 28)], color, OUTLINE, 6))
    p.append(poly("neckerchief", [(cx - w + 14, y + 6), (cx + w - 14, y + 6),
                                  (cx + w - 26, y + 26), (cx, y + 38), (cx - w + 26, y + 26)], light))
    p.append(poly("neckerchief", [(cx - 74 * scale, y + 26), (cx + 74 * scale, y + 26),
                                  (cx + 58 * scale, y + 96 * scale), (cx + 18 * scale, y + 132 * scale),
                                  (cx - 2 * scale, y + 108 * scale), (cx - 34 * scale, y + 128 * scale),
                                  (cx - 66 * scale, y + 78 * scale)], color, OUTLINE, 6))
    p.append(poly("neckerchief", [(cx + 6, y + 34), (cx + 62 * scale, y + 34),
                                  (cx + 40 * scale, y + 96 * scale), (cx + 10, y + 112)], dark))
    p.append(poly("neckerchief", [(cx - 56 * scale, y + 40), (cx - 22 * scale, y + 38),
                                  (cx - 30 * scale, y + 96 * scale), (cx - 52 * scale, y + 82)], light))
    p.append(line("neckerchief", [(cx - 30, y + 44), (cx - 20, y + 100)], dark, 3))
    p.append(line("neckerchief", [(cx + 34, y + 42), (cx + 24, y + 104)], dark, 3))
    p.append(poly("neckerchief", [(cx - 34, y + 112), (cx - 12, y + 116), (cx - 26, y + 156)],
                  color, OUTLINE, 5))
    p.append(poly("neckerchief", [(cx + 2, y + 112), (cx + 26, y + 112), (cx + 38, y + 146)],
                  color, OUTLINE, 5))
    p.append(circ("neckerchief", cx, y + 22, 24, dark, OUTLINE, 5))
    p.append(circ("neckerchief", cx - 4, y + 18, 8, light))
    return p


def drape_side(cx, y, color, dark, light):
    p = []
    p.append(poly("neckerchief", [(cx - 46, y), (cx + 48, y), (cx + 40, y + 30),
                                  (cx + 2, y + 44), (cx - 42, y + 26)], color, OUTLINE, 6))
    p.append(poly("neckerchief", [(cx - 30, y + 24), (cx + 38, y + 24), (cx + 52, y + 90),
                                  (cx + 30, y + 120), (cx + 12, y + 100), (cx - 4, y + 116),
                                  (cx - 22, y + 78)], color, OUTLINE, 6))
    p.append(poly("neckerchief", [(cx + 10, y + 28), (cx + 38, y + 28), (cx + 44, y + 82),
                                  (cx + 26, y + 104)], dark))
    p.append(poly("neckerchief", [(cx - 18, y + 28), (cx + 2, y + 28), (cx - 2, y + 78),
                                  (cx - 16, y + 68)], light))
    p.append(circ("neckerchief", cx + 26, y + 18, 19, dark, OUTLINE, 5))
    p.append(circ("neckerchief", cx + 23, y + 15, 6, light))
    p.append(poly("neckerchief", [(cx + 34, y + 30), (cx + 50, y + 28), (cx + 66, y + 74)],
                  color, OUTLINE, 5))
    return p


def drape_back(cx, y, color, dark, light):
    p = []
    p.append(poly("neckerchief", [(cx - 86, y), (cx + 86, y), (cx + 78, y + 28),
                                  (cx, y + 40), (cx - 78, y + 28)], color, OUTLINE, 6))
    p.append(poly("neckerchief", [(cx - 68, y + 8), (cx + 68, y + 8), (cx + 60, y + 24),
                                  (cx, y + 32), (cx - 60, y + 24)], dark))
    p.append(line("neckerchief", [(cx - 54, y + 30), (cx - 44, y + 46)], dark, 3))
    p.append(line("neckerchief", [(cx + 54, y + 30), (cx + 44, y + 46)], dark, 3))
    return p


def eye_pair(cx, cy, gap=54, ew=34, eh=42, pupil=20, look=(0, 0), expr="neutral", scale=1.0):
    p = []
    ew, eh, pupil = ew * scale, eh * scale, pupil * scale
    for side in (-1, 1):
        ex = cx + side * gap * scale
        p.append(ell("face", ex, cy, ew, eh, WHITE, OUTLINE, 5))
        p.append(ell("face", ex + look[0], cy + 4 * scale + look[1], pupil, pupil * 1.35, EYE))
        p.append(circ("face", ex - 7 * scale + look[0], cy - 8 * scale + look[1], 6 * scale, WHITE))
        p.append(circ("face", ex + 6 * scale + look[0], cy + 12 * scale + look[1], 3 * scale, WHITE))
        if expr == "happy":
            p.append(line("face", [(ex - ew * 0.62, cy + eh * 0.52), (ex, cy + eh * 0.72),
                                   (ex + ew * 0.62, cy + eh * 0.52)], OUTLINE, 4))
            p.append(line("face", [(ex - ew * 0.45, cy + eh * 0.86), (ex - ew * 0.1, cy + eh * 0.92)], OUTLINE, 3))
        elif expr == "curious" and side == 1:
            p.append(arc("face", (ex - ew, cy - eh * 0.45, ex + ew, cy + eh * 0.1), 200, 340, OUTLINE, 4))
    if expr == "happy":
        p.append(line("face", [(cx - 70 * scale, cy - 62 * scale), (cx - 28 * scale, cy - 72 * scale),
                               (cx - 8 * scale, cy - 60 * scale)], OUTLINE, 5))
        p.append(line("face", [(cx + 70 * scale, cy - 62 * scale), (cx + 28 * scale, cy - 72 * scale),
                               (cx + 8 * scale, cy - 60 * scale)], OUTLINE, 5))
    elif expr == "curious":
        p.append(line("face", [(cx - 72 * scale, cy - 58 * scale), (cx - 28 * scale, cy - 58 * scale)], OUTLINE, 5))
        p.append(line("face", [(cx + 30 * scale, cy - 78 * scale), (cx + 72 * scale, cy - 70 * scale),
                               (cx + 86 * scale, cy - 82 * scale)], OUTLINE, 5))
    else:
        p.append(line("face", [(cx - 72 * scale, cy - 60 * scale), (cx - 26 * scale, cy - 66 * scale)], OUTLINE, 5))
        p.append(line("face", [(cx + 72 * scale, cy - 60 * scale), (cx + 26 * scale, cy - 66 * scale)], OUTLINE, 5))
    return p


def pip_head(cx, cy, expr="neutral", scale=1.0, view="front", far=False):
    p = []
    rx, ry = 150 * scale, 140 * scale
    # ears behind head
    if view in ("front", "three_quarter", "back"):
        p.append(poly("ears", rot_ellipse(cx - 84 * scale, cy - 150 * scale, 42 * scale, 125 * scale, -7), PIP["fur"], OUTLINE, 7))
        p.append(poly("ears", rot_ellipse(cx + 84 * scale, cy - 150 * scale, 42 * scale, 125 * scale, 7), PIP["fur"], OUTLINE, 7))
        if view != "back":
            p.append(poly("ears", rot_ellipse(cx - 84 * scale, cy - 148 * scale, 22 * scale, 96 * scale, -7), PIP["pink"]))
            p.append(poly("ears", rot_ellipse(cx + 84 * scale, cy - 148 * scale, 22 * scale, 96 * scale, 7), PIP["pink"]))
    elif view == "side":
        p.append(poly("ears", rot_ellipse(cx - 108 * scale, cy - 148 * scale, 40 * scale, 126 * scale, -9), PIP["fur"], OUTLINE, 7))
        p.append(poly("ears", rot_ellipse(cx - 106 * scale, cy - 146 * scale, 20 * scale, 96 * scale, -9), PIP["pink"]))
        p.append(poly("ears", rot_ellipse(cx - 150 * scale, cy - 128 * scale, 28 * scale, 104 * scale, -22), PIP["fur_d"], OUTLINE, 6))
    p.append(ell("head", cx, cy, rx, ry, PIP["fur"], OUTLINE, 8))
    # shading + highlight
    p.append(poly("shade_head", [(cx + 40 * scale, cy - 120 * scale), (cx + 140 * scale, cy - 40 * scale),
                            (cx + 120 * scale, cy + 100 * scale), (cx + 46 * scale, cy + 120 * scale)],
                  PIP["fur_d"]))
    p.append(ell("shade_head", cx - 52 * scale, cy - 48 * scale, 62 * scale, 40 * scale, PIP["fur_l"]))
    if view == "back":
        p.append(ell("shade_head", cx - 36 * scale, cy - 66 * scale, 50 * scale, 34 * scale, PIP["fur_l"]))
        return p
    # face
    if view == "front":
        p += eye_pair(cx, cy - 12 * scale, 56, 34, 42, 20,
                      (7, -2) if expr == "curious" else (0, 0), expr, scale)
        p.append(ell("face", cx, cy + 46 * scale, 58 * scale, 38 * scale, PIP["cream"], OUTLINE, 5))
        p.append(ell("face", cx, cy + 34 * scale, 13 * scale, 10 * scale, PIP["pink"], OUTLINE, 4))
        p.append(line("face", [(cx, cy + 44 * scale), (cx, cy + 52 * scale)], OUTLINE, 4))
        if expr == "happy":
            p.append(arc("face", (cx - 40 * scale, cy + 50 * scale, cx + 40 * scale, cy + 92 * scale), 15, 165, OUTLINE, 5))
            p.append(line("face", [(cx - 16 * scale, cy + 68 * scale), (cx + 16 * scale, cy + 68 * scale)], OUTLINE, 3))
        elif expr == "curious":
            p.append(ell("face", cx, cy + 64 * scale, 11 * scale, 13 * scale, EYE))
        else:
            p.append(arc("face", (cx - 26 * scale, cy + 52 * scale, cx, cy + 72 * scale), 0, 180, OUTLINE, 4))
            p.append(arc("face", (cx, cy + 52 * scale, cx + 26 * scale, cy + 72 * scale), 0, 180, OUTLINE, 4))
        p.append(ell("face", cx - 104 * scale, cy + 34 * scale, 30 * scale, 17 * scale, PIP["blush"]))
        p.append(ell("face", cx + 104 * scale, cy + 34 * scale, 30 * scale, 17 * scale, PIP["blush"]))
        for dy in (-8, 4, 16):
            p.append(line("face", [(cx - 96 * scale, cy + (48 + dy) * scale), (cx - 150 * scale, cy + (40 + dy) * scale)], OUTLINE, 3))
            p.append(line("face", [(cx + 96 * scale, cy + (48 + dy) * scale), (cx + 150 * scale, cy + (40 + dy) * scale)], OUTLINE, 3))
    elif view == "three_quarter":
        p.append(ell("face", cx + 18 * scale, cy + 48 * scale, 62 * scale, 40 * scale, PIP["cream"], OUTLINE, 5))
        p.append(ell("face", cx + 14 * scale, cy + 36 * scale, 12 * scale, 9 * scale, PIP["pink"], OUTLINE, 4))
        p.append(ell("face", cx - 34 * scale, cy - 10 * scale, 34 * scale, 44 * scale, WHITE, OUTLINE, 5))
        p.append(ell("face", cx - 32 * scale, cy - 2 * scale, 20 * scale, 28 * scale, EYE))
        p.append(circ("face", cx - 39 * scale, cy - 14 * scale, 6 * scale, WHITE))
        p.append(ell("face", cx + 64 * scale, cy - 12 * scale, 24 * scale, 34 * scale, WHITE, OUTLINE, 5))
        p.append(ell("face", cx + 68 * scale, cy - 5 * scale, 15 * scale, 22 * scale, EYE))
        p.append(circ("face", cx + 63 * scale, cy - 15 * scale, 5 * scale, WHITE))
        p.append(line("face", [(cx - 62 * scale, cy - 62 * scale), (cx - 16 * scale, cy - 66 * scale)], OUTLINE, 5))
        p.append(line("face", [(cx + 46 * scale, cy - 62 * scale), (cx + 88 * scale, cy - 58 * scale)], OUTLINE, 5))
        p.append(arc("face", (cx - 6 * scale, cy + 54 * scale, cx + 42 * scale, cy + 76 * scale), 0, 170, OUTLINE, 4))
        p.append(ell("face", cx - 66 * scale, cy + 36 * scale, 26 * scale, 15 * scale, PIP["blush"]))
    elif view == "side":
        p.append(ell("face", cx + 74 * scale, cy + 32 * scale, 44 * scale, 32 * scale, PIP["cream"], OUTLINE, 5))
        p.append(ell("face", cx + 108 * scale, cy + 22 * scale, 12 * scale, 9 * scale, PIP["pink"], OUTLINE, 4))
        p.append(ell("face", cx + 8 * scale, cy - 12 * scale, 32 * scale, 42 * scale, WHITE, OUTLINE, 5))
        p.append(ell("face", cx + 14 * scale, cy - 4 * scale, 19 * scale, 27 * scale, EYE))
        p.append(circ("face", cx + 7 * scale, cy - 16 * scale, 6 * scale, WHITE))
        p.append(line("face", [(cx - 24 * scale, cy - 58 * scale), (cx + 28 * scale, cy - 64 * scale)], OUTLINE, 5))
        p.append(arc("face", (cx + 62 * scale, cy + 40 * scale, cx + 100 * scale, cy + 62 * scale), 10, 160, OUTLINE, 4))
        for dy in (-4, 8, 20):
            p.append(line("face", [(cx + 96 * scale, cy + (40 + dy) * scale), (cx + 146 * scale, cy + (32 + dy) * scale)], OUTLINE, 3))
    return p


def pip_body_front(expr="neutral"):
    p = []
    p += shadow()
    p.append(ell("tail", 704, 770, 44, 36, PIP["fur"], OUTLINE, 7))
    p.append(poly("tail", [(726, 790), (764, 816), (740, 812), (752, 844), (722, 818)], PIP["fur_l"], OUTLINE, 4))
    p.append(poly("legs", [(458, 744), (500, 744), (506, 900), (486, 922), (452, 918), (446, 898)], PIP["fur"], OUTLINE, 7))
    p.append(poly("legs", [(566, 744), (524, 744), (518, 900), (538, 922), (572, 918), (578, 898)], PIP["fur"], OUTLINE, 7))
    p.append(ell("legs", 452, 922, 64, 28, PIP["cream"], OUTLINE, 6))
    p.append(ell("legs", 572, 922, 64, 28, PIP["cream"], OUTLINE, 6))
    body = [(512, 462), (596, 500), (626, 610), (618, 754), (574, 812), (512, 832),
            (450, 812), (406, 754), (398, 610), (428, 500)]
    p.append(poly("body", body, PIP["fur"], OUTLINE, 8))
    p.append(poly("shade", [(560, 500), (626, 610), (618, 754), (574, 812), (548, 806), (566, 700), (566, 560)], PIP["fur_d"]))
    p.append(ell("body", 476, 620, 34, 90, PIP["fur_l"]))
    p.append(ell("body", 512, 690, 72, 104, PIP["cream"]))
    p.append(poly("arms", [(438, 512), (410, 526), (392, 620), (400, 712), (414, 744), (438, 736), (432, 640), (452, 556)], PIP["fur"], OUTLINE, 7))
    p.append(poly("arms", [(586, 512), (614, 526), (632, 620), (624, 712), (610, 744), (586, 736), (592, 640), (572, 556)], PIP["fur"], OUTLINE, 7))
    p.append(ell("arms", 426, 748, 28, 24, PIP["cream"], OUTLINE, 6))
    p.append(ell("arms", 598, 748, 28, 24, PIP["cream"], OUTLINE, 6))
    p += pip_head(512, 352, expr, 1.0, "front")
    p += drape_front(512, 496, PIP["orange"], PIP["orange_d"], PIP["orange_l"], 1.0)
    return p


def pip_body_three_quarter():
    p = []
    p += shadow(rx=160)
    p.append(ell("tail", 712, 770, 40, 34, PIP["fur"], OUTLINE, 7))
    p.append(poly("tail", [(732, 790), (768, 814), (744, 812), (756, 842), (726, 818)], PIP["fur_l"], OUTLINE, 4))
    p.append(poly("legs", [(470, 748), (512, 748), (520, 900), (500, 920), (466, 916), (460, 896)], PIP["fur_d"], OUTLINE, 6))
    p.append(poly("legs", [(574, 744), (534, 744), (530, 900), (550, 922), (584, 918), (590, 898)], PIP["fur"], OUTLINE, 7))
    p.append(ell("legs", 466, 920, 60, 26, PIP["cream_d"], OUTLINE, 6))
    p.append(ell("legs", 584, 922, 64, 28, PIP["cream"], OUTLINE, 6))
    body = [(522, 466), (600, 504), (620, 610), (610, 748), (566, 808), (508, 826),
            (452, 806), (414, 748), (408, 610), (442, 500)]
    p.append(poly("body", body, PIP["fur"], OUTLINE, 8))
    p.append(poly("shade", [(568, 500), (620, 610), (610, 748), (566, 808), (540, 802), (558, 700), (566, 560)], PIP["fur_d"]))
    p.append(ell("body", 486, 616, 32, 84, PIP["fur_l"]))
    p.append(ell("body", 520, 690, 68, 100, PIP["cream"]))
    p.append(poly("arms", [(600, 516), (628, 532), (642, 622), (632, 710), (616, 738), (594, 730), (600, 640), (584, 560)], PIP["fur"], OUTLINE, 7))
    p.append(ell("arms", 606, 742, 27, 23, PIP["cream"], OUTLINE, 6))
    p.append(poly("arms", [(454, 516), (428, 530), (414, 622), (424, 704), (438, 728), (458, 720), (452, 630), (468, 558)], PIP["fur_d"], OUTLINE, 6))
    p += pip_head(548, 350, "neutral", 0.98, "three_quarter")
    p += drape_front(536, 496, PIP["orange"], PIP["orange_d"], PIP["orange_l"], 0.94)
    return p


def pip_body_side():
    p = []
    p += shadow(rx=150)
    p.append(ell("tail", 398, 750, 40, 34, PIP["fur"], OUTLINE, 7))
    p.append(poly("tail", [(378, 768), (340, 792), (366, 790), (352, 820), (384, 796)], PIP["fur_l"], OUTLINE, 4))
    p.append(poly("legs", [(470, 752), (506, 752), (508, 900), (490, 920), (458, 916), (454, 896)], PIP["fur_d"], OUTLINE, 6))
    p.append(poly("legs", [(540, 748), (506, 748), (510, 900), (530, 922), (562, 918), (566, 898)], PIP["fur"], OUTLINE, 7))
    p.append(ell("legs", 458, 920, 58, 26, PIP["cream_d"], OUTLINE, 6))
    p.append(ell("legs", 562, 922, 60, 27, PIP["cream"], OUTLINE, 6))
    p.append(ell("body", 508, 650, 118, 168, PIP["fur"], OUTLINE, 8))
    p.append(poly("shade", [(560, 520), (614, 640), (600, 760), (556, 800), (540, 700), (548, 580)], PIP["fur_d"]))
    p.append(ell("body", 486, 620, 26, 76, PIP["fur_l"]))
    p.append(ell("body", 540, 690, 58, 96, PIP["cream"]))
    p.append(poly("arms", [(542, 520), (566, 530), (586, 620), (576, 700), (560, 724), (540, 716), (546, 630), (530, 556)], PIP["fur"], OUTLINE, 7))
    p.append(ell("arms", 552, 728, 26, 22, PIP["cream"], OUTLINE, 6))
    p += pip_head(548, 348, "neutral", 0.98, "side")
    p += drape_side(566, 496, PIP["orange"], PIP["orange_d"], PIP["orange_l"])
    return p


def pip_body_back():
    p = []
    p += shadow()
    p.append(ell("tail", 512, 748, 46, 40, PIP["fur"], OUTLINE, 7))
    p.append(poly("tail", [(536, 770), (574, 794), (550, 792), (562, 824), (532, 798)], PIP["fur_l"], OUTLINE, 4))
    p.append(poly("legs", [(458, 744), (500, 744), (506, 900), (486, 922), (452, 918), (446, 898)], PIP["fur"], OUTLINE, 7))
    p.append(poly("legs", [(566, 744), (524, 744), (518, 900), (538, 922), (572, 918), (578, 898)], PIP["fur"], OUTLINE, 7))
    p.append(ell("legs", 452, 922, 64, 28, PIP["cream"], OUTLINE, 6))
    p.append(ell("legs", 572, 922, 64, 28, PIP["cream"], OUTLINE, 6))
    body = [(512, 462), (596, 500), (626, 610), (618, 754), (574, 812), (512, 832),
            (450, 812), (406, 754), (398, 610), (428, 500)]
    p.append(poly("body", body, PIP["fur"], OUTLINE, 8))
    p.append(poly("shade", [(560, 500), (626, 610), (618, 754), (574, 812), (548, 806), (566, 700), (566, 560)], PIP["fur_d"]))
    p.append(poly("arms", [(438, 512), (410, 526), (392, 620), (400, 712), (414, 744), (438, 736), (432, 640), (452, 556)], PIP["fur"], OUTLINE, 7))
    p.append(poly("arms", [(586, 512), (614, 526), (632, 620), (624, 712), (610, 744), (586, 736), (592, 640), (572, 556)], PIP["fur"], OUTLINE, 7))
    p.append(ell("arms", 426, 748, 28, 24, PIP["cream"], OUTLINE, 6))
    p.append(ell("arms", 598, 748, 28, 24, PIP["cream"], OUTLINE, 6))
    p += pip_head(512, 352, "neutral", 1.0, "back")
    p += drape_back(512, 496, PIP["orange"], PIP["orange_d"], PIP["orange_l"])
    return p


def ollie_head(cx, cy, expr="neutral", scale=1.0, view="front"):
    p = []
    rx, ry = 146 * scale, 132 * scale
    # mane behind head/neck
    p.append(poly("hair", [(cx - 46, cy - 106), (cx - 78, cy - 30), (cx - 88, cy + 96),
                           (cx - 40, cy + 132), (cx + 20, cy + 136), (cx + 64, cy + 104),
                           (cx + 76, cy - 10), (cx + 40, cy - 112), (cx, cy - 132)],
                  OLLIE["mane"], OUTLINE, 6))
    if view in ("front", "three_quarter", "back"):
        p.append(poly("ears", rot_ellipse(cx - 92 * scale, cy - 150 * scale, 36 * scale, 132 * scale, -26), OLLIE["coat"], OUTLINE, 7))
        p.append(poly("ears", rot_ellipse(cx + 92 * scale, cy - 150 * scale, 36 * scale, 132 * scale, 26), OLLIE["coat"], OUTLINE, 7))
        if view != "back":
            p.append(poly("ears", rot_ellipse(cx - 92 * scale, cy - 148 * scale, 18 * scale, 102 * scale, -26), "#E8C9A8"))
            p.append(poly("ears", rot_ellipse(cx + 92 * scale, cy - 148 * scale, 18 * scale, 102 * scale, 26), "#E8C9A8"))
    elif view == "side":
        p.append(poly("ears", rot_ellipse(cx - 104 * scale, cy - 148 * scale, 34 * scale, 132 * scale, -16), OLLIE["coat"], OUTLINE, 7))
        p.append(poly("ears", rot_ellipse(cx - 102 * scale, cy - 146 * scale, 17 * scale, 102 * scale, -16), "#E8C9A8"))
        p.append(poly("ears", rot_ellipse(cx - 146 * scale, cy - 130 * scale, 26 * scale, 108 * scale, -34), OLLIE["coat_d"], OUTLINE, 6))
    p.append(ell("head", cx, cy, rx, ry, OLLIE["coat"], OUTLINE, 8))
    p.append(poly("shade_head", [(cx + 36 * scale, cy - 116 * scale), (cx + 138 * scale, cy - 30 * scale),
                            (cx + 118 * scale, cy + 96 * scale), (cx + 42 * scale, cy + 112 * scale)],
                  OLLIE["coat_d"]))
    p.append(ell("shade_head", cx - 50 * scale, cy - 44 * scale, 58 * scale, 38 * scale, OLLIE["coat_l"]))
    # forehead mane tuft
    p.append(poly("hair", [(cx - 34, cy - 116), (cx - 20, cy - 150), (cx - 4, cy - 126),
                           (cx + 14, cy - 158), (cx + 26, cy - 126), (cx + 46, cy - 146),
                           (cx + 40, cy - 108), (cx + 4, cy - 100)], OLLIE["mane"], OUTLINE, 5))
    if view == "back":
        p.append(poly("hair", [(cx - 18, cy - 96), (cx - 34, cy + 8), (cx - 28, cy + 100),
                               (cx - 6, cy + 128), (cx + 16, cy + 116), (cx + 24, cy + 18),
                               (cx + 16, cy - 92)], OLLIE["mane"], OUTLINE, 5))
        p.append(poly("hair", [(cx - 10, cy - 80), (cx - 20, cy + 6), (cx - 16, cy + 92),
                               (cx - 4, cy + 112), (cx + 6, cy + 104), (cx + 10, cy + 12),
                               (cx + 6, cy - 78)], OLLIE["mane_l"]))
        return p
    # long muzzle (front / 3q / side)
    if view == "front":
        p += eye_pair(cx, cy - 18 * scale, 54, 32, 42, 19,
                      (7, -2) if expr == "curious" else (0, 0), expr, scale)
        p.append(ell("face", cx, cy + 56 * scale, 82 * scale, 48 * scale, OLLIE["cream"], OUTLINE, 6))
        p.append(ell("face", cx, cy + 34 * scale, 30 * scale, 18 * scale, OLLIE["cream_d"]))
        p.append(ell("face", cx - 26 * scale, cy + 46 * scale, 9 * scale, 7 * scale, OLLIE["hoof"]))
        p.append(ell("face", cx + 26 * scale, cy + 46 * scale, 9 * scale, 7 * scale, OLLIE["hoof"]))
        p.append(line("face", [(cx, cy + 60 * scale), (cx, cy + 70 * scale)], OUTLINE, 4))
        if expr == "happy":
            p.append(arc("face", (cx - 48 * scale, cy + 62 * scale, cx + 48 * scale, cy + 108 * scale), 15, 165, OUTLINE, 5))
        elif expr == "curious":
            p.append(ell("face", cx, cy + 76 * scale, 11 * scale, 13 * scale, EYE))
        else:
            p.append(arc("face", (cx - 30 * scale, cy + 66 * scale, cx, cy + 88 * scale), 0, 180, OUTLINE, 4))
            p.append(arc("face", (cx, cy + 66 * scale, cx + 30 * scale, cy + 88 * scale), 0, 180, OUTLINE, 4))
        p.append(ell("face", cx - 106 * scale, cy + 24 * scale, 28 * scale, 16 * scale, OLLIE["blush"]))
        p.append(ell("face", cx + 106 * scale, cy + 24 * scale, 28 * scale, 16 * scale, OLLIE["blush"]))
    elif view == "three_quarter":
        p.append(ell("face", cx + 26 * scale, cy + 58 * scale, 86 * scale, 46 * scale, OLLIE["cream"], OUTLINE, 6))
        p.append(ell("face", cx + 18 * scale, cy + 38 * scale, 28 * scale, 16 * scale, OLLIE["cream_d"]))
        p.append(ell("face", cx - 36 * scale, cy - 16 * scale, 32 * scale, 43 * scale, WHITE, OUTLINE, 5))
        p.append(ell("face", cx - 32 * scale, cy - 8 * scale, 19 * scale, 27 * scale, EYE))
        p.append(circ("face", cx - 40 * scale, cy - 20 * scale, 6 * scale, WHITE))
        p.append(ell("face", cx + 62 * scale, cy - 18 * scale, 23 * scale, 33 * scale, WHITE, OUTLINE, 5))
        p.append(ell("face", cx + 66 * scale, cy - 10 * scale, 14 * scale, 21 * scale, EYE))
        p.append(circ("face", cx + 61 * scale, cy - 20 * scale, 5 * scale, WHITE))
        p.append(line("face", [(cx - 64 * scale, cy - 66 * scale), (cx - 18 * scale, cy - 70 * scale)], OUTLINE, 5))
        p.append(line("face", [(cx + 44 * scale, cy - 66 * scale), (cx + 86 * scale, cy - 62 * scale)], OUTLINE, 5))
        p.append(ell("face", cx - 72 * scale, cy + 28 * scale, 24 * scale, 14 * scale, OLLIE["blush"]))
    elif view == "side":
        p.append(ell("face", cx + 92 * scale, cy + 42 * scale, 68 * scale, 40 * scale, OLLIE["cream"], OUTLINE, 6))
        p.append(ell("face", cx + 78 * scale, cy + 26 * scale, 24 * scale, 14 * scale, OLLIE["cream_d"]))
        p.append(ell("face", cx + 154 * scale, cy + 34 * scale, 10 * scale, 7 * scale, OLLIE["hoof"]))
        p.append(ell("face", cx + 6 * scale, cy - 16 * scale, 31 * scale, 42 * scale, WHITE, OUTLINE, 5))
        p.append(ell("face", cx + 12 * scale, cy - 8 * scale, 19 * scale, 27 * scale, EYE))
        p.append(circ("face", cx + 5 * scale, cy - 20 * scale, 6 * scale, WHITE))
        p.append(line("face", [(cx - 26 * scale, cy - 64 * scale), (cx + 26 * scale, cy - 70 * scale)], OUTLINE, 5))
        p.append(arc("face", (cx + 96 * scale, cy + 48 * scale, cx + 138 * scale, cy + 72 * scale), 10, 160, OUTLINE, 4))
    return p


def ollie_body_front(expr="neutral"):
    p = []
    p += shadow(rx=176)
    p.append(ell("tail", 700, 730, 38, 54, OLLIE["coat"], OUTLINE, 7))
    p.append(poly("tail", [(712, 776), (748, 806), (722, 800), (734, 830), (704, 804)], OLLIE["mane"], OUTLINE, 4))
    p.append(poly("legs", [(456, 752), (498, 752), (502, 900), (484, 922), (452, 918), (446, 898)], OLLIE["coat"], OUTLINE, 7))
    p.append(poly("legs", [(568, 752), (526, 752), (522, 900), (540, 922), (572, 918), (578, 898)], OLLIE["coat"], OUTLINE, 7))
    p.append(ell("legs", 452, 924, 58, 28, OLLIE["hoof"], OUTLINE, 6))
    p.append(ell("legs", 572, 924, 58, 28, OLLIE["hoof"], OUTLINE, 6))
    body = [(512, 448), (604, 490), (632, 610), (620, 760), (572, 822), (512, 844),
            (452, 822), (404, 760), (392, 610), (420, 490)]
    p.append(poly("body", body, OLLIE["coat"], OUTLINE, 8))
    p.append(poly("shade", [(562, 490), (632, 610), (620, 760), (572, 822), (546, 812), (566, 700), (566, 550)], OLLIE["coat_d"]))
    p.append(ell("body", 474, 610, 32, 88, OLLIE["coat_l"]))
    p.append(ell("body", 512, 692, 82, 112, OLLIE["cream"]))
    p.append(poly("arms", [(432, 500), (402, 516), (384, 618), (394, 714), (410, 748), (434, 738), (426, 638), (448, 548)], OLLIE["coat"], OUTLINE, 7))
    p.append(poly("arms", [(592, 500), (622, 516), (640, 618), (630, 714), (614, 748), (590, 738), (598, 638), (576, 548)], OLLIE["coat"], OUTLINE, 7))
    p.append(ell("arms", 422, 752, 28, 22, OLLIE["hoof"], OUTLINE, 5))
    p.append(ell("arms", 602, 752, 28, 22, OLLIE["hoof"], OUTLINE, 5))
    p += ollie_head(512, 336, expr, 1.0, "front")
    p += drape_front(512, 490, OLLIE["teal"], OLLIE["teal_d"], OLLIE["teal_l"], 1.0)
    return p


def ollie_body_three_quarter():
    p = []
    p += shadow(rx=166)
    p.append(ell("tail", 708, 732, 36, 52, OLLIE["coat"], OUTLINE, 7))
    p.append(poly("tail", [(720, 778), (754, 806), (730, 802), (742, 830), (712, 806)], OLLIE["mane"], OUTLINE, 4))
    p.append(poly("legs", [(470, 754), (512, 754), (518, 900), (500, 920), (466, 916), (460, 896)], OLLIE["coat_d"], OUTLINE, 6))
    p.append(poly("legs", [(574, 750), (534, 750), (530, 900), (550, 922), (584, 918), (590, 898)], OLLIE["coat"], OUTLINE, 7))
    p.append(ell("legs", 466, 920, 54, 26, OLLIE["hoof"], OUTLINE, 5))
    p.append(ell("legs", 584, 922, 58, 27, OLLIE["hoof"], OUTLINE, 5))
    body = [(522, 452), (608, 492), (626, 610), (612, 754), (564, 816), (508, 836),
            (450, 814), (412, 754), (400, 610), (434, 492)]
    p.append(poly("body", body, OLLIE["coat"], OUTLINE, 8))
    p.append(poly("shade", [(566, 492), (626, 610), (612, 754), (564, 816), (538, 806), (558, 700), (566, 550)], OLLIE["coat_d"]))
    p.append(ell("body", 484, 610, 30, 82, OLLIE["coat_l"]))
    p.append(ell("body", 522, 690, 76, 106, OLLIE["cream"]))
    p.append(poly("arms", [(606, 506), (632, 522), (648, 618), (636, 710), (620, 740), (598, 732), (606, 638), (588, 552)], OLLIE["coat"], OUTLINE, 7))
    p.append(ell("arms", 610, 744, 27, 21, OLLIE["hoof"], OUTLINE, 5))
    p.append(poly("arms", [(452, 506), (426, 520), (410, 618), (420, 706), (436, 732), (456, 724), (450, 630), (466, 552)], OLLIE["coat_d"], OUTLINE, 6))
    p += ollie_head(548, 334, "neutral", 0.98, "three_quarter")
    p += drape_front(536, 490, OLLIE["teal"], OLLIE["teal_d"], OLLIE["teal_l"], 0.94)
    return p


def ollie_body_side():
    p = []
    p += shadow(rx=156)
    p.append(ell("tail", 392, 726, 34, 50, OLLIE["coat"], OUTLINE, 7))
    p.append(poly("tail", [(376, 772), (344, 800), (368, 796), (354, 824), (384, 800)], OLLIE["mane"], OUTLINE, 4))
    p.append(poly("legs", [(470, 756), (508, 756), (510, 900), (492, 920), (460, 916), (456, 896)], OLLIE["coat_d"], OUTLINE, 6))
    p.append(poly("legs", [(542, 752), (506, 752), (512, 900), (532, 922), (564, 918), (568, 898)], OLLIE["coat"], OUTLINE, 7))
    p.append(ell("legs", 460, 920, 54, 26, OLLIE["hoof"], OUTLINE, 5))
    p.append(ell("legs", 564, 922, 58, 27, OLLIE["hoof"], OUTLINE, 5))
    p.append(ell("body", 508, 640, 122, 172, OLLIE["coat"], OUTLINE, 8))
    p.append(poly("shade", [(558, 500), (618, 620), (604, 760), (558, 804), (540, 700), (548, 566)], OLLIE["coat_d"]))
    p.append(ell("body", 486, 610, 26, 74, OLLIE["coat_l"]))
    p.append(ell("body", 546, 690, 62, 100, OLLIE["cream"]))
    p.append(poly("arms", [(548, 510), (572, 520), (592, 616), (582, 700), (566, 730), (546, 722), (552, 630), (536, 546)], OLLIE["coat"], OUTLINE, 7))
    p.append(ell("arms", 558, 734, 26, 21, OLLIE["hoof"], OUTLINE, 5))
    p.append(poly("hair", [(500, 330), (462, 400), (450, 480), (458, 522), (486, 506),
                           (492, 430), (516, 360)], OLLIE["mane"], OUTLINE, 5))
    p.append(poly("hair", [(492, 356), (472, 408), (464, 474), (470, 502), (478, 492),
                           (480, 420), (500, 370)], OLLIE["mane_d"]))
    p += ollie_head(552, 332, "neutral", 0.98, "side")
    p += drape_side(574, 490, OLLIE["teal"], OLLIE["teal_d"], OLLIE["teal_l"])
    return p


def ollie_body_back():
    p = []
    p += shadow(rx=176)
    p.append(ell("tail", 512, 716, 40, 56, OLLIE["coat"], OUTLINE, 7))
    p.append(poly("tail", [(526, 760), (562, 788), (538, 786), (550, 816), (520, 790)], OLLIE["mane"], OUTLINE, 4))
    p.append(poly("legs", [(456, 752), (498, 752), (502, 900), (484, 922), (452, 918), (446, 898)], OLLIE["coat"], OUTLINE, 7))
    p.append(poly("legs", [(568, 752), (526, 752), (522, 900), (540, 922), (572, 918), (578, 898)], OLLIE["coat"], OUTLINE, 7))
    p.append(ell("legs", 452, 924, 58, 28, OLLIE["hoof"], OUTLINE, 6))
    p.append(ell("legs", 572, 924, 58, 28, OLLIE["hoof"], OUTLINE, 6))
    body = [(512, 448), (604, 490), (632, 610), (620, 760), (572, 822), (512, 844),
            (452, 822), (404, 760), (392, 610), (420, 490)]
    p.append(poly("body", body, OLLIE["coat"], OUTLINE, 8))
    p.append(poly("shade", [(562, 490), (632, 610), (620, 760), (572, 822), (546, 812), (566, 700), (566, 550)], OLLIE["coat_d"]))
    p.append(poly("arms", [(432, 500), (402, 516), (384, 618), (394, 714), (410, 748), (434, 738), (426, 638), (448, 548)], OLLIE["coat"], OUTLINE, 7))
    p.append(poly("arms", [(592, 500), (622, 516), (640, 618), (630, 714), (614, 748), (590, 738), (598, 638), (576, 548)], OLLIE["coat"], OUTLINE, 7))
    p.append(ell("arms", 422, 752, 28, 22, OLLIE["hoof"], OUTLINE, 5))
    p.append(ell("arms", 602, 752, 28, 22, OLLIE["hoof"], OUTLINE, 5))
    p += ollie_head(512, 336, "neutral", 1.0, "back")
    p += drape_back(512, 490, OLLIE["teal"], OLLIE["teal_d"], OLLIE["teal_l"])
    return p


BUILDERS = {
    ("pip", "front", "neutral"): lambda: pip_body_front("neutral"),
    ("pip", "front", "happy"): lambda: pip_body_front("happy"),
    ("pip", "front", "curious"): lambda: pip_body_front("curious"),
    ("pip", "three_quarter", "neutral"): pip_body_three_quarter,
    ("pip", "side", "neutral"): pip_body_side,
    ("pip", "back", "neutral"): pip_body_back,
    ("ollie", "front", "neutral"): lambda: ollie_body_front("neutral"),
    ("ollie", "front", "happy"): lambda: ollie_body_front("happy"),
    ("ollie", "front", "curious"): lambda: ollie_body_front("curious"),
    ("ollie", "three_quarter", "neutral"): ollie_body_three_quarter,
    ("ollie", "side", "neutral"): ollie_body_side,
    ("ollie", "back", "neutral"): ollie_body_back,
}


def sha16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def label_font(size: int, bold: bool = False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def make_sheet(entries, columns, cell, path, title):
    rows = math.ceil(len(entries) / columns)
    sheet = Image.new("RGB", (columns * cell, rows * (cell + 30) + 46), (236, 236, 236))
    d = ImageDraw.Draw(sheet)
    d.text((16, 12), title, font=label_font(24, True), fill=(30, 30, 30))
    for i, (label, img) in enumerate(entries):
        x = (i % columns) * cell
        y = 46 + (i // columns) * (cell + 30)
        img = img.convert("RGB")
        img.thumbnail((cell - 16, cell - 16))
        sheet.paste(img, (x + (cell - img.width) // 2, y + 24))
        d.text((x + 8, y + 2), label, font=label_font(16, True), fill=(50, 50, 50))
    sheet.save(path)


def silhouette_of(path: Path) -> Image.Image:
    im = Image.open(path).convert("RGB")
    bg = im.getpixel((2, 2))
    mask = Image.new("L", im.size, 0)
    px, src = mask.load(), im.load()
    for y in range(im.height):
        for x in range(im.width):
            p = src[x, y]
            if max(abs(p[i] - bg[i]) for i in range(3)) > 26:
                px[x, y] = 255
    out = Image.new("RGB", im.size, (236, 236, 236))
    out.paste(Image.new("RGB", im.size, (55, 40, 32)), (0, 0), mask)
    return out


def patch_leo_star() -> dict:
    src = Image.open(V4).convert("RGB")
    im = src.copy()
    cx, cy = 541, 445
    d = ImageDraw.Draw(im)
    # replace the flower badge with a local vertical fabric gradient (sampled shirt)
    # cover the flower badge with a clean, intentional sewn patch
    d = ImageDraw.Draw(im)
    d.ellipse((cx - 32, cy - 31, cx + 32, cy + 33), fill=(244, 230, 200), outline=(96, 66, 30), width=2)
    # stitch ring
    for a in range(0, 360, 18):
        x0 = cx + 27 * math.cos(math.radians(a))
        y0 = cy + 28 * math.sin(math.radians(a))
        x1 = cx + 29 * math.cos(math.radians(a))
        y1 = cy + 30 * math.sin(math.radians(a))
        d.line((x0, y0, x1, y1), fill=(140, 100, 50), width=1)
    # clear five-point star patch
    pts = star_pts(cx, cy + 1, 22, 9.5)
    d.polygon(pts, fill=(244, 190, 43), outline=(83, 54, 16))
    d.line(pts + [pts[0]], fill=(83, 54, 16), width=4, joint="curve")
    # stitch hint and small highlight
    inner = star_pts(cx, cy + 1, 21, 9)
    d.line(inner + [inner[0]], fill=(255, 220, 120), width=2)
    out_png = OUT / "leo_front_no_backpack_v5_star.png"
    im.save(out_png)
    # QA crops
    box = (474, 376, 610, 520)
    crop_v4 = src.crop(box).resize((408, 432), Image.LANCZOS)
    crop_v5 = im.crop(box).resize((408, 432), Image.LANCZOS)
    zoom = Image.new("RGB", (840, 500), (236, 236, 236))
    zoom.paste(crop_v4, (4, 44))
    zoom.paste(crop_v5, (428, 44))
    dz = ImageDraw.Draw(zoom)
    dz.text((8, 12), f"v4 asset 14d99ab25a13 (round badge)", font=label_font(18, True), fill=(30, 30, 30))
    dz.text((432, 12), "v5 star-patch correction (new file)", font=label_font(18, True), fill=(30, 30, 30))
    zoom.save(OUT / "leo_star_patch_comparison.png")
    im.crop((cx - 70, cy - 70, cx + 70, cy + 70)).resize((420, 420), Image.LANCZOS).save(OUT / "leo_star_patch_zoom.png")
    return {"source": V4.name, "output": out_png.name, "center": [cx, cy]}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": "character_lock_pack_v3",
        "status": "draft; not registered; not approved; not canonical",
        "canvas": [v1.W, v1.H],
        "note": "Deterministic vector art from editable primitives. No model generation.",
        "characters": {},
        "comparisons": {},
        "leo": {},
    }
    pngs: dict[tuple[str, str, str], Path] = {}
    for (char, view, expr), builder in BUILDERS.items():
        prims = builder()
        pivot = HEAD_PIVOT[(char, view)]
        head_scale = 0.86 if view == "side" else 0.92
        prims = scale_groups(prims, HEAD_GROUPS, pivot[0], pivot[1], head_scale, dy=6)
        stem = f"{char}_v3_{view}_{expr}"
        svg, png = OUT / f"{stem}.svg", OUT / f"{stem}.png"
        v1.render_svg(prims, svg)
        v1.render_png(prims, png)
        pngs[(char, view, expr)] = png
        manifest["characters"].setdefault(char, {"views": {}, "expressions": {}})["views"].setdefault(view, {})[expr] = {
            "svg": svg.name, "png": png.name, "shapes": len(prims),
            "svg_sha256_16": sha16(svg), "png_sha256_16": sha16(png),
        }
        if expr != "neutral":
            manifest["characters"][char]["expressions"][expr] = png.name
    # neutral silhouettes for all four views
    for char in ("pip", "ollie"):
        for view in ("front", "three_quarter", "side", "back"):
            png = pngs[(char, view, "neutral")]
            sil = OUT / f"{char}_v3_{view}_neutral_silhouette.png"
            silhouette_of(png).save(sil)
            manifest["characters"][char]["views"][view]["neutral"]["silhouette_png"] = sil.name

    # contact sheets
    for char in ("pip", "ollie"):
        views = [(v.replace("_", " ").title(), Image.open(pngs[(char, v, "neutral")]))
                 for v in ("front", "three_quarter", "side", "back")]
        path = OUT / f"{char}_v3_view_sheet.png"
        make_sheet(views, 4, 330, path, f"{char.title()} V3 - four distinct views (neutral)")
        manifest["comparisons"][f"{char}_views"] = path.name
        exprs = [(e.title(), Image.open(pngs[(char, "front", e)])) for e in ("neutral", "happy", "curious")]
        path = OUT / f"{char}_v3_expression_sheet.png"
        make_sheet(exprs, 3, 330, path, f"{char.title()} V3 - neutral / happy / curious")
        manifest["comparisons"][f"{char}_expressions"] = path.name

    # fetch canonical rasters through local API (read-only)
    import httpx
    canonical = {}
    with httpx.Client(timeout=60) as client:
        for name, aid in CANONICAL.items():
            r = client.get(f"http://127.0.0.1:8010/api/assets/{aid}/file")
            r.raise_for_status()
            from io import BytesIO
            canonical[name] = Image.open(BytesIO(r.content)).convert("RGB")

    leo = patch_leo_star()
    manifest["leo"] = {
        **leo,
        "source_asset_id": "14d99ab25a13",
        "profile_character_id": "7077c0fc963f",
        "note": "v4 preserved; backpack absent; star patch redrawn as clear five-point star; framing/wardrobe unchanged",
        "sha256": hashlib.sha256((OUT / leo["output"]).read_bytes()).hexdigest(),
    }

    lineup = [(f"{n} - canonical draft {CANONICAL[n]}", im) for n, im in canonical.items()]
    lineup += [("Pip - V3 vector", Image.open(pngs[("pip", "front", "neutral")])),
               ("Ollie - V3 vector", Image.open(pngs[("ollie", "front", "neutral")])),
               ("Leo - V5 no-backpack star", Image.open(OUT / leo["output"]))]
    path = OUT / "lineup_v3.png"
    make_sheet(lineup, 4, 300, path, "CHARACTER LOCK V3 - canonical drafts + V3 vector + Leo V5")
    manifest["comparisons"]["lineup"] = path.name

    sil_entries = []
    for n, im in canonical.items():
        sil_entries.append((f"{n} - canonical silhouette", silhouette_of_bytes(im)))
    for char in ("pip", "ollie"):
        for view in ("front", "three_quarter", "side", "back"):
            sil_entries.append((f"{char.title()} {view.replace('_', ' ')} - V3 silhouette",
                                Image.open(OUT / f"{char}_v3_{view}_neutral_silhouette.png")))
    path = OUT / "silhouette_compare_v3.png"
    make_sheet(sil_entries, 4, 300, path, "CHARACTER LOCK V3 - silhouette comparison")
    manifest["comparisons"]["silhouette"] = path.name

    (OUT / "manifest_v3.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "characters"}, indent=2))
    print("characters:", {c: len(v["views"]) for c, v in manifest["characters"].items()})


def silhouette_of_bytes(im: Image.Image) -> Image.Image:
    rgb = im.convert("RGB")
    bg = rgb.getpixel((2, 2))
    mask = Image.new("L", rgb.size, 0)
    px, src = mask.load(), rgb.load()
    for y in range(rgb.height):
        for x in range(rgb.width):
            p = src[x, y]
            if max(abs(p[i] - bg[i]) for i in range(3)) > 26:
                px[x, y] = 255
    out = Image.new("RGB", rgb.size, (236, 236, 236))
    out.paste(Image.new("RGB", rgb.size, (55, 40, 32)), (0, 0), mask)
    return out


if __name__ == "__main__":
    main()
