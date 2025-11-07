"""Logging configuration for ASD."""

import logging
import sys
from typing import TextIO


def setup_logging(verbose: bool = False, stream: TextIO | None = None) -> logging.Logger:
    """Configure ASD logging framework.

    Sets up a logger with appropriate formatting and handlers for the ASD tool.
    Supports both normal and verbose (debug) modes.

    Args:
        verbose: Enable verbose/debug logging (default: False)
        stream: Output stream for logging (default: sys.stderr)

    Returns:
        Configured logger instance

    Examples:
        >>> logger = setup_logging(verbose=False)
        >>> logger.info("Build started")
        INFO: Build started

        >>> logger = setup_logging(verbose=True)
        >>> logger.debug("Processing file: counter.sv")
        DEBUG: Processing file: counter.sv
    """
    logger = logging.getLogger("asd")

    # Prevent duplicate handlers if setup is called multiple times
    if logger.handlers:
        logger.handlers.clear()

    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)

    # Create console handler
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setLevel(level)

    # Simple format: LEVEL: message
    formatter = logging.Formatter("%(levelname)s: %(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger() -> logging.Logger:
    """Get the ASD logger instance.

    Returns the existing logger if already configured, otherwise sets up
    a default logger with INFO level.

    Returns:
        Logger instance

    Examples:
        >>> logger = get_logger()
        >>> logger.info("Starting simulation")
    """
    logger = logging.getLogger("asd")
    if not logger.handlers:
        # Set up default logger if not already configured
        return setup_logging(verbose=False)
    return logger
