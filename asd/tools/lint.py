"""Linting tool for HDL sources."""

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from rich.console import Console

from ..core.config import ModuleConfig
from ..core.loader import TOMLLoader
from ..core.repository import Repository
from ..simulators.verilator import VerilatorSimulator
from ..utils.config_validation import validate_tool_configuration
from ..utils.logging import get_logger
from ..utils.sources import SourceManager

logger = get_logger()

# Build directory name (same as simulation)
BUILD_DIR_NAME = "asdw"


@contextmanager
def _redirect_output(log_file: Path) -> Iterator[None]:
    """Redirect stdout/stderr to log file using OS-level file descriptors.

    Args:
        log_file: Path to log file

    Yields:
        None
    """
    sys.stdout.flush()
    sys.stderr.flush()

    stdout_fd = sys.stdout.fileno()
    stderr_fd = sys.stderr.fileno()

    saved_stdout = os.dup(stdout_fd)
    saved_stderr = os.dup(stderr_fd)

    try:
        log_fd = os.open(str(log_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        os.dup2(log_fd, stdout_fd)
        os.dup2(log_fd, stderr_fd)
        os.close(log_fd)

        yield

        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        os.dup2(saved_stdout, stdout_fd)
        os.dup2(saved_stderr, stderr_fd)
        os.close(saved_stdout)
        os.close(saved_stderr)


class Linter:
    """HDL linting tool."""

    def __init__(self, repository: Repository, loader: TOMLLoader) -> None:
        """Initialize linter.

        Args:
            repository: Repository instance
            loader: TOML loader instance
        """
        self.repo = repository
        self.loader = loader
        self.source_manager = SourceManager(repository, loader)

    def validate_configuration(
        self, config: ModuleConfig, requested_config: str
    ) -> tuple[bool, str]:
        """Validate that requested configuration is allowed by lint tool.

        Args:
            config: Module configuration
            requested_config: Configuration name requested via CLI

        Returns:
            Tuple of (is_valid, error_message)
        """
        return validate_tool_configuration(
            config=config,
            requested_config=requested_config,
            tool_config=config.lint,
            tool_name="lint",
        )

    def lint(
        self,
        config: ModuleConfig,
        toml_stem: str,
        configuration: str | None = None,
        param_overrides: dict[str, Any] | None = None,
        tool: str = "verilator",
        extra_args: list[str] | None = None,
    ) -> int:
        """Run lint checks on HDL sources.

        Args:
            config: Module configuration
            toml_stem: TOML file stem (for build directory naming)
            configuration: Configuration to use
            param_overrides: Parameter overrides
            tool: Lint tool to use
            extra_args: Additional arguments to pass to the linter

        Returns:
            Number of issues found (0 for success)
        """
        console = Console()
        configuration = configuration or "default"

        if tool != "verilator":
            logger.error(f"Unsupported lint tool '{tool}'")
            return 1

        # Create build directory and log file
        build_dir = Path(BUILD_DIR_NAME) / f"{toml_stem}-{configuration}"
        build_dir.mkdir(parents=True, exist_ok=True)
        log_file = build_dir / "asd.log"

        console.print(f"[dim]Log file: {log_file.resolve()}[/dim]")

        # Use Verilator for linting (pass build_dir for --Mdir)
        verilator = VerilatorSimulator(build_dir=build_dir)

        if not verilator.is_available():
            logger.error("Verilator is not available on this system")
            return 1

        # Compose parameters and defines for linting
        composed = self.loader.composer.compose(config, "lint", configuration, param_overrides)

        parameters = composed["parameters"]
        defines = composed["defines"]

        # Prepare source files
        sources = self.source_manager.prepare_sources(config)
        if not sources:
            logger.error("No source files found")
            return 1

        # Get include directories
        includes = self.source_manager.get_include_dirs(config)

        # Run lint with output redirected to log file
        with _redirect_output(log_file):
            ret = verilator.lint(
                sources=sources,
                parameters=parameters,
                defines=defines,
                includes=includes,
                extra_args=extra_args or [],
            )

        return ret
