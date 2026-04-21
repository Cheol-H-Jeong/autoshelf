from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from autoshelf.paths import log_dir


def configure_logging(level: str = "INFO") -> Path:
    logs = log_dir()
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / "autoshelf.log"
    logger.remove()
    logger.add(sys.stderr, level=level.upper())
    logger.add(log_path, rotation="10 MB", retention=5, level=level.upper())
    return log_path
