"""Simulation runner for ASD using cocotb."""

import json
import os
import re
import shutil
import sys
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from ..core.config import ModuleConfig
from ..core.loader import TOMLLoader
from ..core.repository import Repository
from ..utils.sources import SourceManager


@contextmanager
def _redirect_output(log_file: Path) -> Iterator[None]:
    """Redirect stdout/stderr to log file using OS-level file descriptors.

    Always writes all output to log file. This captures subprocess output
    that writes directly to file descriptors, not just Python's print() statements.

    Args:
        log_file: Path to log file

    Yields:
        None
    """
    # Flush Python buffers before redirecting
    sys.stdout.flush()
    sys.stderr.flush()

    stdout_fd = sys.stdout.fileno()
    stderr_fd = sys.stderr.fileno()

    # Save original file descriptors
    saved_stdout = os.dup(stdout_fd)
    saved_stderr = os.dup(stderr_fd)

    try:
        # Open log file and redirect both stdout and stderr to it
        log_fd = os.open(str(log_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        os.dup2(log_fd, stdout_fd)
        os.dup2(log_fd, stderr_fd)
        os.close(log_fd)

        yield

        # Flush before restoring
        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        # Restore original file descriptors
        os.dup2(saved_stdout, stdout_fd)
        os.dup2(saved_stderr, stderr_fd)
        os.close(saved_stdout)
        os.close(saved_stderr)


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
        log_filename: str | None = None,
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
            log_filename: Custom log filename (default: asd-YYYY-MM-DD-HH-MM-SS.log)

        Returns:
            Return code (0 for success)
        """
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

        # Suppress experimental API warning from cocotb
        warnings.filterwarnings("ignore", category=UserWarning, module="cocotb.runner")

        try:
            from cocotb.runner import get_runner
        except ImportError:
            print("Error: cocotb is required for simulation")
            print("Install with: pip install cocotb")
            return 1

        # Create build directory: asdw/{toml_stem}-{configuration}/
        build_dir = Path("asdw") / f"{toml_stem}-{configuration}"
        build_dir.mkdir(parents=True, exist_ok=True)

        # Prepare environment variables with configuration
        test_env = self._prepare_test_environment(parameters, defines, configuration)

        # Set up test module directories
        test_dirs = set()
        test_modules = []
        for test_file in test_files:
            test_modules.append(test_file.stem)
            test_dirs.add(str(test_file.parent.resolve()))

        # Get cocotb runner
        runner = get_runner(simulator)

        # Set up logging with timestamp or custom filename
        if log_filename:
            # Custom log filename is relative to current directory, not build dir
            log_file = Path(log_filename)
        else:
            # Default log filename goes in asdw directory with configuration name
            timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            log_file = Path("asdw") / f"{configuration}-{timestamp}.log"
        log_file_abs = log_file.resolve()

        from rich.console import Console

        console = Console()
        console.print(f"[dim]Log file: {log_file_abs}[/dim]")

        # Copy test files to build directory
        # This is necessary because cocotb's subprocess doesn't respect PYTHONPATH
        for test_file in test_files:
            dest = build_dir / test_file.name
            shutil.copy2(test_file, dest)

        # Also ensure asd package is in PYTHONPATH so tests can import asd.simulators.cocotb_utils
        asd_package_dir = Path(__file__).parent.parent.parent.resolve()  # Go up to asd root
        current_pythonpath = os.environ.get("PYTHONPATH", "")
        if current_pythonpath:
            os.environ["PYTHONPATH"] = f"{asd_package_dir}:{current_pythonpath}"
        else:
            os.environ["PYTHONPATH"] = str(asd_package_dir)

        try:
            # Redirect all output (build and test) to log file
            with _redirect_output(log_file):
                # Prepare build arguments for waveform tracing
                build_args = []
                if waves and simulator == "verilator":
                    build_args = ["--trace", "--trace-structs"]

                # Build the design
                runner.build(
                    verilog_sources=[str(s) for s in sources],
                    hdl_toplevel=config.top,
                    includes=[str(i) for i in includes],
                    defines=defines,
                    parameters=parameters,
                    build_args=build_args,
                    build_dir=str(build_dir),
                    waves=waves,
                    always=True,  # Always rebuild
                )

                # Run tests (PYTHONPATH is set in os.environ above)
                # For Verilator, we need to explicitly set VM_TRACE when building with make
                test_args = []
                if waves and simulator == "verilator":
                    test_args = ["+trace"]

                runner.test(
                    hdl_toplevel=config.top,
                    test_module=",".join(test_modules),
                    waves=waves,
                    gui=gui,
                    test_args=test_args,
                    extra_env=test_env,
                    build_dir=str(build_dir),
                )

            # Check log file for test failures
            if log_file.exists():
                log_content = log_file.read_text()

                # Check for critical failures (import errors, etc.)
                if "CRITICAL" in log_content or "Failed to import module" in log_content:
                    console.print("[red]✗ Simulation failed: Test import error[/red]")
                    console.print(f"[dim]Check log file for details: {log_file_abs}[/dim]")
                    return 1

                # Check for test failures by looking for "FAIL=" in the results summary
                # Format: "** TESTS=7 PASS=3 FAIL=4 SKIP=0 **"
                fail_match = re.search(r"\*\* TESTS=\d+ PASS=\d+ FAIL=(\d+)", log_content)
                if fail_match:
                    fail_count = int(fail_match.group(1))
                    if fail_count > 0:
                        console.print(
                            f"[red]✗ Simulation failed: {fail_count} test(s) failed[/red]"
                        )
                        console.print(f"[dim]Check log file for details: {log_file_abs}[/dim]")
                        return 1

            return 0
        except Exception as e:
            console.print(f"[red]✗ Simulation failed: {e}[/red]")
            console.print(f"[dim]Check log file for details: {log_file_abs}[/dim]")
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
        test_files: list[Path] = []

        # Check if tests are defined in TOML
        if config.simulation and config.simulation.tests:
            if test_name:
                # Specific test requested
                test_config = config.simulation.tests.get(test_name)
                if test_config and hasattr(test_config, "test_module"):
                    test_file = self._resolve_test_path(test_config.test_module)
                    if test_file:
                        test_files.append(test_file)
            else:
                # No specific test - use all tests from TOML
                for test_config in config.simulation.tests.values():
                    if hasattr(test_config, "test_module"):
                        test_file = self._resolve_test_path(test_config.test_module)
                        if test_file:
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

    def _resolve_test_path(self, test_module: str) -> Path | None:
        """Resolve test module path to absolute file path.

        Args:
            test_module: Test module path (can be file path or dotted module name)

        Returns:
            Resolved test file path, or None if not found
        """
        # First, try as a direct file path
        test_file = Path(test_module)
        if not test_file.suffix:
            # If no extension, assume .py
            test_file = test_file.with_suffix(".py")

        # Try as absolute path
        if test_file.is_absolute() and test_file.exists():
            return test_file

        # Try relative to repo root
        test_file_abs = self.repo.root / test_file
        if test_file_abs.exists():
            return test_file_abs

        # Try converting dotted module name to path
        if "." in test_module and not test_module.endswith(".py"):
            test_file = Path(test_module.replace(".", "/") + ".py")
            test_file_abs = self.repo.root / test_file
            if test_file_abs.exists():
                return test_file_abs

        return None

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
        # Start with a copy of the current environment
        env = dict(os.environ)

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
        build_dir = Path("asdw") / f"{toml_stem}-{configuration}"
        if build_dir.exists():
            shutil.rmtree(build_dir)
            print(f"Cleaned {build_dir}")
