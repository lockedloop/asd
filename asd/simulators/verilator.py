"""Verilator simulator implementation."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..utils.logging import get_logger
from .base import SimulatorBase

logger = get_logger()


class VerilatorSimulator(SimulatorBase):
    """Verilator simulator for both linting and simulation."""

    def __init__(self, build_dir: Path | None = None) -> None:
        """Initialize Verilator simulator.

        Args:
            build_dir: Build directory path
        """
        super().__init__("verilator", build_dir)
        self.exe_name: str | None = None
        self.verilator_path = self._find_verilator()

    def _find_verilator(self) -> Path | None:
        """Find Verilator executable.

        Returns:
            Path to verilator executable or None
        """
        # Check if verilator is in PATH
        verilator = shutil.which("verilator")
        if verilator:
            return Path(verilator)

        # Check common installation locations
        common_paths = [
            Path("/usr/local/bin/verilator"),
            Path("/usr/bin/verilator"),
            Path("/opt/homebrew/bin/verilator"),
            Path.home() / ".local/bin/verilator",
        ]

        for path in common_paths:
            if path.exists():
                return path

        return None

    def is_available(self) -> bool:
        """Check if Verilator is available.

        Returns:
            True if Verilator is found
        """
        return self.verilator_path is not None

    def compile(
        self,
        sources: list[Path],
        parameters: dict[str, Any],
        defines: dict[str, Any],
        lint_only: bool = False,
        top_module: str | None = None,
        includes: list[Path] | None = None,
        verbose: bool = False,
        **kwargs: Any,
    ) -> int:
        """Compile with Verilator.

        Args:
            sources: List of source files
            parameters: Module parameters
            defines: Preprocessor defines
            lint_only: Only perform linting
            top_module: Top module name
            includes: Include directories
            verbose: Print the full command being executed
            **kwargs: Additional Verilator options

        Returns:
            Return code
        """
        if not self.verilator_path:
            logger.error("Verilator not found")
            return 1

        cmd = [str(self.verilator_path)]

        if lint_only:
            cmd.extend(["--lint-only", "-Wall", "-Wno-PROCASSINIT"])
        else:
            # Simulation mode
            cmd.extend(
                [
                    "--cc",  # C++ output
                    "--exe",  # Create executable
                    "--build",  # Build immediately
                    "--timing",  # Timing support
                    "--trace-vcd",  # VCD traces
                    "-j",
                    "0",  # Use all cores
                    "--Mdir",
                    str(self.build_dir),
                ]
            )

            # Add main.cpp for simulation
            if top_module:
                main_cpp = self._generate_main_cpp(top_module)
                main_file = self.build_dir / "main.cpp"
                main_file.write_text(main_cpp)
                cmd.append(str(main_file))

        # Add include directories
        if includes:
            for inc_dir in includes:
                cmd.extend(["-I", str(inc_dir)])

        # Add parameters
        for name, value in parameters.items():
            if isinstance(value, str):
                # String parameters need quotes for Verilator
                cmd.append(f'-G{name}="{value}"')
            else:
                cmd.append(f"-G{name}={value}")

        # Add defines
        for name, value in defines.items():
            if value is True:
                cmd.append(f"-D{name}")
            else:
                cmd.append(f"-D{name}={value}")

        # Add sources
        cmd.extend(str(s) for s in sources)

        # Add top module
        if top_module:
            cmd.extend(["--top-module", top_module])
            self.exe_name = f"V{top_module}"

        # Add extra compile args
        cmd.extend(kwargs.get("compile_args", []))

        # Print command if verbose
        if verbose:
            logger.info("\n[Verilator Command]")
            logger.info(" ".join(cmd))
            logger.info("")

        # Execute
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.build_dir.parent,
            )

            if result.returncode != 0:
                logger.error("Verilator compilation failed:")
                if result.stderr:
                    logger.error(result.stderr)
                if result.stdout:
                    logger.error(result.stdout)

            return result.returncode

        except subprocess.TimeoutExpired:
            logger.error("Verilator compilation timed out")
            return 1
        except Exception as e:
            logger.error(f"Error running Verilator: {e}")
            return 1

    def elaborate(self, top_module: str, parameters: dict[str, Any], **kwargs: Any) -> int:
        """Verilator combines compilation and elaboration.

        Args:
            top_module: Top module name
            parameters: Module parameters
            **kwargs: Additional options

        Returns:
            0 (no separate elaboration needed)
        """
        # Verilator doesn't have a separate elaboration step
        return 0

    def simulate(
        self,
        top_module: str,
        test_module: str | None = None,
        timeout: int = 3600,
        waves: bool = True,
        **kwargs: Any,
    ) -> int:
        """Run Verilator simulation.

        Args:
            top_module: Top module name
            test_module: Cocotb test module
            timeout: Simulation timeout in seconds
            waves: Generate waveforms
            **kwargs: Additional options

        Returns:
            Return code
        """
        exe_path = self.build_dir / (self.exe_name or f"V{top_module}")

        if not exe_path.exists():
            logger.error(f"Executable {exe_path} not found. Compile first.")
            return 1

        cmd = [str(exe_path)]

        # Add runtime arguments
        if waves:
            cmd.append("+trace")

        # Add simulation args
        cmd.extend(kwargs.get("sim_args", []))

        # Set up environment for cocotb if test module specified
        env = os.environ.copy()
        if test_module:
            env["MODULE"] = test_module
            env["TOPLEVEL"] = top_module
            env["TOPLEVEL_LANG"] = "verilog"

            # Try to find cocotb VPI library
            try:
                import cocotb

                cocotb_dir = Path(cocotb.__file__).parent
                # Look for Verilator VPI library
                vpi_patterns = [
                    "libs/libcocotbvpi_verilator.so",
                    "libs/libcocotbvpi_verilator.dylib",
                    "libs/libcocotbvpi_verilator.dll",
                ]
                for pattern in vpi_patterns:
                    vpi_lib = cocotb_dir / pattern
                    if vpi_lib.exists():
                        env["COCOTB_VPI_MODULE"] = str(vpi_lib)
                        break
            except ImportError:
                logger.warning("cocotb not found, test module will not be loaded")

        # Run simulation
        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.build_dir,
            )

            if result.returncode != 0:
                logger.error("Simulation failed:")
                if result.stderr:
                    logger.error(result.stderr)
                if result.stdout:
                    logger.error(result.stdout)
            else:
                if result.stdout:
                    logger.info(result.stdout)

            return result.returncode

        except subprocess.TimeoutExpired:
            logger.error(f"Simulation timed out after {timeout} seconds")
            return 1
        except Exception as e:
            logger.error(f"Error running simulation: {e}")
            return 1

    def _generate_main_cpp(self, top_module: str) -> str:
        """Generate C++ main file for simulation.

        Args:
            top_module: Top module name

        Returns:
            C++ source code
        """
        return f"""#include "V{top_module}.h"
#include "verilated.h"
#include "verilated_vcd_c.h"
#include <iostream>
#include <memory>
#include <signal.h>

// Global flag for graceful shutdown
volatile bool shutdown_requested = false;

void signal_handler(int signum) {{
    shutdown_requested = true;
}}

int main(int argc, char** argv) {{
    // Setup signal handlers for graceful shutdown
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    // Initialize Verilator
    Verilated::commandArgs(argc, argv);
    Verilated::debug(0);
    Verilated::randReset(2);

    // Create top module
    auto top = std::make_unique<V{top_module}>();

    // VCD tracing setup
    std::unique_ptr<VerilatedVcdC> tfp;
    if (Verilated::commandArgsPlusMatch("+trace")) {{
        Verilated::traceEverOn(true);
        tfp = std::make_unique<VerilatedVcdC>();
        top->trace(tfp.get(), 99);
        tfp->open("{top_module}.vcd");
        std::cout << "VCD trace enabled: {top_module}.vcd" << std::endl;
    }}

    // Initialize simulation
    vluint64_t sim_time = 0;
    vluint64_t max_sim_time = 1000000;

    // Parse command line for max simulation time
    for (int i = 1; i < argc; i++) {{
        if (std::string(argv[i]).find("+max-sim-time=") == 0) {{
            max_sim_time = std::stoull(std::string(argv[i]).substr(14));
        }}
    }}

    std::cout << "Starting simulation of {top_module}" << std::endl;

    // Main simulation loop
    while (!Verilated::gotFinish() && !shutdown_requested && sim_time < max_sim_time) {{
        // Evaluate model
        top->eval();

        // Dump waveforms
        if (tfp) {{
            tfp->dump(sim_time);
        }}

        sim_time++;

        // Print progress periodically
        if (sim_time % 100000 == 0) {{
            std::cout << "Simulation time: " << sim_time << std::endl;
        }}
    }}

    std::cout << "Simulation ended at time " << sim_time << std::endl;

    // Cleanup
    if (tfp) {{
        tfp->close();
    }}

    // Final model cleanup
    top->final();

    // Check if we ended due to timeout
    if (sim_time >= max_sim_time) {{
        std::cerr << "Warning: Simulation reached maximum time limit" << std::endl;
        return 2;  // Indicate timeout
    }}

    return shutdown_requested ? 1 : 0;
}}"""

    def lint(
        self,
        sources: list[Path],
        parameters: dict[str, Any],
        defines: dict[str, Any],
        includes: list[Path] | None = None,
        extra_args: list[str] | None = None,
        verbose: bool = False,
        **kwargs: Any,
    ) -> int:
        """Run Verilator in lint mode.

        Args:
            sources: Source files to lint
            parameters: Module parameters
            defines: Preprocessor defines
            includes: Include directories
            extra_args: Additional arguments to pass to Verilator
            verbose: Print the full command being executed
            **kwargs: Additional options

        Returns:
            Return code
        """
        # Merge extra_args with any existing compile_args in kwargs
        compile_args = kwargs.get("compile_args", [])
        if extra_args:
            compile_args = list(compile_args) + list(extra_args)
        kwargs["compile_args"] = compile_args

        return self.compile(
            sources=sources,
            parameters=parameters,
            defines=defines,
            lint_only=True,
            includes=includes,
            verbose=verbose,
            **kwargs,
        )
