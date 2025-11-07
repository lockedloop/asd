"""Simulation runner for ASD using cocotb."""

import json
from pathlib import Path
from typing import Any

from ..core.config import ModuleConfig
from ..core.loader import TOMLLoader
from ..core.repository import Repository
from ..utils.sources import SourceManager


class SimulationRunner:
    """Coordinate simulation execution using cocotb runner API."""

    def __init__(self, repository: Repository, loader: TOMLLoader) -> None:
        """Initialize simulation runner.

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

        # If no simulation config, allow all configurations
        if not config.simulation:
            return (True, "")

        # If simulation.configurations is None or empty, allow all
        if not config.simulation.configurations:
            return (True, "")

        # If simulation.configurations contains "all", allow any configuration
        if "all" in config.simulation.configurations:
            return (True, "")

        # Otherwise, requested config must be in the allowed list
        if requested_config == "all":
            # "all" means all module configurations must be in tool's allowed list
            for cfg_name in config.configurations.keys():
                if cfg_name not in config.simulation.configurations:
                    return (
                        False,
                        f"Configuration '{cfg_name}' not supported by simulation tool. "
                        f"Tool supports: {', '.join(config.simulation.configurations)}",
                    )
            return (True, "")
        else:
            # Single config must be in allowed list
            if requested_config not in config.simulation.configurations:
                return (
                    False,
                    f"Configuration '{requested_config}' not supported by simulation tool. "
                    f"Tool supports: {', '.join(config.simulation.configurations)}",
                )
            return (True, "")

    def run(
        self,
        config: ModuleConfig,
        toml_stem: str,
        simulator: str = "verilator",
        configuration: str | None = None,
        param_overrides: dict[str, Any] | None = None,
        test_name: str | None = None,
        gui: bool = False,
        waves: bool = True,
        parallel: int | None = None,
    ) -> int:
        """Run simulation with cocotb runner API.

        Args:
            config: Module configuration
            toml_stem: TOML file stem (for build directory naming)
            simulator: Simulator to use (verilator, icarus, etc.)
            configuration: Configuration name to use
            param_overrides: Parameter overrides from CLI
            test_name: Specific test to run
            gui: Run with GUI (simulator-specific)
            waves: Generate waveforms (default: True)
            parallel: Number of parallel tests

        Returns:
            Return code (0 for success)
        """
        try:
            from cocotb.runner import get_runner
        except ImportError:
            print("Error: cocotb is required for simulation")
            print("Install with: pip install cocotb")
            return 1

        # Use default configuration if not specified
        configuration = configuration or "default"

        # Compose parameters and defines for the configuration
        composed = self.loader.composer.compose(
            config, "simulation", configuration, param_overrides
        )

        parameters = composed["parameters"]
        defines = composed["defines"]

        # Prepare source files
        sources = self.source_manager.prepare_sources(config)
        if not sources:
            print("Error: No source files found")
            return 1

        # Get include directories
        includes = self.source_manager.get_include_dirs(config)

        # Find test files (auto-discover sim_*.py or use specified tests)
        test_files = self._find_test_files(config, test_name)
        if not test_files:
            print("Error: No test files found")
            print("Expected test files matching pattern: sim_*.py")
            if config.simulation and config.simulation.tests:
                print("Or test files specified in TOML simulation.tests")
            return 1

        # Create build directory: build-{toml_stem}-{configuration}/
        build_dir = Path(f"build-{toml_stem}-{configuration}")
        build_dir.mkdir(parents=True, exist_ok=True)

        # Prepare environment variables with configuration
        test_env = self._prepare_test_environment(parameters, defines, configuration)

        # Get cocotb runner
        runner = get_runner(simulator)

        # Build the design
        runner.build(
            verilog_sources=[str(s) for s in sources],
            hdl_toplevel=config.top,
            includes=[str(i) for i in includes],
            defines=defines,
            parameters=parameters,
            build_dir=str(build_dir),
            always=True,  # Always rebuild
        )

        # Set up test modules
        test_modules = []
        for test_file in test_files:
            # Convert file path to Python module name
            # e.g., sim_counter.py -> sim_counter
            module_name = test_file.stem
            test_modules.append(module_name)

        # Run tests
        from rich.console import Console

        console = Console()
        console.print(f"[bold green]Running tests with {simulator}...[/bold green]")
        console.print(f"Configuration: {configuration}")
        console.print(f"Top module: {config.top}")
        console.print(f"Test modules: {', '.join(test_modules)}")

        try:
            runner.test(
                hdl_toplevel=config.top,
                test_module=",".join(test_modules),
                waves=waves,
                gui=gui,
                extra_env=test_env,
                build_dir=str(build_dir),
            )
            return 0
        except Exception as e:
            print(f"Simulation failed: {e}")
            return 1

    def _find_test_files(self, config: ModuleConfig, test_name: str | None = None) -> list[Path]:
        """Find test files for simulation.

        Searches for sim_*.py files in the same directory as the sources,
        or uses test files specified in the TOML configuration.

        Args:
            config: Module configuration
            test_name: Specific test name to run (optional)

        Returns:
            List of test file paths
        """
        test_files = []

        # If specific test requested and defined in config
        if test_name and config.simulation and config.simulation.tests:
            test_config = config.simulation.tests.get(test_name)
            if test_config and hasattr(test_config, "test_module"):
                # Convert module name to file path
                test_file = Path(test_config.test_module.replace(".", "/") + ".py")
                if test_file.exists():
                    test_files.append(test_file)
                else:
                    # Try relative to repo root
                    test_file = self.repo.root / test_file
                    if test_file.exists():
                        test_files.append(test_file)

        # If no test files found, auto-discover sim_*.py
        if not test_files and config.sources.modules:
            # Search in the same directory as the first source file
            first_source = Path(config.sources.modules[0])
            search_dir = first_source.parent

            # Look for sim_*.py files
            test_files = list(search_dir.glob("sim_*.py"))

            # Also check parent directory's tests folder
            tests_dir = search_dir.parent / "tests"
            if tests_dir.exists():
                test_files.extend(tests_dir.glob("sim_*.py"))

        return test_files

    def _prepare_test_environment(
        self, parameters: dict[str, Any], defines: dict[str, Any], config_name: str
    ) -> dict[str, str]:
        """Prepare environment variables for test execution.

        Encodes configuration data as JSON in environment variables that
        tests can access via cocotb_utils.py functions.

        Args:
            parameters: Composed parameters
            defines: Composed defines
            config_name: Configuration name

        Returns:
            Dictionary of environment variables
        """
        env = {}

        # Encode parameters as JSON
        if parameters:
            env["COCOTB_TEST_VAR_PARAMETERS"] = json.dumps(parameters)

        # Encode defines as JSON
        if defines:
            env["COCOTB_TEST_VAR_DEFINES"] = json.dumps(defines)

        # Store configuration name
        env["COCOTB_TEST_VAR_CONFIG_NAME"] = json.dumps(config_name)

        return env

    def list_tests(self, config: ModuleConfig) -> list[str]:
        """List available tests.

        Args:
            config: Module configuration

        Returns:
            List of test names
        """
        tests: list[str] = []

        # From explicit TOML configuration
        if config.simulation and config.simulation.tests:
            tests.extend(config.simulation.tests.keys())

        # Auto-discovered sim_*.py files
        discovered = self._find_test_files(config)
        for test_file in discovered:
            tests.append(test_file.stem)

        return list(set(tests))  # Remove duplicates

    def clean(self, toml_stem: str, configuration: str = "default") -> None:
        """Clean simulation artifacts.

        Args:
            toml_stem: TOML file stem
            configuration: Configuration name
        """
        import shutil

        build_dir = Path(f"build-{toml_stem}-{configuration}")
        if build_dir.exists():
            shutil.rmtree(build_dir)
            print(f"Cleaned {build_dir}")
