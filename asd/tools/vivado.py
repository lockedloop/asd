"""Vivado OOC synthesis tool for HDL sources."""

import shutil
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console

from ..core.config import ModuleConfig, SynthesisConfig
from ..core.loader import TOMLLoader
from ..core.repository import Repository
from ..utils.config_validation import validate_tool_configuration
from ..utils.logging import get_logger
from ..utils.sources import SourceManager
from .vivado_tcl import generate_ooc_tcl

logger = get_logger()

BUILD_DIR_PREFIX = "build"


class VivadoSynthesizer:
    """Vivado OOC synthesis tool."""

    def __init__(self, repository: Repository, loader: TOMLLoader) -> None:
        """Initialize synthesizer.

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
        """Validate that requested configuration is allowed by synthesis tool.

        Args:
            config: Module configuration
            requested_config: Configuration name requested via CLI

        Returns:
            Tuple of (is_valid, error_message)
        """
        return validate_tool_configuration(
            config=config,
            requested_config=requested_config,
            tool_config=config.synthesis,
            tool_name="synthesis",
        )

    def is_available(self) -> bool:
        """Check if Vivado is available on the system.

        Returns:
            True if vivado command is found in PATH
        """
        return shutil.which("vivado") is not None

    def get_version(self) -> str | None:
        """Get Vivado version string.

        Returns:
            Version string or None if not available
        """
        if not self.is_available():
            return None
        try:
            result = subprocess.run(
                ["vivado", "-version"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            # Parse first line: "Vivado v2024.1 (64-bit)"
            for line in result.stdout.splitlines():
                if "Vivado" in line:
                    return line.strip()
            return None
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return None

    def synthesize(
        self,
        config: ModuleConfig,
        toml_stem: str,
        configuration: str | None = None,
        param_overrides: dict[str, Any] | None = None,
        part_override: str | None = None,
        tcl_only: bool = False,
    ) -> int:
        """Run OOC synthesis on HDL sources.

        Args:
            config: Module configuration
            toml_stem: TOML file stem (for build directory naming)
            configuration: Configuration to use
            param_overrides: Parameter overrides from CLI
            part_override: Override FPGA part number
            tcl_only: If True, generate TCL but don't run Vivado

        Returns:
            Return code (0 for success)
        """
        console = Console()
        configuration = configuration or "default"

        # Get synthesis config with defaults
        synth_config = config.synthesis or SynthesisConfig()

        # Create build directory
        build_dir = Path(BUILD_DIR_PREFIX) / f"{toml_stem}-{configuration}"
        build_dir.mkdir(parents=True, exist_ok=True)
        reports_dir = build_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Compose parameters and defines
        composed = self.loader.composer.compose(config, "synthesis", configuration, param_overrides)
        parameters = composed["parameters"]
        defines = composed["defines"]

        # Prepare source files
        sources = self.source_manager.prepare_sources(config)
        if not sources:
            logger.error("No source files found")
            return 1

        # Separate packages from modules
        packages = [Path(p) for p in config.sources.packages]
        modules = [Path(m) for m in config.sources.modules]

        # Resolve to absolute paths
        packages = [self.repo.resolve_path(p) for p in packages]
        modules = [self.repo.resolve_path(m) for m in modules]

        # Determine part
        part = part_override or synth_config.part

        # Get OOC config
        ooc_config = synth_config.ooc
        directives = synth_config.directives

        # Generate label for output files
        label = f"{config.name}_{configuration}"

        # Generate TCL script
        tcl_content = generate_ooc_tcl(
            module_name=config.name,
            top=config.top,
            configuration=configuration,
            part=part,
            sources=modules,
            packages=packages,
            parameters=parameters,
            defines=defines,
            clocks=ooc_config.clocks,
            clock_uncertainty=ooc_config.clock_uncertainty,
            synth_directive=directives.synthesis,
            place_directive=directives.placement,
            route_directive=directives.route,
            build_dir=build_dir.resolve(),
            label=label,
        )

        # Write TCL script
        tcl_file = build_dir / f"{label}.tcl"
        tcl_file.write_text(tcl_content)
        console.print(f"[dim]TCL script: {tcl_file.resolve()}[/dim]")

        if tcl_only:
            console.print(f"[green]TCL generated:[/green] {tcl_file}")
            return 0

        # Check Vivado availability
        if not self.is_available():
            logger.error("Vivado is not available on this system")
            console.print("[red]Error:[/red] Vivado not found in PATH")
            return 1

        version = self.get_version()
        if version:
            console.print(f"[dim]{version}[/dim]")

        # Run Vivado in batch mode
        console.print(f"[bold]Running synthesis for {config.name} ({configuration})...[/bold]")
        console.print(f"[dim]Part: {part}[/dim]")

        log_file = build_dir / f"{label}.log"

        try:
            with open(log_file, "w") as log_fh:
                result = subprocess.run(
                    [
                        "vivado",
                        "-notrace",
                        "-mode",
                        "batch",
                        "-source",
                        str(tcl_file.resolve()),
                    ],
                    cwd=build_dir,
                    stdout=log_fh,
                    stderr=subprocess.STDOUT,
                    timeout=3600,  # 1 hour timeout
                )

            if result.returncode != 0:
                console.print(f"[red]Synthesis failed[/red] (exit code {result.returncode})")
                console.print(f"[dim]Log file: {log_file.resolve()}[/dim]")
                return result.returncode

            console.print("[green]Synthesis complete[/green]")
            console.print(f"[dim]Checkpoint: {build_dir / f'{label}_ROUTED.dcp'}[/dim]")
            console.print(f"[dim]Log file: {log_file.resolve()}[/dim]")
            return 0

        except subprocess.TimeoutExpired:
            console.print("[red]Error:[/red] Synthesis timed out after 1 hour")
            return 1
        except subprocess.SubprocessError as e:
            console.print(f"[red]Error:[/red] Failed to run Vivado: {e}")
            return 1
