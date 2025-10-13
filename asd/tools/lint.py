"""Linting tool for HDL sources."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.config import ModuleConfig
from ..core.loader import TOMLLoader
from ..core.repository import Repository
from ..utils.sources import SourceManager
from ..simulators.verilator import VerilatorSimulator


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
        self.source_manager = SourceManager(repository)

    def lint(
        self,
        config: ModuleConfig,
        param_set: Optional[str] = None,
        param_overrides: Optional[Dict[str, Any]] = None,
        tool: str = "verilator",
        extra_args: Optional[List[str]] = None,
        verbose: bool = False,
    ) -> int:
        """Run lint checks on HDL sources.

        Args:
            config: Module configuration
            param_set: Parameter set to use
            param_overrides: Parameter overrides
            tool: Lint tool to use
            extra_args: Additional arguments to pass to the linter
            verbose: Print the full command being executed

        Returns:
            Number of issues found (0 for success)
        """
        if tool != "verilator":
            print(f"Error: Unsupported lint tool '{tool}'")
            return 1

        # Use Verilator for linting
        verilator = VerilatorSimulator()

        if not verilator.is_available():
            print("Error: Verilator is not available on this system")
            return 1

        # Compose parameters for linting
        if param_set and config.lint:
            # Override with specified parameter set
            lint_config = config.lint.model_copy()
            lint_config.parameter_set = param_set
            temp_config = config.model_copy()
            temp_config.lint = lint_config
            composed = self.loader.composer.compose(temp_config, "lint", param_overrides)
        else:
            composed = self.loader.composer.compose(config, "lint", param_overrides)

        parameters = composed["parameters"]
        defines = composed["defines"]

        # Prepare source files
        sources = self.source_manager.prepare_sources(config)
        if not sources:
            print("Error: No source files found")
            return 1

        # Get include directories
        includes = self.source_manager.get_include_dirs(config)

        # Run lint
        print(f"Running lint checks with {tool}...")
        ret = verilator.lint(
            sources=sources,
            parameters=parameters,
            defines=defines,
            includes=includes,
            extra_args=extra_args or [],
            verbose=verbose,
        )

        return ret