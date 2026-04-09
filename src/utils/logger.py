"""Loguru singleton — import this everywhere instead of stdlib logging or print()."""
import sys

from loguru import logger

from src.utils.settings import settings

logger.remove()
logger.add(
    sys.stdout,
    level=settings.log_level,
    format="{time:ISO8601} | {level:<8} | {name}:{line} | {message}",
)

__all__ = ["logger"]
