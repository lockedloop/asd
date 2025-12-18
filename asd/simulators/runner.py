"""Simulation runner for ASD using cocotb."""

import json
import os
import re
import shutil
import sys
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..core.config import ModuleConfig
from ..core.loader import TOMLLoader
from ..core.repository import Repository
from ..utils.config_validation import validate_tool_configuration
from ..utils.logging import get_logger
from ..utils.sources import SourceManager

# Suppress experimental API warning from cocotb.runner
warnings.filterwarnings(
    "ignore", message="Python runners and associated APIs are an experimental feature"
)

from cocotb_tools.runner import get_runner  # noqa: E402

logger = get_logger()

# Build directory name
BUILD_DIR_NAME = "asdw"


@dataclass
class SimulationContext:
    """Context for simulation execution with all prepared data."""

    config: ModuleConfig
    configuration: str
    parameters: dict[str, Any]
    defines: dict[str, Any]
    sources: list[Path]
    includes: list[Path]
    test_files: list[Path]


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
        self.source_manager = SourceManager(repository, loader)

    def validate_configuration(
        self, config: ModuleConfig, requested_config: str
    ) -> tuple[bool, str]:
        """Validate that requested configuration is allowed by simulation tool.

        Args:
            config: Module configuration
            requested_config: Configuration name requested via CLI

        Returns:
            Tuple of (is_valid, error_message)
        """
        return validate_tool_configuration(
            config=config,
            requested_config=requested_config,
            tool_config=config.simulation,
            tool_name="simulation",
        )

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
        seed: int = 0xDEADBEEF,
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
            log_filename: Custom log filename (if None, uses asd.log in build_dir)
            seed: Random seed for reproducible simulations (default: 0xDEADBEEF)

        Returns:
            Return code (0 for success)
        """
        # Use default configuration if not specified
        configuration = configuration or "default"

        # Prepare simulation context with all required data
        sim_context = self._prepare_simulation(config, configuration, param_overrides, test_name)
        if sim_context is None:
            return 1

        # Set up build environment (directories, logs, paths)
        build_dir, log_file = self._setup_build_environment(
            toml_stem, configuration, sim_context.test_files, log_filename
        )

        # Print output file paths
        from rich.console import Console

        console = Console()
        console.print(f"[dim]Log file: {log_file.resolve()}[/dim]")
        if waves:
            vcd_file = build_dir / f"{config.top}.vcd"
            console.print(f"[dim]VCD file: {vcd_file.resolve()}[/dim]")

        # Execute simulation and check results
        # Pass whether custom log was used to determine if timestamped copy should be made
        return self._execute_simulation(
            sim_context,
            build_dir,
            log_file,
            simulator,
            gui,
            waves,
            parallel,
            seed,
            use_custom_log=log_filename is not None,
        )

    def _prepare_simulation(
        self,
        config: ModuleConfig,
        configuration: str,
        param_overrides: dict[str, Any] | None,
        test_name: str | None,
    ) -> SimulationContext | None:
        """Prepare simulation context by composing parameters and gathering files.

        Args:
            config: Module configuration
            configuration: Configuration name
            param_overrides: Parameter overrides from CLI
            test_name: Specific test to run

        Returns:
            SimulationContext if successful, None if preparation failed
        """
        # Compose parameters and defines for the configuration
        composed = self.loader.composer.compose(
            config, "simulation", configuration, param_overrides
        )

        # Prepare source files
        sources = self.source_manager.prepare_sources(config)
        if not sources:
            logger.error("No source files found")
            return None

        # Get include directories
        includes = self.source_manager.get_include_dirs(config)

        # Find test files (auto-discover sim_*.py or use specified tests)
        test_files = self._find_test_files(config, test_name)
        if not test_files:
            logger.error("No test files found")
            logger.error("Expected test files matching pattern: sim_*.py")
            if config.simulation and config.simulation.tests:
                logger.error("Or test files specified in TOML simulation.tests")
            return None

        return SimulationContext(
            config=config,
            configuration=configuration,
            parameters=composed["parameters"],
            defines=composed["defines"],
            sources=sources,
            includes=includes,
            test_files=test_files,
        )

    def _setup_build_environment(
        self,
        toml_stem: str,
        configuration: str,
        test_files: list[Path],
        log_filename: str | None,
    ) -> tuple[Path, Path]:
        """Set up build directories, log files, and PYTHONPATH.

        When log_filename is None, creates log at build_dir/asd.log which will
        be copied to a timestamped version after successful simulation.

        Args:
            toml_stem: TOML file stem for build directory naming
            configuration: Configuration name
            test_files: List of test files to copy
            log_filename: Custom log filename (optional, defaults to asd.log in build_dir)

        Returns:
            Tuple of (build_dir, log_file) paths
        """
        # Create build directory
        build_dir = Path(BUILD_DIR_NAME) / f"{toml_stem}-{configuration}"
        build_dir.mkdir(parents=True, exist_ok=True)

        # Set up logging - use custom filename or default to asd.log in build_dir
        if log_filename:
            log_file = Path(log_filename)
        else:
            log_file = build_dir / "asd.log"

        # Copy test files and supporting Python modules to build directory
        # This is necessary because cocotb's subprocess doesn't respect PYTHONPATH
        copied_dirs: set[Path] = set()
        for test_file in test_files:
            dest = build_dir / test_file.name
            shutil.copy2(test_file, dest)

            # Also copy other .py files from the same directory (supporting modules)
            test_dir = test_file.parent
            if test_dir not in copied_dirs:
                copied_dirs.add(test_dir)
                for py_file in test_dir.glob("*.py"):
                    if py_file != test_file:  # Don't copy twice
                        dest = build_dir / py_file.name
                        if not dest.exists():
                            shutil.copy2(py_file, dest)

        # Ensure asd package is in PYTHONPATH so tests can import asd.simulators.cocotb_utils
        asd_package_dir = Path(__file__).parent.parent.parent.resolve()
        current_pythonpath = os.environ.get("PYTHONPATH", "")
        if current_pythonpath:
            os.environ["PYTHONPATH"] = f"{asd_package_dir}:{current_pythonpath}"
        else:
            os.environ["PYTHONPATH"] = str(asd_package_dir)

        return build_dir, log_file

    def _execute_simulation(
        self,
        sim_context: SimulationContext,
        build_dir: Path,
        log_file: Path,
        simulator: str,
        gui: bool,
        waves: bool,
        parallel: int | None,
        seed: int,
        use_custom_log: bool = False,
    ) -> int:
        """Execute simulation build and test, then check results.

        After simulation completes, creates a timestamped copy of the log file
        if using the default log location (not custom log filename).

        Args:
            sim_context: Simulation context with all prepared data
            build_dir: Build directory path
            log_file: Log file path
            simulator: Simulator to use
            gui: Run with GUI
            waves: Generate waveforms
            parallel: Number of parallel tests
            seed: Random seed for reproducible simulations
            use_custom_log: Whether custom log filename was specified (no timestamp copy if True)

        Returns:
            Return code (0 for success)
        """
        from rich.console import Console

        console = Console()
        log_file_abs = log_file.resolve()

        # Get test variables from simulation config
        test_vars = None
        if sim_context.config.simulation and sim_context.config.simulation.vars:
            test_vars = sim_context.config.simulation.vars

        # Prepare test environment variables
        test_env = self._prepare_test_environment(
            sim_context.parameters,
            sim_context.defines,
            sim_context.configuration,
            seed,
            test_vars,
        )

        # Prepare test module list
        test_modules = [test_file.stem for test_file in sim_context.test_files]

        # Get cocotb runner
        runner = get_runner(simulator)

        try:
            # Redirect all output (build and test) to log file
            with _redirect_output(log_file):
                # Prepare build arguments for waveform tracing
                build_args = []
                if waves and simulator == "verilator":
                    build_args = ["--trace", "--trace-structs"]

                # Prepare parameters with quoted strings for Verilator
                formatted_params = self._format_parameters_for_simulator(
                    sim_context.parameters, simulator
                )

                # Build the design
                runner.build(
                    sources=[str(s) for s in sim_context.sources],
                    hdl_toplevel=sim_context.config.top,
                    includes=[str(i) for i in sim_context.includes],
                    defines=sim_context.defines,
                    parameters=formatted_params,
                    build_args=build_args,
                    build_dir=str(build_dir),
                    waves=waves,
                    always=True,  # Always rebuild
                )

                # Run tests
                test_args = []
                if waves and simulator == "verilator":
                    test_args = ["+trace"]

                runner.test(
                    hdl_toplevel=sim_context.config.top,
                    test_module=",".join(test_modules),
                    waves=waves,
                    gui=gui,
                    test_args=test_args,
                    extra_env=test_env,
                    build_dir=str(build_dir),
                )

            # Check log file for test failures
            result = self._check_simulation_results(log_file, log_file_abs, console)

            # Create timestamped copy if using default log location
            if not use_custom_log and log_file.exists():
                self._create_timestamped_log_copy(log_file, build_dir)

            return result

        except Exception as e:
            console.print(f"[red]✗ Simulation failed: {e}[/red]")
            console.print(f"[dim]Check log file for details: {log_file_abs}[/dim]")

            # Create timestamped copy even on failure if using default log location
            if not use_custom_log and log_file.exists():
                self._create_timestamped_log_copy(log_file, build_dir)

            return 1

    def _format_parameters_for_simulator(
        self, parameters: dict[str, Any], simulator: str
    ) -> dict[str, Any]:
        """Format parameters for the target simulator.

        Verilator requires string parameters to be quoted. This method wraps
        string values with quotes when targeting Verilator.

        Args:
            parameters: Original parameters dict
            simulator: Target simulator name

        Returns:
            Formatted parameters dict
        """
        if simulator != "verilator":
            return parameters

        formatted: dict[str, Any] = {}
        for name, value in parameters.items():
            if isinstance(value, str):
                # Verilator needs string parameters quoted
                formatted[name] = f'"{value}"'
            else:
                formatted[name] = value
        return formatted

    def _check_simulation_results(self, log_file: Path, log_file_abs: Path, console: Any) -> int:
        """Check simulation log file for failures and errors.

        Args:
            log_file: Log file path
            log_file_abs: Absolute log file path for display
            console: Rich console for output

        Returns:
            Return code (0 for success, 1 for failure)
        """
        if not log_file.exists():
            return 0

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
                console.print(f"[red]✗ Simulation failed: {fail_count} test(s) failed[/red]")
                console.print(f"[dim]Check log file for details: {log_file_abs}[/dim]")
                return 1

        return 0

    def _create_timestamped_log_copy(self, log_file: Path, build_dir: Path) -> None:
        """Create timestamped copy of log file in build directory.

        This preserves historical logs while keeping asd.log pointing to the latest run.

        Args:
            log_file: Source log file (should be build_dir/asd.log)
            build_dir: Build directory where timestamped copy will be created
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            timestamped_log = build_dir / f"asd-{timestamp}.log"
            shutil.copy2(log_file, timestamped_log)
            logger.debug(f"Created timestamped log copy: {timestamped_log}")
        except Exception as e:
            # Don't fail the simulation if log copy fails
            logger.warning(f"Failed to create timestamped log copy: {e}")

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
        self,
        parameters: dict[str, Any],
        defines: dict[str, Any],
        config_name: str,
        seed: int,
        test_vars: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Prepare environment variables for test execution.

        Encodes configuration data as JSON in environment variables that
        tests can access via cocotb_utils.py functions. Also sets COCOTB_RANDOM_SEED
        for cocotb's built-in random seed handling.

        Args:
            parameters: Composed parameters
            defines: Composed defines
            config_name: Configuration name
            seed: Random seed for reproducible simulations
            test_vars: Test variables from TOML [tools.simulation.vars]

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

        # Encode test variables as JSON
        if test_vars:
            env["COCOTB_TEST_VAR_VARS"] = json.dumps(test_vars)

        # Store configuration name
        env["COCOTB_TEST_VAR_CONFIG_NAME"] = json.dumps(config_name)

        # Set cocotb's native random seed environment variable
        # This automatically seeds Python's random module for reproducible tests
        env["COCOTB_RANDOM_SEED"] = str(seed)

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
        build_dir = Path(BUILD_DIR_NAME) / f"{toml_stem}-{configuration}"
        if build_dir.exists():
            shutil.rmtree(build_dir)
            logger.info(f"Cleaned {build_dir}")
