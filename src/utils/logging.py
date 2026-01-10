"""Logging utility with verbosity levels and file logging."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_logging(
    verbosity: int = 0,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """
    Set up logging with verbosity levels and file output.

    Args:
        verbosity: Verbosity level (0=WARNING, 1=INFO, 2=DEBUG, 3=DEBUG with more detail)
        log_file: Optional log file path. If None, uses default pattern.

    Returns:
        Configured logger instance
    """
    # Determine log level based on verbosity
    if verbosity == 0:
        log_level = logging.WARNING
    elif verbosity == 1:
        log_level = logging.INFO
    elif verbosity == 2:
        log_level = logging.DEBUG
    else:  # verbosity >= 3
        log_level = logging.DEBUG

    # Create logs directory if needed
    if log_file is None:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        # Use local datetime for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = logs_dir / f"log_{timestamp}.log"
    else:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Set to DEBUG to allow all levels

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler with verbosity-based level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # File handler (always DEBUG level to capture everything)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Verbosity: {verbosity}, Log file: {log_file}")

    return logger


def parse_verbosity(args: list) -> int:
    """
    Parse verbosity level from command line arguments.

    Args:
        args: Command line arguments

    Returns:
        Verbosity level (0-3)
    """
    verbosity = 0
    for arg in args:
        if arg == "-v":
            verbosity = 1
        elif arg == "-vv":
            verbosity = 2
        elif arg == "-vvv":
            verbosity = 3
    return verbosity

