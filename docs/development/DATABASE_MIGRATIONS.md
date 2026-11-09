# Database Migrations

## Current mechanism

The app used `CREATE TABLE IF NOT EXISTS` plus `_ensure_column`. The integration adds a versioned runner:

- `backend/app/db_migrations.py`
- `schema_migrations(version, name, applied_at)`

`init_db()` calls `run_migrations(conn)` after the base schema and legacy column checks.

## Applied migration

### version 1 — ai_integration_foundation

Adds:

- Integration columns on `projects`, `characters`, `scenes`, `episodes`, `assets`.
- `ai_conversations`, `ai_messages`, `ai_tool_executions`, `ai_context_snapshots`.
- `production_runs`, `production_tasks`.
- `provider_configs` with default provider rows.
- `audit_logs`.
- `character_versions`, `asset_versions`, `scene_reviews`.
- `mcp_tokens`.
- Indexes for conversations, tool executions, production, versions, reviews and token lookup.

## Safety

- No table/column is dropped.
- Existing records are preserved.
- `ALTER TABLE ADD COLUMN` is used only when the column is missing.
- Migrations are recorded and skipped on subsequent startups.
- A backup was created before the integration:
  `backups/pre-ai-integration-20261109-221344.zip`.

## Adding a migration

Append a new entry to `MIGRATIONS` with a unique version, optional `columns`, and SQL. Never edit an already-applied migration in production; add a new version.

## Test isolation

Tests set `CARTOON_STUDIO_DB_PATH` to a temporary file and call `init_db()` per test. See `backend/tests/conftest.py`.
