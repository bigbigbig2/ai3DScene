from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_root: Path, level: str = "INFO") -> None:
    log_root.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_root / "scene_spatial.log", maxBytes=10_000_000, backupCount=5)
    formatter = logging.Formatter(
        '{"level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
    )
    handler.setFormatter(formatter)
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), handlers=[handler])
