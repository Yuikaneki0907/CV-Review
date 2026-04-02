"""
Central logging configuration for CV-Review backend.

Usage:
    from app.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Hello", extra={"user_id": "abc"})
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# ── Log directory ────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ── Formatter ────────────────────────────────────────────────────
LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _make_file_handler(filename: str, level: int = logging.DEBUG) -> RotatingFileHandler:
    """Create a rotating file handler (5 MB × 3 backups)."""
    path = os.path.join(LOG_DIR, filename)
    handler = RotatingFileHandler(path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    return handler


def _make_console_handler(level: int = logging.DEBUG) -> logging.StreamHandler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    return handler


# ── Pre-built handlers (shared across loggers) ───────────────────
_backend_file_handler = _make_file_handler("backend.log")
_ai_file_handler = _make_file_handler("ai.log")
_console_handler = _make_console_handler()

# Read level from env
_LOG_LEVEL = getattr(logging, os.getenv("LOG_LEVEL", "DEBUG").upper(), logging.DEBUG)


def get_logger(name: str) -> logging.Logger:
    """
    Factory for module-level loggers.

    • Names starting with 'app.infrastructure.ai' → write to ai.log
    • Everything else                              → write to backend.log
    • All loggers also write to console
    """
    logger = logging.getLogger(name)

    if logger.handlers:  # already configured
        return logger

    logger.setLevel(_LOG_LEVEL)
    logger.propagate = False

    # Route to the correct file
    if name.startswith("app.infrastructure.ai") or name.startswith("ai."):
        logger.addHandler(_ai_file_handler)
    else:
        logger.addHandler(_backend_file_handler)

    logger.addHandler(_console_handler)
    return logger
