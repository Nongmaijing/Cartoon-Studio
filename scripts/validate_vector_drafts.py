"""Validate vector draft files, SVG groups, previews and registration state."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.db import query  # noqa: E402

SVG_NS = "{http://www.w3.org/2000/svg}"
REQUIRED_GROUPS = {"head", "ears", "body", "arms", "legs", "neckerchief", "face"}


def sha16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=r"D:\bro\CartoonStudio\docs\operations\vector_drafts")
    parser.add_argument("--manifest", default="manifest.json")
    parser.add_argument("--project-id", default="16556b67d331")
    args = parser.parse_args()
    root = Path(args.dir)
    manifest_path = root / args.manifest
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []

    for name, entry in manifest["characters"].items():
        for key in ("svg", "png", "silhouette_svg", "silhouette_png"):
            path = root / entry[key]
            if not path.exists():
                errors.append(f"{name}: missing {key} {path.name}")
        svg_path = root / entry["svg"]
        png_path = root / entry["png"]
        sil_png = root / entry["silhouette_png"]
        if not svg_path.exists() or not png_path.exists() or not sil_png.exists():
            continue

        try:
            tree = ET.parse(svg_path)
        except ET.ParseError as exc:
            errors.append(f"{name}: invalid SVG: {exc}")
            continue
        groups = {elem.get("id") for elem in tree.iter(f"{SVG_NS}g")}
        missing = REQUIRED_GROUPS - groups
        if missing:
            errors.append(f"{name}: missing SVG groups {sorted(missing)}")

        with Image.open(png_path) as image:
            if image.size != (1024, 1024):
                errors.append(f"{name}: PNG size {image.size}, expected 1024x1024")
            rgb = image.convert("RGB")
            pixels = list(rgb.get_flattened_data()) if hasattr(rgb, "get_flattened_data") else list(rgb.getdata())
            bg = (228, 228, 228)
            non_bg = sum(1 for px in pixels if max(abs(px[i] - bg[i]) for i in range(3)) > 4)
            ratio = non_bg / len(pixels)
            if ratio < 0.05:
                errors.append(f"{name}: preview looks empty ({ratio:.1%} non-background)")
            if ratio > 0.75:
                warnings.append(f"{name}: preview covers {ratio:.1%} of canvas")

        with Image.open(sil_png) as image:
            rgb = image.convert("RGB")
            pixels = list(rgb.get_flattened_data()) if hasattr(rgb, "get_flattened_data") else list(rgb.getdata())
            dark = sum(1 for px in pixels if sum(px) / 3 < 100)
            if dark / (rgb.width * rgb.height) < 0.05:
                errors.append(f"{name}: silhouette looks empty")

        if sha16(svg_path) != entry.get("svg_sha256_16"):
            errors.append(f"{name}: SVG hash mismatch")
        if sha16(png_path) != entry.get("png_sha256_16"):
            errors.append(f"{name}: PNG hash mismatch")

    if manifest.get("comparison"):
        for key, filename in manifest["comparison"].items():
            path = root / filename
            if not path.exists():
                errors.append(f"missing comparison {key}: {filename}")
            else:
                with Image.open(path) as image:
                    if image.width < 600 or image.height < 400:
                        warnings.append(f"comparison {key} is small: {image.size}")

    filenames = [
        entry[key]
        for entry in manifest.get("characters", {}).values()
        for key in ("svg", "png", "silhouette_svg", "silhouette_png")
        if entry.get(key)
    ]
    placeholders = ",".join("?" for _ in filenames)
    registered = []
    if filenames:
        registered = query(
            f"SELECT id, filename, rel_path FROM assets WHERE filename IN ({placeholders}) "
            "OR rel_path LIKE '%vector_drafts%'",
            filenames,
        )
    if registered:
        errors.append(f"Vector drafts are unexpectedly registered: {registered}")

    report = {
        "manifest": str(manifest_path),
        "version": manifest.get("version"),
        "registered_assets": registered,
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }
    print(json.dumps(report, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
