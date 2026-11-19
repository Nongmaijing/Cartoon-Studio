from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

SCHEMA_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
"""

MIGRATIONS: list[dict[str, Any]] = [
    {
        "version": 1,
        "name": "ai_integration_foundation",
        "columns": [
            ("projects", "memory_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("characters", "memory_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("characters", "approval_status", "TEXT NOT NULL DEFAULT 'draft'"),
            ("characters", "approved_at", "TEXT"),
            ("characters", "version", "INTEGER NOT NULL DEFAULT 1"),
            ("scenes", "approval_status", "TEXT NOT NULL DEFAULT 'draft'"),
            ("scenes", "approved_at", "TEXT"),
            ("scenes", "quality_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("scenes", "version", "INTEGER NOT NULL DEFAULT 1"),
            ("episodes", "production_state", "TEXT NOT NULL DEFAULT 'DRAFT'"),
            ("episodes", "production_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("episodes", "script_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("episodes", "storyboard_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("episodes", "approved_at", "TEXT"),
            ("episodes", "approved_by", "TEXT"),
            ("assets", "version", "INTEGER NOT NULL DEFAULT 1"),
            ("assets", "parent_asset_id", "TEXT"),
            ("assets", "approved", "INTEGER NOT NULL DEFAULT 0"),
        ],
        "sql": """
CREATE TABLE IF NOT EXISTS ai_conversations (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    episode_id TEXT,
    title TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    last_response_id TEXT,
    context_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    tool_calls_json TEXT NOT NULL DEFAULT '[]',
    response_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_tool_executions (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    tool_name TEXT NOT NULL,
    arguments_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'running',
    error TEXT,
    actor TEXT NOT NULL DEFAULT 'ai_director',
    idempotency_key TEXT,
    created_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS ai_context_snapshots (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    project_id TEXT,
    snapshot_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS production_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'DRAFT',
    status TEXT NOT NULL DEFAULT 'idle',
    progress REAL NOT NULL DEFAULT 0,
    plan_json TEXT NOT NULL DEFAULT '{}',
    current_stage TEXT,
    error TEXT,
    log TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS production_tasks (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    scene_id TEXT,
    job_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS provider_configs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(name, type)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    detail_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS character_versions (
    id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL DEFAULT '{}',
    approved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS asset_versions (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL,
    parent_asset_id TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    operation TEXT NOT NULL DEFAULT 'generated',
    approved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scene_reviews (
    id TEXT PRIMARY KEY,
    scene_id TEXT NOT NULL,
    status TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL DEFAULT 'user',
    quality_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mcp_tokens (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    scopes TEXT NOT NULL DEFAULT 'production',
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_ai_messages_conversation ON ai_messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_tools_conversation ON ai_tool_executions(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_tools_status ON ai_tool_executions(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_tools_idempotency
    ON ai_tool_executions(tool_name, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_production_runs_project ON production_runs(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_production_runs_episode ON production_runs(episode_id, created_at);
CREATE INDEX IF NOT EXISTS idx_production_tasks_run ON production_tasks(run_id, created_at);
CREATE INDEX IF NOT EXISTS idx_production_tasks_status ON production_tasks(status);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id, created_at);
CREATE INDEX IF NOT EXISTS idx_character_versions ON character_versions(character_id, version);
CREATE INDEX IF NOT EXISTS idx_asset_versions ON asset_versions(asset_id, version);
CREATE INDEX IF NOT EXISTS idx_scene_reviews ON scene_reviews(scene_id, created_at);
CREATE INDEX IF NOT EXISTS idx_mcp_tokens_hash ON mcp_tokens(token_hash);

INSERT OR IGNORE INTO provider_configs (id, name, type, config_json, enabled, created_at, updated_at)
VALUES
 ('prov_comfyui_image', 'comfyui_image', 'image', '{}', 1, datetime('now'), datetime('now')),
 ('prov_comfyui_video', 'comfyui_video', 'video', '{}', 1, datetime('now'), datetime('now')),
 ('prov_kokoro_audio', 'kokoro_audio', 'audio', '{}', 1, datetime('now'), datetime('now')),
 ('prov_ffmpeg_editing', 'ffmpeg_editing', 'editing', '{}', 1, datetime('now'), datetime('now'));
""",
    },
    {
        "version": 2,
        "name": "production_resource_tracking",
        "columns": [
            ("jobs", "resource_class", "TEXT"),
            ("jobs", "model_name", "TEXT"),
            ("jobs", "execution_seconds", "REAL"),
            ("jobs", "peak_vram_mb", "INTEGER"),
            ("jobs", "priority", "INTEGER NOT NULL DEFAULT 0"),
            ("jobs", "estimated_seconds", "REAL"),
            ("production_tasks", "resource_class", "TEXT"),
            ("production_tasks", "model_name", "TEXT"),
            ("production_tasks", "execution_seconds", "REAL"),
            ("production_tasks", "peak_vram_mb", "INTEGER"),
            ("production_runs", "estimated_seconds", "REAL"),
            ("production_runs", "actual_seconds", "REAL"),
        ],
        "sql": """
CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(status, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_resource ON jobs(resource_class, created_at);
""",
    },
    {
        "version": 3,
        "name": "lip_sync_cues",
        "columns": [
            ("dialogue_lines", "lip_sync_json", "TEXT NOT NULL DEFAULT '{}'"),
        ],
        "sql": "",
    },
    {
        "version": 4,
        "name": "script_revisions",
        "columns": [],
        "sql": """
CREATE TABLE IF NOT EXISTS script_revisions (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    revision_number INTEGER NOT NULL,
    script_json TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    script_format TEXT NOT NULL DEFAULT 'story_scenes',
    scene_count INTEGER NOT NULL DEFAULT 0,
    dialogue_lines INTEGER NOT NULL DEFAULT 0,
    base_revision_id TEXT,
    actor TEXT NOT NULL DEFAULT 'user',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(episode_id, revision_number)
);

CREATE INDEX IF NOT EXISTS idx_script_revisions_episode
    ON script_revisions(episode_id, revision_number);
""",
    },
]


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return column in {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def run_migrations(conn: sqlite3.Connection) -> list[int]:
    conn.executescript(SCHEMA_MIGRATIONS)
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    newly_applied: list[int] = []
    for migration in MIGRATIONS:
        version = int(migration["version"])
        if version in applied:
            continue
        for table, column, ddl in migration.get("columns", []):
            if not _column_exists(conn, table, column):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        conn.executescript(migration["sql"])
        conn.execute(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
            (version, migration["name"], datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        newly_applied.append(version)
    return newly_applied
