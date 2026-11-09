from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from ..config import load_config
from ..db import execute, now, query, query_one
from ..logging_setup import logger


def _decorate(row: dict[str, Any]) -> dict[str, Any]:
    row["meta"] = json.loads(row.pop("meta_json") or "{}")
    row["url"] = f"/api/assets/{row['id']}/file"
    return row


def list_assets(
    limit: int = 50,
    project_id: str | None = None,
    kind: str | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM assets"
    clauses: list[str] = []
    params: list[Any] = []
    if project_id:
        clauses.append("project_id = ?")
        params.append(project_id)
    if kind:
        clauses.append("kind = ?")
        params.append(kind)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    return [_decorate(row) for row in query(sql, params)]


def get_asset(asset_id: str) -> dict[str, Any] | None:
    row = query_one("SELECT * FROM assets WHERE id = ?", (asset_id,))
    return _decorate(row) if row else None


def asset_file(asset_id: str) -> tuple[Path, dict[str, Any]] | None:
    asset = get_asset(asset_id)
    if not asset:
        return None
    config = load_config()
    root = Path(config["paths"]["output_dir"]).resolve()
    path = (root / asset["rel_path"]).resolve()
    if root not in path.parents and path != root:
        return None
    if not path.exists():
        return None
    return path, asset


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


def store_asset_from_path(
    *,
    project_id: str,
    subdir: str,
    filename: str,
    source_path: Path,
    kind: str,
    mime: str,
    meta: dict[str, Any],
    job_id: str | None = None,
) -> dict[str, Any]:
    """Move a generated file into the project's output tree and register it as an asset."""
    config = load_config()
    root = Path(config["paths"]["output_dir"]).resolve()
    directory = root / project_id / subdir
    target = _unique_path(directory, filename)
    if source_path.resolve() != target.resolve():
        shutil.move(str(source_path), str(target))
    rel_path = target.relative_to(root).as_posix()
    asset_id = uuid.uuid4().hex[:12]
    execute(
        """INSERT INTO assets (id, project_id, job_id, kind, filename, rel_path, mime, meta_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            asset_id,
            project_id,
            job_id,
            kind,
            target.name,
            rel_path,
            mime,
            json.dumps(meta),
            now(),
        ),
    )
    row = query_one("SELECT * FROM assets WHERE id = ?", (asset_id,))
    if not row:
        raise RuntimeError("Could not register the generated asset.")
    logger.info("Stored %s asset %s at %s", kind, asset_id, rel_path)
    return _decorate(row)
