"""
Structured logging setup for GEO-ANOM.

Provides a consistent, coloured console logger with optional file output.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


_LOG_FORMAT = "%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(
    name: str = "geo_anom",
    level: str = "INFO",
    log_file: Path | str | None = None,
) -> logging.Logger:
    """
    Configure and return a named logger.

    Parameters
    ----------
    name : str
        Logger name (usually module-level, e.g. ``geo_anom.phase1``).
    level : str
        Logging level (DEBUG, INFO, WARNING, ERROR).
    log_file : Path or str, optional
        If provided, also write log lines to this file.

    Returns
    -------
    logging.Logger
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers on re-call
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    logger.addHandler(console)

    # Optional file handler
    if log_file is not None:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_path))
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
        logger.addHandler(file_handler)

    return logger
