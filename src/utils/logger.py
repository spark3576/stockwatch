"""로깅 설정."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logger(level: str | None = None) -> None:
    """전역 로거 초기화."""
    log_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:HH:mm:ss}</green> <level>{level:<7}</level> <cyan>{name}</cyan>: {message}",
    )
    logger.add(
        LOG_DIR / "stockwatch.log",
        level="DEBUG",
        rotation="10 MB",
        retention=10,
        encoding="utf-8",
    )


__all__ = ["logger", "setup_logger"]
