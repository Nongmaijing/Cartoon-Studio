from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import load_config
from .db_migrations import run_migrations

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    scene_id TEXT,
    workflow_id TEXT NOT NULL,
    workflow_name TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0,
    node TEXT,
    prompt_id TEXT,
    params_json TEXT NOT NULL DEFAULT '{}',
    outputs_json TEXT NOT NULL DEFAULT '[]',
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    job_id TEXT,
    kind TEXT NOT NULL DEFAULT 'image',
    filename TEXT NOT NULL,
    rel_path TEXT NOT NULL,
    mime TEXT NOT NULL DEFAULT 'application/octet-stream',
    meta_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS media_links (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL,
    owner_type TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'reference',
    label TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    style TEXT NOT NULL DEFAULT '',
    clothing TEXT NOT NULL DEFAULT '',
    appearance TEXT NOT NULL DEFAULT '',
    canonical_asset_id TEXT,
    voice_engine TEXT NOT NULL DEFAULT '',
    voice_name TEXT NOT NULL DEFAULT '',
    voice_rate INTEGER NOT NULL DEFAULT 0,
    voice_pitch INTEGER NOT NULL DEFAULT 0,
    voice_volume INTEGER NOT NULL DEFAULT 100,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS backgrounds (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    aspect_ratio TEXT NOT NULL DEFAULT '16:9',
    width INTEGER NOT NULL DEFAULT 1280,
    height INTEGER NOT NULL DEFAULT 720,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scenes (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    dialogue TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL DEFAULT '',
    camera TEXT NOT NULL DEFAULT '',
    duration REAL NOT NULL DEFAULT 5,
    settings_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scene_cast (
    id TEXT PRIMARY KEY,
    scene_id TEXT NOT NULL,
    character_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'main',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dialogue_lines (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    scene_id TEXT NOT NULL,
    character_id TEXT,
    order_index INTEGER NOT NULL DEFAULT 0,
    text TEXT NOT NULL DEFAULT '',
    emotion TEXT NOT NULL DEFAULT 'neutral',
    voice_engine TEXT NOT NULL DEFAULT '',
    voice_name TEXT NOT NULL DEFAULT '',
    rate INTEGER NOT NULL DEFAULT 0,
    pitch INTEGER NOT NULL DEFAULT 0,
    volume INTEGER NOT NULL DEFAULT 100,
    start_ms INTEGER NOT NULL DEFAULT 0,
    audio_asset_id TEXT,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    progress REAL NOT NULL DEFAULT 0,
    timeline_json TEXT NOT NULL DEFAULT '[]',
    settings_json TEXT NOT NULL DEFAULT '{}',
    output_path TEXT,
    output_asset_id TEXT,
    subtitle_path TEXT,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    log TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id);
CREATE INDEX IF NOT EXISTS idx_assets_job ON assets(job_id);
CREATE INDEX IF NOT EXISTS idx_media_owner ON media_links(owner_type, owner_id);
CREATE INDEX IF NOT EXISTS idx_media_asset ON media_links(asset_id);
CREATE INDEX IF NOT EXISTS idx_scene_cast_scene ON scene_cast(scene_id);
CREATE INDEX IF NOT EXISTS idx_scene_cast_character ON scene_cast(character_id);
CREATE INDEX IF NOT EXISTS idx_jobs_scene ON jobs(scene_id);
CREATE INDEX IF NOT EXISTS idx_dialogue_scene ON dialogue_lines(scene_id);
CREATE INDEX IF NOT EXISTS idx_dialogue_character ON dialogue_lines(character_id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db_path() -> Path:
    override = os.environ.get("CARTOON_STUDIO_DB_PATH", "").strip()
    if override:
        return Path(override)
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url.startswith("sqlite:///"):
        return Path(database_url[len("sqlite:///") :])
    config = load_config()
    return Path(config["paths"]["data_dir"]) / "cartoon_studio.db"


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        _ensure_column(conn, "characters", "canonical_asset_id", "TEXT")
        _ensure_column(conn, "characters", "voice_engine", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "characters", "voice_name", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "characters", "voice_rate", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "characters", "voice_pitch", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "characters", "voice_volume", "INTEGER NOT NULL DEFAULT 100")
        _ensure_column(conn, "episodes", "description", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "episodes", "progress", "REAL NOT NULL DEFAULT 0")
        _ensure_column(conn, "episodes", "settings_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(conn, "episodes", "output_asset_id", "TEXT")
        _ensure_column(conn, "episodes", "subtitle_path", "TEXT")
        _ensure_column(conn, "episodes", "duration_ms", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "episodes", "error", "TEXT")
        _ensure_column(conn, "episodes", "log", "TEXT")
        _ensure_column(conn, "episodes", "started_at", "TEXT")
        _ensure_column(conn, "episodes", "finished_at", "TEXT")
        run_migrations(conn)
        conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    """Add a column to an existing database without touching any data."""
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def query(sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]


def query_one(sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: Iterable[Any] = ()) -> None:
    with connect() as conn:
        conn.execute(sql, tuple(params))
        conn.commit()
