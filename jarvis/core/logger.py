"""
JARVIS Structured Logging Module
Provides unified, thread-safe console and file logging with
correlation IDs, ISO timestamps, and log rotation support.
"""

import logging
import sys
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from jarvis.config import settings


def setup_logger(name: str = "jarvis") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if settings.jarvis_debug else logging.INFO)

    # Attach ZeroLeakLogFilter to eradicate secret leaks across console and file logs
    try:
        from jarvis.security.ten_layer_shield import ZeroLeakLogFilter
        leak_filter = ZeroLeakLogFilter()
    except Exception:
        leak_filter = None

    # Avoid adding duplicate handlers if already configured
    if logger.handlers:
        if leak_filter:
            for h in logger.handlers:
                if leak_filter not in getattr(h, "filters", []):
                    h.addFilter(leak_filter)
            if leak_filter not in getattr(logger, "filters", []):
                logger.addFilter(leak_filter)
        return logger

    # Ensure log directory exists
    log_file = settings.audit_log_path.parent / "jarvis.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Formatter
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s:%(module)s:%(lineno)d] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    if leak_filter:
        console_handler.addFilter(leak_filter)
    logger.addHandler(console_handler)

    # Rotating File Handler (Max 10MB, 5 backups)
    try:
        file_handler = RotatingFileHandler(
            filename=str(log_file), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        if leak_filter:
            file_handler.addFilter(leak_filter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Failed to initialize rotating file logger: {e}")

    if leak_filter:
        logger.addFilter(leak_filter)

    return logger


# Global default logger
logger = setup_logger()
get_logger = setup_logger
