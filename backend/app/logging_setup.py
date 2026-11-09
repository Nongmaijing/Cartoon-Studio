from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import load_config


def configure_logging() -> logging.Logger:
    config = load_config()
    log_dir = Path(config["paths"]["logs_dir"])
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "backend.log"

    logger = logging.getLogger("cartoon_studio")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    file_handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    return logger


logger = configure_logging()
