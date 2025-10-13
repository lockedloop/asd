"""Simulation runner for ASD."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.config import ModuleConfig
from ..core.loader import TOMLLoader
from ..core.repository import Repository
from ..utils.sources import SourceManager
from .verilator import VerilatorSimulator


class SimulationRunner:
    """Coordinate simulation execution."""

    def __init__(self, repository: Repository, loader: TOMLLoader) -> None:
        """Initialize simulation runner.

        Args:
            repository: Repository instance
            loader: TOML loader instance
        """
        self.repo = repository
        self.loader = loader
        self.source_manager = SourceManager(repository)
        self.simulators = {
            "verilator": VerilatorSimulator,
        }

    def run(
        self,
        config: ModuleConfig,
        simulator: str = "verilator",
        param_set: Optional[str] = None,
        param_overrides: Optional[Dict[str, Any]] = None,
        test_name: Optional[str] = None,
        gui: bool = False,
        waves: bool = True,
        parallel: Optional[int] = None,
        build_dir: Optional[Path] = None,
    ) -> int:
        """Run simulation with specified configuration.

        Args:
            config: Module configuration
            simulator: Simulator to use
            param_set: Parameter set name
            param_overrides: Parameter overrides from CLI
            test_name: Specific test to run
            gui: Run with GUI (simulator-specific)
            waves: Generate waveforms
            parallel: Number of parallel tests
            build_dir: Custom build directory

        Returns:
            Return code (0 for success)
        """
        # Get simulator class
        if simulator not in self.simulators:
            print(f"Error: Unknown simulator '{simulator}'")
            print(f"Available simulators: {', '.join(self.simulators.keys())}")
            return 1

        sim_class = self.simulators[simulator]
        sim = sim_class(build_dir=build_dir)

        # Check if simulator is available
        if not sim.is_available():
            print(f"Error: {simulator} is not available on this system")
            return 1

        # Compose parameters for simulation
        if param_set and config.simulation and config.simulation.parameter_set:
            # Override with specified parameter set
            sim_config = config.simulation.model_copy()
            sim_config.parameter_set = param_set
            temp_config = config.model_copy()
            temp_config.simulation = sim_config
            composed = self.loader.composer.compose(
                temp_config, "simulation", param_overrides
            )
        else:
            composed = self.loader.composer.compose(
                config, "simulation", param_overrides
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

        # Compile
        from rich.console import Console
        console = Console()

        with console.status(f"[bold green]Compiling with {simulator}...[/bold green]"):
            compile_args = []
            if config.simulation and hasattr(config.simulation, simulator):
                sim_config = getattr(config.simulation, simulator)
                if sim_config:
                    compile_args = sim_config.compile_args

            ret = sim.compile(
                sources=sources,
                parameters=parameters,
                defines=defines,
                top_module=config.top,
                includes=includes,
                compile_args=compile_args,
            )

        if ret != 0:
            return ret

        # Elaborate (if needed)
        ret = sim.elaborate(config.top, parameters)
        if ret != 0:
            return ret

        # Determine test module
        test_module = None
        if test_name and config.simulation and config.simulation.tests:
            test = config.simulation.tests.get(test_name)
            if test:
                test_module = test.test_module
                # Apply test-specific parameters
                parameters.update(test.parameters)
        elif config.simulation and config.simulation.tests:
            # Use first test if none specified
            first_test = next(iter(config.simulation.tests.values()), None)
            if first_test:
                test_module = first_test.test_module

        # Run simulation
        print(f"Running simulation...")
        sim_args = []
        if config.simulation and hasattr(config.simulation, simulator):
            sim_config = getattr(config.simulation, simulator)
            if sim_config:
                sim_args = sim_config.sim_args

        ret = sim.simulate(
            top_module=config.top,
            test_module=test_module,
            waves=waves,
            sim_args=sim_args,
        )

        return ret

    def list_tests(self, config: ModuleConfig) -> List[str]:
        """List available tests.

        Args:
            config: Module configuration

        Returns:
            List of test names
        """
        if config.simulation and config.simulation.tests:
            return list(config.simulation.tests.keys())
        return []

    def clean(self, simulator: str = "verilator") -> None:
        """Clean simulation artifacts.

        Args:
            simulator: Simulator to clean
        """
        if simulator in self.simulators:
            sim = self.simulators[simulator]()
            sim.clean()
            print(f"Cleaned {simulator} build artifacts")