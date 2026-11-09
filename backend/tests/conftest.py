from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_MODULE_DB_DIR = Path(tempfile.mkdtemp(prefix="cartoon_studio_tests_"))
os.environ["CARTOON_STUDIO_DB_PATH"] = str(_MODULE_DB_DIR / "module.db")


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("CARTOON_STUDIO_DB_PATH", str(db_file))
    from app.config import load_config
    from app.db import init_db
    from app.services import project_service
    from app.providers.registry import registry

    init_db()
    config = load_config()
    test_config = {
        **config,
        "paths": {
            **config["paths"],
            "projects_dir": str(tmp_path / "projects"),
            "output_dir": str(tmp_path / "outputs"),
            "logs_dir": str(tmp_path / "logs"),
            "data_dir": str(tmp_path / "data"),
            "workflow_dir": str(Path(__file__).resolve().parents[1] / "workflows"),
        },
    }
    monkeypatch.setattr(project_service, "load_config", lambda: test_config)
    registry.refresh()
    yield
