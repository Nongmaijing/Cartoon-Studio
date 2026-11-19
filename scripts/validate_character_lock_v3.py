"""Validate the CHARACTER LOCK PACK V3 manifests and artefacts (read-only)."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "operations" / "character_lock_v3"
DB = ROOT / "data" / "cartoon_studio.db"
V4 = ROOT / "outputs" / "16556b67d331" / "e0012667d951" / "e0012667d951_00001_.png"
V4_SHA = "22cef6777a87b1586c17d95951914f51e60468b2dc63027b0621feaf91bfb4c8"
SVG_NS = "{http://www.w3.org/2000/svg}"
REQUIRED = {"head", "ears", "body", "arms", "legs", "neckerchief", "shade_head"}
VIEWS = ("front", "three_quarter", "side", "back")
EXPRS = ("neutral", "happy", "curious")


def sha16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def diff_ratio(a: Image.Image, b: Image.Image, threshold: int = 8) -> float:
    a, b = a.convert("RGB"), b.convert("RGB")
    if a.size != b.size:
        return 1.0
    diff = ImageChops.difference(a, b).convert("L")
    mask = diff.point(lambda v: 255 if v > threshold else 0)
    hist = mask.histogram()
    return hist[255] / (a.width * a.height)


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    manifest = json.loads((OUT / "manifest_v3.json").read_text(encoding="utf-8"))
    pngs: dict[tuple[str, str, str], Image.Image] = {}

    for char in ("pip", "ollie"):
        views = manifest["characters"].get(char, {}).get("views") or {}
        if set(views) != set(VIEWS):
            errors.append(f"{char}: views {sorted(views)} != {sorted(VIEWS)}")
        for view in VIEWS:
            entries = views.get(view) or {}
            if view == "front" and set(entries) != set(EXPRS):
                errors.append(f"{char} front: expressions {sorted(entries)}")
            if view != "front" and set(entries) != {"neutral"}:
                errors.append(f"{char} {view}: expected only neutral")
            for expr, entry in entries.items():
                svg, png = OUT / entry["svg"], OUT / entry["png"]
                if not svg.exists() or not png.exists():
                    errors.append(f"{char} {view} {expr}: missing svg/png")
                    continue
                if sha16(svg) != entry["svg_sha256_16"]:
                    errors.append(f"{char} {view} {expr}: svg hash mismatch")
                if sha16(png) != entry["png_sha256_16"]:
                    errors.append(f"{char} {view} {expr}: png hash mismatch")
                try:
                    tree = ET.parse(svg)
                except ET.ParseError as exc:
                    errors.append(f"{char} {view} {expr}: invalid svg: {exc}")
                    continue
                groups = {e.get("id") for e in tree.iter(f"{SVG_NS}g")}
                missing = REQUIRED - groups
                if missing:
                    errors.append(f"{char} {view} {expr}: missing groups {sorted(missing)}")
                if view != "back" and "face" not in groups:
                    errors.append(f"{char} {view} {expr}: missing face group")
                if view == "back" and "face" in groups:
                    warnings.append(f"{char} back {expr}: face group present")
                with Image.open(png) as im:
                    if im.size != (1024, 1024):
                        errors.append(f"{char} {view} {expr}: size {im.size}")
                    im = im.convert("RGB")
                    pngs[(char, view, expr)] = im.copy()
                    bg = im.getpixel((2, 2))
                    px = im.load()
                    non_bg = sum(1 for y in range(0, 1024, 4) for x in range(0, 1024, 4)
                                 if max(abs(px[x, y][i] - bg[i]) for i in range(3)) > 8)
                    ratio = non_bg / (256 * 256)
                    if not 0.05 <= ratio <= 0.75:
                        errors.append(f"{char} {view} {expr}: coverage {ratio:.1%}")
        # silhouettes
        for view in VIEWS:
            entry = views[view]["neutral"]
            sil = OUT / entry.get("silhouette_png", "")
            if not sil.exists():
                errors.append(f"{char} {view}: missing silhouette")

    # distinct views / expressions
    for char in ("pip", "ollie"):
        for a, b in (("front", "three_quarter"), ("front", "side"), ("front", "back"),
                     ("three_quarter", "side"), ("side", "back")):
            r = diff_ratio(pngs[(char, a, "neutral")], pngs[(char, b, "neutral")])
            if r < 0.02:
                errors.append(f"{char}: {a}/{b} too similar ({r:.2%})")
        for expr in ("happy", "curious"):
            r = diff_ratio(pngs[(char, "front", "neutral")], pngs[(char, "front", expr)])
            if r < 0.001:
                errors.append(f"{char}: {expr} too similar to neutral ({r:.3%})")
        hashes = {sha16(OUT / manifest["characters"][char]["views"][v]["neutral"]["png"]) for v in VIEWS}
        if len(hashes) != len(VIEWS):
            errors.append(f"{char}: duplicate neutral view files")

    # comparisons
    for key, name in manifest["comparisons"].items():
        if not (OUT / name).exists():
            errors.append(f"missing comparison {key}: {name}")

    # Leo v5
    leo = manifest.get("leo") or {}
    v5 = OUT / leo.get("output", "")
    if not v5.exists():
        errors.append("Leo v5 missing")
    else:
        with Image.open(v5) as im:
            if im.size != (1024, 1024):
                errors.append(f"Leo v5 size {im.size}")
            v5i = im.convert("RGB")
        v4i = Image.open(V4).convert("RGB")
        if sha256(V4) != V4_SHA:
            errors.append("Leo v4 source changed")
        box = (474, 376, 610, 520)
        inside = diff_ratio(v4i.crop(box), v5i.crop(box))
        outside_a = v4i.copy(); outside_b = v5i.copy()
        outside_a.paste((0, 0, 0), box); outside_b.paste((0, 0, 0), box)
        outside = diff_ratio(outside_a, outside_b)
        if inside < 0.02:
            errors.append(f"Leo v5 patch not changed ({inside:.2%})")
        if outside > 0.0005:
            errors.append(f"Leo v5 changed pixels outside patch ({outside:.3%})")
        # clear star pixels near centre
        px = v5i.load()
        gold = sum(1 for y in range(410, 485) for x in range(505, 580)
                   if px[x, y][0] > 200 and px[x, y][1] > 140 and px[x, y][2] < 120)
        if gold < 80:
            errors.append(f"Leo star pixels too few ({gold})")

    # DB state: read-only
    con = sqlite3.connect("file:" + str(DB) + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = {r["name"]: dict(r) for r in con.execute(
        "SELECT name,approval_status,canonical_asset_id FROM characters WHERE project_id='16556b67d331'")}
    for name in ("Leo", "Mira", "Toby", "Bruno", "Pip", "Ollie"):
        if name not in rows:
            errors.append(f"DB missing character {name}")
        elif rows[name]["approval_status"] != "draft":
            errors.append(f"DB {name} is not draft")
    for name in ("Pip", "Ollie"):
        if rows.get(name, {}).get("canonical_asset_id"):
            errors.append(f"DB {name} has a canonical asset; pack must not promote")
    registered = [r["filename"] for r in con.execute("SELECT filename FROM assets")]
    leaked = [n for n in registered if n.startswith(("pip_v3_", "ollie_v3_", "leo_front_no_backpack_v5"))]
    if leaked:
        errors.append(f"pack files registered as assets: {leaked}")
    con.close()

    print(json.dumps({
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "characters": {c: {"views": len(manifest["characters"][c]["views"]),
                           "files": sum(len(v) for v in manifest["characters"][c]["views"].values())}
                       for c in ("pip", "ollie")},
        "leo": {"output": leo.get("output"), "sha256": leo.get("sha256")},
        "db": {n: {"status": rows[n]["approval_status"], "canonical": rows[n]["canonical_asset_id"]}
               for n in rows if n in ("Leo", "Pip", "Ollie")},
    }, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
