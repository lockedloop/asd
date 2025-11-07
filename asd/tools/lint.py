"""Linting tool for HDL sources."""

from typing import Any

from ..core.config import ModuleConfig
from ..core.loader import TOMLLoader
from ..core.repository import Repository
from ..simulators.verilator import VerilatorSimulator
from ..utils.sources import SourceManager


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

    def validate_configuration(
        self, config: ModuleConfig, requested_config: str
    ) -> tuple[bool, str]:
        """Validate that requested configuration is allowed by tool configuration.

        Args:
            config: Module configuration
            requested_config: Configuration name requested via CLI

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if configuration exists in module
        if requested_config != "all" and requested_config not in config.configurations:
            return (
                False,
                f"Configuration '{requested_config}' not found. "
                f"Available: {', '.join(config.configurations.keys())}",
            )

        # If no lint config, allow all configurations
        if not config.lint:
            return (True, "")

        # If lint.configurations is None or empty, allow all
        if not config.lint.configurations:
            return (True, "")

        # If lint.configurations contains "all", allow any configuration
        if "all" in config.lint.configurations:
            return (True, "")

        # Otherwise, requested config must be in the allowed list
        if requested_config == "all":
            # "all" means all module configurations must be in tool's allowed list
            for cfg_name in config.configurations.keys():
                if cfg_name not in config.lint.configurations:
                    return (
                        False,
                        f"Configuration '{cfg_name}' not supported by lint tool. "
                        f"Tool supports: {', '.join(config.lint.configurations)}",
                    )
            return (True, "")
        else:
            # Single config must be in allowed list
            if requested_config not in config.lint.configurations:
                return (
                    False,
                    f"Configuration '{requested_config}' not supported by lint tool. "
                    f"Tool supports: {', '.join(config.lint.configurations)}",
                )
            return (True, "")

    def lint(
        self,
        config: ModuleConfig,
        configuration: str | None = None,
        param_overrides: dict[str, Any] | None = None,
        tool: str = "verilator",
        extra_args: list[str] | None = None,
        verbose: bool = False,
    ) -> int:
        """Run lint checks on HDL sources.

        Args:
            config: Module configuration
            configuration: Configuration to use
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

        # Compose parameters and defines for linting
        composed = self.loader.composer.compose(config, "lint", configuration, param_overrides)

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
