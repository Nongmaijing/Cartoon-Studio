"""Build the S01E01 pilot-proof storyboard animatic from existing assets.

Read-only with respect to source assets and the production database. Creates a
new versioned folder under outputs/<project>/pilot_only/animatic_vN and never
overwrites an existing MP4.

No model generation, no audio, no DB writes.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "cartoon_studio.db"
SCRIPT = ROOT / "docs" / "operations" / "S01E01_SCRIPT_V3.json"
PROJECT_ID = "16556b67d331"
LABEL = "PILOT PROOF — NOT FINAL"
W, H, FPS = 1280, 720, 24
FONT_DIR = Path(r"C:\Windows\Fonts")
FONT_BOLD = FONT_DIR / "segoeuib.ttf"
FONT_SEMI = FONT_DIR / "segoeuib.ttf"
FONT_REG = FONT_DIR / "segoeui.ttf"

CHARACTERS = {
    "Leo": "7077c0fc963f",
    "Mira": "701e992712f0",
    "Toby": "1bdcc7d86d5f",
    "Bruno": "8db8c4fae68d",
}
OFFSCREEN = {"Pip", "Ollie"}
PLACEHOLDERS = {
    "Pip": ROOT / "docs" / "operations" / "vector_drafts" / "pip_v2.png",
    "Ollie": ROOT / "docs" / "operations" / "vector_drafts" / "ollie_v2.png",
}
BACKGROUND_NAMES = {"The Old Oak Gathering": "Old Oak Clearing v2", "default": "Garden Patch v2"}


def connect() -> sqlite3.Connection:
    con = sqlite3.connect("file:" + str(DB) + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def resolve_sources(con: sqlite3.Connection) -> tuple[dict[str, Path], dict[str, tuple[str, Path]]]:
    chars: dict[str, Path] = {}
    for name, cid in CHARACTERS.items():
        row = con.execute(
            "SELECT a.rel_path FROM characters c JOIN assets a ON a.id=c.canonical_asset_id WHERE c.id=?",
            (cid,),
        ).fetchone()
        if not row:
            raise SystemExit(f"Missing canonical front for {name}")
        chars[name] = ROOT / "outputs" / row["rel_path"]

    backgrounds: dict[str, tuple[str, Path]] = {}
    for name in set(BACKGROUND_NAMES.values()):
        row = con.execute(
            """SELECT b.id, a.id AS asset_id, a.rel_path
               FROM backgrounds b
               JOIN media_links m ON m.owner_type='background' AND m.owner_id=b.id AND m.role='background'
               JOIN assets a ON a.id=m.asset_id
               WHERE b.project_id=? AND b.name=? ORDER BY m.created_at LIMIT 1""",
            (PROJECT_ID, name),
        ).fetchone()
        if not row:
            raise SystemExit(f"Missing background asset for {name}")
        backgrounds[name] = (row["asset_id"], ROOT / "outputs" / row["rel_path"])
    return chars, backgrounds


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def cover(im: Image.Image, zoom: float = 1.0, ox: float = 0.0, oy: float = 0.0) -> Image.Image:
    im = im.convert("RGB")
    scale = max(W / im.width, H / im.height) * zoom
    nw, nh = int(im.width * scale + 0.5), int(im.height * scale + 0.5)
    im = im.resize((nw, nh), Image.LANCZOS)
    left = max(0, min(nw - W, int((nw - W) / 2 + ox)))
    top = max(0, min(nh - H, int((nh - H) / 2 + oy)))
    return im.crop((left, top, left + W, top + H))


def wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=f) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def badge(draw: ImageDraw.ImageDraw, xy: tuple[int, int] | None = None) -> None:
    text = LABEL
    f = font(FONT_BOLD, 22)
    pad = 10
    tw = draw.textlength(text, font=f)
    x = W - tw - pad * 2 - 24 if xy is None else xy[0]
    y = 12 if xy is None else xy[1]
    draw.rounded_rectangle((x, y, x + tw + pad * 2, y + 38), radius=8, fill=(190, 24, 24))
    draw.text((x + pad, y + 7), text, font=f, fill=(255, 245, 235))


def character_card(frame: Image.Image, path: Path, name: str, placeholder: bool = False) -> None:
    card_w, card_h = 250, 300
    top = 190
    im = Image.open(path).convert("RGB")
    im = ImageOps.fit(im, (card_w, card_h), method=Image.LANCZOS, centering=(0.5, 0.45))
    mask = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card_w, card_h), radius=22, fill=255)
    border = Image.new("RGB", (card_w + 8, card_h + 8), (245, 238, 220))
    bmask = Image.new("L", border.size, 0)
    ImageDraw.Draw(bmask).rounded_rectangle((0, 0, border.width, border.height), radius=26, fill=255)
    x = W - card_w - 58
    frame.paste(border, (x - 4, top - 4), bmask)
    frame.paste(im, (x, top), mask)
    d = ImageDraw.Draw(frame)
    label = f"{name} · PLACEHOLDER" if placeholder else name
    d.rounded_rectangle((x, top + card_h - 44, x + card_w, top + card_h), radius=10, fill=(16, 18, 22))
    f = font(FONT_BOLD, 20)
    tw = d.textlength(label, font=f)
    d.text((x + (card_w - tw) / 2, top + card_h - 36), label, font=f,
           fill=(255, 176, 64) if placeholder else (255, 245, 230))
    if placeholder:
        d.text((x, top - 28), "pilot-only vector draft · off-screen", font=font(FONT_REG, 15),
               fill=(255, 205, 170))


def caption(frame: Image.Image, speaker: str, text: str, note: str) -> None:
    d = ImageDraw.Draw(frame)
    top = H - 170
    d.rectangle((0, top, W, H), fill=(10, 12, 16))
    d.line((0, top, W, top), fill=(210, 180, 120), width=2)
    sf = font(FONT_BOLD, 30)
    label = speaker.upper()
    color = (255, 196, 92)
    if speaker in OFFSCREEN:
        label += "  ·  OFF-SCREEN"
        color = (255, 160, 140)
    d.text((48, top + 16), label, font=sf, fill=color)
    tf = font(FONT_REG, 31)
    lines = wrap(d, text, tf, W - 96)
    if len(lines) > 3:
        tf = font(FONT_REG, 28)
        lines = wrap(d, text, tf, W - 96)
    y = top + 58
    for line in lines[:3]:
        d.text((48, y), line, font=tf, fill=(246, 246, 244))
        y += int(tf.size * 1.25)
    d.text((48, H - 26), note, font=font(FONT_REG, 16), fill=(150, 150, 150))


def top_bar(frame: Image.Image, left: str) -> None:
    d = ImageDraw.Draw(frame)
    d.rectangle((0, 0, W, 62), fill=(10, 12, 16))
    d.text((42, 14), left, font=font(FONT_BOLD, 24), fill=(238, 230, 214))
    badge(d)


def add_gradient(im: Image.Image, y_from: int, y_to: int, max_alpha: int = 205) -> Image.Image:
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    span = max(1, y_to - y_from)
    for i in range(span):
        a = int(max_alpha * (i / span))
        d.line((0, y_from + i, W, y_from + i), fill=(0, 0, 0, a))
    return Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")


def slide_title(bg: Path, subtitle: str, note: str) -> Image.Image:
    im = ImageEnhance.Brightness(cover(Image.open(bg))).enhance(0.55)
    im = im.filter(ImageFilter.GaussianBlur(2))
    d = ImageDraw.Draw(im)
    top_bar(im, "S01E01 · The Little Seed")
    d.text((90, 250), "S01E01", font=font(FONT_BOLD, 34), fill=(255, 196, 92))
    d.text((90, 300), "The Little Seed", font=font(FONT_BOLD, 76), fill=(255, 250, 240))
    d.text((90, 400), subtitle, font=font(FONT_REG, 30), fill=(230, 226, 214))
    d.text((90, 470), note, font=font(FONT_REG, 22), fill=(200, 196, 186))
    d.text((90, 640), "Storyboard animatic · existing assets only · no audio", font=font(FONT_REG, 18),
           fill=(170, 168, 160))
    return im


def slide_scene(bg: Path, number: int, title: str, location: str) -> Image.Image:
    im = ImageEnhance.Brightness(cover(Image.open(bg))).enhance(0.5)
    im = im.filter(ImageFilter.GaussianBlur(1))
    d = ImageDraw.Draw(im)
    top_bar(im, "S01E01 · The Little Seed")
    d.text((90, 270), f"SCENE {number} OF 4", font=font(FONT_BOLD, 28), fill=(255, 196, 92))
    d.text((90, 315), title, font=font(FONT_BOLD, 64), fill=(255, 250, 240))
    d.text((90, 400), location, font=font(FONT_REG, 28), fill=(220, 216, 204))
    d.text((90, 640), "Animatic panel · dialogue timing proof", font=font(FONT_REG, 18),
           fill=(170, 168, 160))
    return im


def slide_cast(bg: Path, chars: dict[str, Path], placeholders: dict[str, Path]) -> Image.Image:
    im = ImageEnhance.Brightness(cover(Image.open(bg))).enhance(0.48)
    im = im.filter(ImageFilter.GaussianBlur(2))
    d = ImageDraw.Draw(im)
    top_bar(im, "S01E01 · The Little Seed")
    d.text((85, 96), "Cast · existing canonical drafts (not approved)", font=font(FONT_BOLD, 36),
           fill=(255, 248, 236))
    d.text((85, 146), "Pip and Ollie: off-screen voices / labelled pilot-only placeholders",
           font=font(FONT_REG, 21), fill=(220, 214, 200))
    names = ["Leo", "Mira", "Toby", "Bruno", "Pip", "Ollie"]
    card_w, card_h, gap = 170, 200, 18
    start = (W - (len(names) * card_w + (len(names) - 1) * gap)) // 2
    top = 250
    for i, name in enumerate(names):
        path = chars.get(name) or placeholders[name]
        placeholder = name in placeholders
        im2 = Image.open(path).convert("RGB")
        im2 = ImageOps.fit(im2, (card_w, card_h), method=Image.LANCZOS, centering=(0.5, 0.45))
        mask = Image.new("L", (card_w, card_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, card_w, card_h), radius=14, fill=255)
        x = start + i * (card_w + gap)
        border = Image.new("RGB", (card_w + 6, card_h + 6), (245, 238, 220))
        bmask = Image.new("L", border.size, 0)
        ImageDraw.Draw(bmask).rounded_rectangle((0, 0, border.width, border.height), radius=17, fill=255)
        im.paste(border, (x - 3, top - 3), bmask)
        im.paste(im2, (x, top), mask)
        nf = font(FONT_BOLD, 20)
        tw = d.textlength(name, font=nf)
        d.text((x + (card_w - tw) / 2, top + card_h + 10), name, font=nf, fill=(255, 245, 230))
        if placeholder:
            note = "PLACEHOLDER · OFF-SCREEN"
            nf2 = font(FONT_BOLD, 12)
            tw2 = d.textlength(note, font=nf2)
            d.text((x + (card_w - tw2) / 2, top + card_h + 36), note, font=nf2, fill=(255, 150, 130))
    d.text((85, 640), "Animatic · existing assets only · no audio · no new keyframes",
           font=font(FONT_REG, 18), fill=(175, 172, 164))
    return im


def slide_line(bg: Path, scene_title: str, speaker: str, text: str, idx: int,
               char_path: Path | None) -> Image.Image:
    zoom = 1.02 + (idx % 3) * 0.03
    im = cover(Image.open(bg), zoom=zoom, ox=((idx % 5) - 2) * 12, oy=((idx % 4) - 1.5) * 8)
    im = ImageEnhance.Brightness(im).enhance(0.82)
    im = add_gradient(im, H - 300, H - 170, 185)
    d = ImageDraw.Draw(im)
    top_bar(im, f"S01E01 · {scene_title}")
    if char_path:
        character_card(im, char_path, speaker, placeholder=speaker in OFFSCREEN)
    caption(im, speaker, text, "PILOT PROOF — NOT FINAL · animatic · no audio · condensed timing")
    return im


def slide_outro(bg: Path, duration_note: str) -> Image.Image:
    im = ImageEnhance.Brightness(cover(Image.open(bg))).enhance(0.45)
    im = im.filter(ImageFilter.GaussianBlur(3))
    d = ImageDraw.Draw(im)
    top_bar(im, "S01E01 · The Little Seed")
    d.text((90, 250), "END OF PILOT PROOF", font=font(FONT_BOLD, 64), fill=(255, 250, 240))
    d.text((90, 340), "Storyboard animatic · no audio · no final keyframes", font=font(FONT_REG, 28),
           fill=(230, 226, 214))
    d.text((90, 390), duration_note, font=font(FONT_REG, 24), fill=(210, 206, 196))
    d.text((90, 470), "Not for broadcast · not an approved episode", font=font(FONT_BOLD, 30),
           fill=(255, 170, 120))
    return im


def main() -> int:
    if not SCRIPT.exists():
        raise SystemExit(f"Missing script: {SCRIPT}")
    script_bytes = SCRIPT.read_bytes()
    digest = hashlib.sha256(script_bytes).hexdigest()
    data = json.loads(script_bytes.decode("utf-8"))
    story = data["story"]
    scenes = story["scenes"]

    con = connect()
    chars, backgrounds = resolve_sources(con)
    con.close()

    out_root = ROOT / "outputs" / PROJECT_ID / "pilot_only"
    version = 1
    while (out_root / f"animatic_v{version}").exists():
        version += 1
    out_dir = out_root / f"animatic_v{version}"
    slides_dir = out_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=False)

    slides: list[tuple[Path, float]] = []
    captions: list[tuple[float, float, str, str]] = []
    elapsed = 0.0

    def add(img: Image.Image, seconds: float, speaker: str = "", text: str = "") -> None:
        nonlocal elapsed
        path = slides_dir / f"slide_{len(slides):04d}.png"
        img.save(path, "PNG")
        slides.append((path, round(seconds, 3)))
        if speaker:
            captions.append((elapsed, elapsed + seconds, speaker, text))
        elapsed += seconds

    old_oak = backgrounds[BACKGROUND_NAMES["The Old Oak Gathering"]][1]
    garden = backgrounds[BACKGROUND_NAMES["default"]][1]

    add(slide_title(old_oak, "Storyboard animatic · pilot proof",
                    "Four scenes · existing character fronts and backgrounds · V3 dialogue"), 8.0)
    add(slide_cast(old_oak, chars, PLACEHOLDERS), 7.0)

    for number, scene in enumerate(scenes, 1):
        bg = old_oak if scene["title"] == "The Old Oak Gathering" else garden
        add(slide_scene(bg, number, scene["title"], scene["background"]), 3.0)
        for idx, line in enumerate(scene.get("dialogue") or []):
            speaker = str(line.get("speaker") or "Narrator")
            text = str(line.get("text") or "").strip()
            if not text:
                continue
            words = len(text.split())
            seconds = max(1.7, min(5.0, 0.33 * words))
            char_path = chars.get(speaker) or PLACEHOLDERS.get(speaker)
            add(slide_line(bg, scene["title"], speaker, text, idx, char_path), seconds, speaker, text)

    add(slide_outro(old_oak, f"Runtime ≈ {elapsed + 7:.0f}s · S01E01 V3 dialogue (condensed timing)"), 7.0)

    total = sum(d for _, d in slides)
    if not 180 <= total <= 240:
        raise SystemExit(f"Duration {total:.1f}s outside the approved 3–4 minute window")

    concat = slides_dir / "slides.txt"
    lines = []
    for path, seconds in slides:
        lines.append(f"file '{path.as_posix()}'")
        lines.append(f"duration {seconds:.3f}")
    lines.append(f"file '{slides[-1][0].as_posix()}'")
    concat.write_text("\n".join(lines) + "\n", encoding="utf-8")

    mp4 = out_dir / "S01E01_PILOT_PROOF_animatic.mp4"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat),
        "-vf", f"fps={FPS},format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-movflags", "+faststart", "-an",
        "-t", f"{total:.3f}", str(mp4),
    ]
    print("Encoding", mp4.name, f"({total:.1f}s, {len(slides)} panels)")
    subprocess.run(cmd, check=True)

    # sidecar SRT for review tools (silent programme)
    def ts(sec: float) -> str:
        ms = int(round(sec * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    srt_lines = []
    for i, (start, end, speaker, text) in enumerate(captions, 1):
        srt_lines += [str(i), f"{ts(start)} --> {ts(end)}", f"{speaker}: {text}", ""]
    (out_dir / "S01E01_PILOT_PROOF_captions.srt").write_text("\n".join(srt_lines), encoding="utf-8")

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=index,codec_type,codec_name,width,height",
         "-of", "json", str(mp4)], capture_output=True, text=True, check=True,
    )
    info = json.loads(probe.stdout)

    manifest = {
        "label": LABEL,
        "output": str(mp4),
        "duration_seconds": round(total, 3),
        "resolution": f"{W}x{H}",
        "fps": FPS,
        "audio": "none",
        "script": {"path": str(SCRIPT), "revision": data.get("revision"), "sha256": digest},
        "sources": {
            "characters": {name: str(path) for name, path in chars.items()},
            "placeholders": {name: str(path) for name, path in PLACEHOLDERS.items()},
            "backgrounds": {name: {"asset_id": aid, "file": str(path)} for name, (aid, path) in backgrounds.items()},
        },
        "panels": [{"file": str(p), "duration": d} for p, d in slides],
        "probe": info,
        "notes": [
            "Existing assets only; no model generation, no audio, no database writes.",
            "Dialogue timing is condensed to fit the approved 3-4 minute proof.",
            "Pip/Ollie appear only as off-screen voices and labelled pilot-only vector placeholders.",
            "Leo canonical front predates the backpack removal and is used unchanged as the approved existing asset.",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(mp4), "duration": round(total, 3), "probe": info}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
