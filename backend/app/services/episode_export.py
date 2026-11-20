from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from ..config import load_config
from ..db import execute, now, query, query_one
from ..logging_setup import logger
from ..schemas import EpisodeTimeline
from .assets import asset_file, store_asset_from_path
from .episodes import parse_timeline, total_duration_ms, validate_timeline

_export_lock = asyncio.Lock()
_cancel_requested: set[str] = set()
_tasks: dict[str, asyncio.Task] = {}


class ExportCancelled(RuntimeError):
    pass


def _ffmpeg(config: dict[str, Any]) -> str:
    configured = str((config.get("ffmpeg") or {}).get("path") or "").strip()
    if configured and Path(configured).exists():
        return configured
    found = shutil.which("ffmpeg")
    if not found:
        raise RuntimeError("FFmpeg was not found. Set its path in Settings.")
    return found


def _creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def _set_progress(episode_id: str, progress: float) -> None:
    execute(
        "UPDATE episodes SET progress = ? WHERE id = ?",
        (max(0.0, min(100.0, round(float(progress), 1))), episode_id),
    )


def _append_log(episode_id: str, message: str) -> None:
    row = query_one("SELECT log FROM episodes WHERE id = ?", (episode_id,))
    existing = (row.get("log") if row else "") or ""
    combined = (existing + ("\n" if existing else "") + message)[-12000:]
    execute("UPDATE episodes SET log = ? WHERE id = ?", (combined, episode_id))
    logger.info("Episode %s: %s", episode_id, message)


def _tail(path: Path, limit: int = 4000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[-limit:]


def _unique_path(directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    counter = 2
    while (directory / f"{stem}_{counter}{suffix}").exists():
        counter += 1
    return directory / f"{stem}_{counter}{suffix}"


def _srt_time(ms: int) -> str:
    ms = max(0, int(ms))
    hours, rem = divmod(ms, 3600000)
    minutes, rem = divmod(rem, 60000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _estimate_line_ms(text: str) -> int:
    words = max(1, len(text.split()))
    return max(1200, min(8000, words * 360))


def meta_cues(meta: dict[str, Any], start_ms: int, total_ms: int) -> list[tuple[int, int, str]]:
    """Expand an audio asset's transcript into subtitle cues.

    Imported narration carries ``meta.cues`` with sentence-level timings; TTS
    lines only carry one text/duration pair.
    """
    cues = meta.get("cues")
    if isinstance(cues, list) and cues:
        entries: list[tuple[int, int, str]] = []
        for cue in cues:
            if not isinstance(cue, dict):
                continue
            text = str(cue.get("text") or "").strip().replace("\r", " ").replace("\n", " ")
            if not text:
                continue
            cue_start = start_ms + max(0, int(cue.get("start_ms") or 0))
            cue_end = start_ms + max(0, int(cue.get("end_ms") or 0))
            if cue_end <= cue_start:
                continue
            cue_end = min(total_ms, cue_end)
            if cue_end > cue_start:
                entries.append((cue_start, cue_end, text))
        if entries:
            return entries

    text = str(meta.get("text") or "").strip().replace("\r", " ").replace("\n", " ")
    if not text:
        return []
    duration_ms = int(meta.get("duration_ms") or 0) or _estimate_line_ms(text)
    end = min(total_ms, start_ms + duration_ms)
    return [(start_ms, end, text)] if end > start_ms else []


def build_srt(timeline: dict[str, Any], total_ms: int) -> str:
    """Build subtitles from the timeline's dialogue audio, falling back to scene script lines."""
    entries: list[tuple[int, int, str]] = []
    dialogue_items = [
        item for item in (timeline.get("audio") or []) if str(item.get("kind") or "") == "dialogue"
    ]
    if dialogue_items:
        for item in sorted(dialogue_items, key=lambda value: int(value.get("start_ms") or 0)):
            asset = query_one("SELECT meta_json FROM assets WHERE id = ?", (item.get("asset_id"),))
            try:
                meta = json.loads((asset or {}).get("meta_json") or "{}")
            except json.JSONDecodeError:
                meta = {}
            start = max(0, int(item.get("start_ms") or 0))
            for start, end, text in meta_cues(meta, start, total_ms):
                if end > start:
                    entries.append((start, end, text))
    else:
        cursor = 0
        for segment in timeline.get("segments") or []:
            duration = max(0, int(segment.get("duration_ms") or 0))
            seg_start = cursor
            seg_end = min(total_ms, seg_start + duration)
            lines = query(
                """SELECT text, start_ms, duration_ms
                   FROM dialogue_lines
                   WHERE scene_id = ?
                   ORDER BY order_index ASC, created_at ASC""",
                (segment.get("scene_id"),),
            )
            line_cursor = seg_start
            for line in lines:
                text = str(line.get("text") or "").strip().replace("\r", " ").replace("\n", " ")
                if not text:
                    continue
                start = max(line_cursor, seg_start + max(0, int(line.get("start_ms") or 0)))
                duration_ms = int(line.get("duration_ms") or 0) or _estimate_line_ms(text)
                end = min(seg_end, start + duration_ms)
                if end > start:
                    entries.append((start, end, text))
                    line_cursor = end + 120
            cursor += duration
    if not entries:
        return ""
    blocks: list[str] = []
    for index, (start, end, text) in enumerate(entries, start=1):
        blocks.append(f"{index}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}\n")
    return "\n".join(blocks)


async def _run_ffmpeg(
    cmd: list[str],
    *,
    log_path: Path,
    episode_id: str,
    media_duration_ms: int,
    progress_start: float,
    progress_end: float,
) -> None:
    if episode_id in _cancel_requested:
        raise ExportCancelled("Export cancelled.")
    with log_path.open("ab") as log_handle:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=log_handle,
            creationflags=_creation_flags(),
        )
        last = -1.0
        assert process.stdout is not None
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            if episode_id in _cancel_requested:
                process.kill()
                await process.wait()
                raise ExportCancelled("Export cancelled.")
            text = line.decode("utf-8", errors="replace").strip()
            if not text or "=" not in text:
                continue
            key, value = text.split("=", 1)
            if key not in ("out_time_us", "out_time_ms", "out_time"):
                continue
            try:
                if key == "out_time":
                    hours, minutes, seconds = value.split(":")
                    elapsed_ms = (int(hours) * 3600 + int(minutes) * 60 + float(seconds)) * 1000
                else:
                    elapsed_ms = float(value) / 1000
            except (ValueError, TypeError):
                continue
            if media_duration_ms <= 0:
                continue
            fraction = min(1.0, max(0.0, elapsed_ms / media_duration_ms))
            progress = progress_start + (progress_end - progress_start) * fraction
            if progress - last >= 1.0:
                _set_progress(episode_id, progress)
                last = progress
        code = await process.wait()
        if code != 0:
            if episode_id in _cancel_requested:
                raise ExportCancelled("Export cancelled.")
            raise RuntimeError(f"FFmpeg failed with exit code {code}.\n{_tail(log_path)}")


def _video_filter(width: int, height: int, fps: float) -> str:
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,"
        f"fps={fps},format=yuv420p"
    )


def _render_segment_args(
    ffmpeg: str,
    source: Path,
    output: Path,
    *,
    kind: str,
    duration_ms: int,
    trim_start_ms: int,
    width: int,
    height: int,
    fps: float,
    fade: bool,
    fade_ms: int,
    motion: str = "none",
) -> list[str]:
    seconds = max(0.1, duration_ms / 1000)
    if kind == "image" and motion in ("zoom_in", "zoom_out", "pan_left", "pan_right"):
        frames = max(2, int(round(seconds * fps)))
        zoom_width = width * 2
        zoom_height = height * 2
        if motion == "zoom_in":
            z = "min(zoom+0.0015,1.15)"
            x = "iw/2-(iw/zoom/2)"
            y = "ih/2-(ih/zoom/2)"
        elif motion == "zoom_out":
            z = "if(eq(on,1),1.15,max(zoom-0.0015,1.0))"
            x = "iw/2-(iw/zoom/2)"
            y = "ih/2-(ih/zoom/2)"
        elif motion == "pan_left":
            z = "1.12"
            x = f"(iw-iw/zoom)*(1-(on-1)/{frames - 1})"
            y = "(ih-ih/zoom)/2"
        else:
            z = "1.12"
            x = f"(iw-iw/zoom)*((on-1)/{frames - 1})"
            y = "(ih-ih/zoom)/2"
        vf = (
            f"scale={zoom_width}:{zoom_height}:force_original_aspect_ratio=decrease,"
            f"pad={zoom_width}:{zoom_height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={width}x{height}:fps={fps:g},"
            "format=yuv420p"
        )
    else:
        vf = _video_filter(width, height, fps)
    if fade and fade_ms > 0 and seconds > 0.5:
        fade_seconds = min(fade_ms / 1000, seconds / 2)
        vf += f",fade=t=in:st=0:d={fade_seconds:.3f},fade=t=out:st={max(0, seconds - fade_seconds):.3f}:d={fade_seconds:.3f}"
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-progress", "pipe:1", "-nostats"]
    if kind == "image":
        cmd += ["-loop", "1", "-i", str(source), "-t", f"{seconds:.3f}"]
    else:
        cmd += ["-stream_loop", "-1"]
        if trim_start_ms > 0:
            cmd += ["-ss", f"{trim_start_ms / 1000:.3f}"]
        cmd += ["-i", str(source), "-t", f"{seconds:.3f}"]
    cmd += [
        "-an",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-r",
        f"{fps:g}",
        str(output),
    ]
    return cmd


def _audio_items(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    items = [dict(item) for item in timeline.get("audio") or []]
    settings = timeline.get("settings") or {}
    music_id = settings.get("background_music_asset_id")
    if music_id:
        items.append(
            {
                "asset_id": music_id,
                "start_ms": 0,
                "volume": float(settings.get("background_music_volume", 0.35)),
                "loop": True,
                "label": "Background music",
                "kind": "music",
            }
        )
    return items


async def _run_export(episode_id: str) -> None:
    async with _export_lock:
        await _export(episode_id)


async def _export(episode_id: str) -> None:
    episode = query_one("SELECT * FROM episodes WHERE id = ?", (episode_id,))
    if not episode:
        return
    if episode_id in _cancel_requested:
        execute(
            "UPDATE episodes SET status='cancelled', error=?, finished_at=?, updated_at=? WHERE id=?",
            ("Export cancelled.", now(), now(), episode_id),
        )
        return

    project_id = episode["project_id"]
    config = load_config()
    started = time.perf_counter()
    work_dir: Path | None = None
    try:
        timeline = parse_timeline(episode.get("timeline_json"))
        timeline = validate_timeline(EpisodeTimeline.model_validate(timeline), project_id)
        segments = timeline["segments"]
        settings = timeline["settings"]
        duration_ms = total_duration_ms(timeline)
        if duration_ms <= 0:
            raise ValueError("Timeline duration is zero.")

        execute(
            "UPDATE episodes SET status='exporting', progress=1, error=NULL, started_at=?, finished_at=NULL, updated_at=? WHERE id=?",
            (now(), now(), episode_id),
        )
        _append_log(
            episode_id,
            f"Export started: {len(segments)} segment(s), {duration_ms / 1000:.2f}s, "
            f"{settings['width']}x{settings['height']} @ {settings['fps']:g} fps.",
        )

        ffmpeg = _ffmpeg(config)
        output_root = Path(config["paths"]["output_dir"]).resolve()
        episode_dir = output_root / project_id / "episodes" / episode_id
        episode_dir.mkdir(parents=True, exist_ok=True)
        work_dir = episode_dir / f"work_{uuid.uuid4().hex[:8]}"
        work_dir.mkdir(parents=True, exist_ok=True)
        log_path = work_dir / "ffmpeg.log"

        segment_files: list[Path] = []
        for index, segment in enumerate(segments):
            asset_id = str(segment["asset_id"])
            resolved = asset_file(asset_id)
            if not resolved:
                raise ValueError(f"Media asset {asset_id} is missing from disk.")
            source, asset = resolved
            kind = "image" if str(segment["kind"]) == "image" else "video"
            target = work_dir / f"segment_{index:03d}.mp4"
            start_progress = 3 + (index / len(segments)) * 62
            end_progress = 3 + ((index + 1) / len(segments)) * 62
            _append_log(
                episode_id,
                f"Rendering segment {index + 1}/{len(segments)} from {asset['filename']} ({kind}, "
                f"{segment['duration_ms'] / 1000:.2f}s).",
            )
            cmd = _render_segment_args(
                ffmpeg,
                source,
                target,
                kind=kind,
                duration_ms=int(segment["duration_ms"]),
                trim_start_ms=int(segment.get("trim_start_ms") or 0),
                width=int(settings["width"]),
                height=int(settings["height"]),
                fps=float(settings["fps"]),
                fade=str(segment.get("transition") or "cut") == "fade",
                fade_ms=int(settings.get("fade_duration_ms") or 0),
                motion=str(segment.get("motion") or "none"),
            )
            await _run_ffmpeg(
                cmd,
                log_path=log_path,
                episode_id=episode_id,
                media_duration_ms=int(segment["duration_ms"]),
                progress_start=start_progress,
                progress_end=end_progress,
            )
            if not target.exists():
                raise RuntimeError(f"FFmpeg did not produce segment {index + 1}.")
            segment_files.append(target)

        _set_progress(episode_id, 68)
        concat_file = work_dir / "concat.txt"
        concat_file.write_text(
            "\n".join(f"file '{path.as_posix()}'" for path in segment_files) + "\n",
            encoding="utf-8",
        )
        silent_video = work_dir / "silent.mp4"
        _append_log(episode_id, "Concatenating segments.")
        await _run_ffmpeg(
            [
                ffmpeg,
                "-hide_banner",
                "-nostdin",
                "-y",
                "-progress",
                "pipe:1",
                "-nostats",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                "-an",
                str(silent_video),
            ],
            log_path=log_path,
            episode_id=episode_id,
            media_duration_ms=duration_ms,
            progress_start=68,
            progress_end=78,
        )

        subtitle_file: Path | None = None
        if str(settings.get("subtitles") or "soft") != "none":
            srt = build_srt(timeline, duration_ms)
            if srt.strip():
                subtitle_file = work_dir / "episode.srt"
                subtitle_file.write_text(srt, encoding="utf-8")
                _append_log(episode_id, "Built subtitle track from dialogue lines.")
            else:
                _append_log(episode_id, "No dialogue lines found; subtitle track skipped.")

        audio_items = _audio_items(timeline)
        final_temp = work_dir / "episode.mp4"
        if audio_items:
            _append_log(episode_id, f"Mixing {len(audio_items)} audio track(s).")
            inputs: list[str] = []
            filters: list[str] = []
            total_seconds = duration_ms / 1000
            for index, item in enumerate(audio_items, start=1):
                resolved = asset_file(str(item["asset_id"]))
                if not resolved:
                    raise ValueError(f"Audio asset {item['asset_id']} is missing from disk.")
                source, asset = resolved
                if str(asset.get("mime") or "").startswith("video/"):
                    raise ValueError(f"Asset {item['asset_id']} is not audio.")
                if item.get("loop"):
                    inputs += ["-stream_loop", "-1", "-t", f"{total_seconds:.3f}", "-i", str(source)]
                else:
                    inputs += ["-i", str(source)]
                delay = max(0, int(item.get("start_ms") or 0))
                volume = max(0.0, min(2.0, float(item.get("volume", 1.0))))
                chain = (
                    f"[{index}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                    f"atrim=0:{total_seconds:.3f},asetpts=PTS-STARTPTS,volume={volume:.3f}"
                )
                if delay > 0:
                    chain += f",adelay={delay}|{delay}"
                chain += f"[a{index}]"
                filters.append(chain)
            if len(audio_items) == 1:
                filters.append(
                    "[a1]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,"
                    "alimiter=limit=0.95[aout]"
                )
            else:
                labels = "".join(f"[a{index}]" for index in range(1, len(audio_items) + 1))
                filters.append(
                    f"{labels}amix=inputs={len(audio_items)}:duration=longest:normalize=0,"
                    "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,"
                    "alimiter=limit=0.95[aout]"
                )
            cmd = [
                ffmpeg,
                "-hide_banner",
                "-nostdin",
                "-y",
                "-progress",
                "pipe:1",
                "-nostats",
                "-i",
                str(silent_video),
                *inputs,
            ]
            if subtitle_file:
                cmd += ["-i", str(subtitle_file)]
            cmd += [
                "-filter_complex",
                ";".join(filters),
                "-map",
                "0:v",
                "-map",
                "[aout]",
            ]
            if subtitle_file:
                cmd += [
                    "-map",
                    f"{1 + len(audio_items)}:s",
                    "-c:s",
                    "mov_text",
                    "-metadata:s:s:0",
                    "language=eng",
                ]
            cmd += [
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-t",
                f"{total_seconds:.3f}",
            ]
            cmd.append(str(final_temp))
            await _run_ffmpeg(
                cmd,
                log_path=log_path,
                episode_id=episode_id,
                media_duration_ms=duration_ms,
                progress_start=80,
                progress_end=97,
            )
        elif subtitle_file:
            _append_log(episode_id, "Muxing subtitle track.")
            await _run_ffmpeg(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-nostdin",
                    "-y",
                    "-progress",
                    "pipe:1",
                    "-nostats",
                    "-i",
                    str(silent_video),
                    "-i",
                    str(subtitle_file),
                    "-map",
                    "0:v",
                    "-map",
                    "1:s",
                    "-c:v",
                    "copy",
                    "-c:s",
                    "mov_text",
                    "-metadata:s:s:0",
                    "language=eng",
                    "-t",
                    f"{duration_ms / 1000:.3f}",
                    str(final_temp),
                ],
                log_path=log_path,
                episode_id=episode_id,
                media_duration_ms=duration_ms,
                progress_start=80,
                progress_end=97,
            )
        else:
            shutil.copy2(silent_video, final_temp)

        _set_progress(episode_id, 98)
        asset = store_asset_from_path(
            project_id=project_id,
            subdir=f"episodes/{episode_id}",
            filename="episode.mp4",
            source_path=final_temp,
            kind="video",
            mime="video/mp4",
            meta={
                "episode_id": episode_id,
                "kind": "episode",
                "width": settings["width"],
                "height": settings["height"],
                "fps": settings["fps"],
                "duration_ms": duration_ms,
                "segments": len(segments),
                "audio_tracks": len(audio_items),
                "subtitles": bool(subtitle_file),
            },
        )
        subtitle_rel = None
        if subtitle_file:
            mp4_target = output_root / asset["rel_path"]
            srt_target = mp4_target.with_suffix(".srt")
            shutil.copy2(subtitle_file, srt_target)
            subtitle_rel = srt_target.relative_to(output_root).as_posix()

        elapsed = time.perf_counter() - started
        size_mb = Path(output_root / asset["rel_path"]).stat().st_size / (1024 * 1024)
        summary = (
            f"Export completed in {elapsed:.2f}s: {settings['width']}x{settings['height']} @ "
            f"{settings['fps']:g} fps, {duration_ms / 1000:.2f}s, {size_mb:.2f} MB, "
            f"{len(segments)} segments, {len(audio_items)} audio track(s)."
        )
        _append_log(episode_id, summary)
        execute(
            """UPDATE episodes
               SET status='completed', progress=100, output_path=?, output_asset_id=?, subtitle_path=?,
                   duration_ms=?, error=NULL, finished_at=?, updated_at=?
               WHERE id=?""",
            (
                asset["rel_path"],
                asset["id"],
                subtitle_rel,
                duration_ms,
                now(),
                now(),
                episode_id,
            ),
        )
    except ExportCancelled:
        execute(
            "UPDATE episodes SET status='cancelled', error=?, finished_at=?, updated_at=? WHERE id=?",
            ("Export cancelled.", now(), now(), episode_id),
        )
        _append_log(episode_id, "Export cancelled.")
    except Exception as exc:  # noqa: BLE001 - store a readable failure on the episode
        logger.exception("Episode %s export failed", episode_id)
        tail = ""
        if work_dir is not None:
            tail = _tail(work_dir / "ffmpeg.log")
        message = str(exc)
        if tail:
            message = f"{message}\n{tail}"[-12000:]
        execute(
            "UPDATE episodes SET status='failed', error=?, log=?, finished_at=?, updated_at=? WHERE id=?",
            (message[:4000], message[-12000:], now(), now(), episode_id),
        )
    finally:
        _cancel_requested.discard(episode_id)
        if work_dir is not None:
            shutil.rmtree(work_dir, ignore_errors=True)


def start_export(episode_id: str) -> dict[str, Any]:
    episode = query_one("SELECT * FROM episodes WHERE id = ?", (episode_id,))
    if not episode:
        raise ValueError("Episode not found.")
    if episode.get("status") in ("queued", "exporting"):
        raise ValueError("This episode is already exporting.")
    has_output = bool(episode.get("output_asset_id"))
    execute(
        """UPDATE episodes
           SET status='queued', progress=0, error=NULL, log=?, started_at=?, finished_at=NULL, updated_at=?
           WHERE id=?""",
        ("Queued for export.", now(), now(), episode_id),
    )
    task = asyncio.create_task(_run_export(episode_id))
    _tasks[episode_id] = task

    def _done(_: asyncio.Task) -> None:
        _tasks.pop(episode_id, None)

    task.add_done_callback(_done)
    return {"episode_id": episode_id, "status": "queued", "had_output": has_output}


def cancel_export(episode_id: str) -> str:
    episode = query_one("SELECT * FROM episodes WHERE id = ?", (episode_id,))
    if not episode:
        return "not_found"
    status = str(episode.get("status") or "")
    if status == "queued":
        _cancel_requested.add(episode_id)
        execute(
            "UPDATE episodes SET status='cancelled', error=?, finished_at=?, updated_at=? WHERE id=?",
            ("Export cancelled.", now(), now(), episode_id),
        )
        task = _tasks.get(episode_id)
        if task:
            task.cancel()
        return "cancelled"
    if status == "exporting":
        _cancel_requested.add(episode_id)
        return "cancelling"
    return "not_running"
