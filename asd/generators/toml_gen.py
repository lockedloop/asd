"""TOML generation from HDL sources."""

from pathlib import Path
from typing import Any

import tomli_w
from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt

from ..core.config import (
    Configuration,
    LintConfig,
    ModuleConfig,
    ModuleSources,
    ModuleType,
    Parameter,
    ParameterType,
    SimulationConfig,
    TestConfig,
)
from ..core.repository import Repository
from ..utils.verilog_parser import VerilogParser

console = Console()


class TOMLGenerator:
    """Generate TOML files from HDL sources."""

    def __init__(self, repository: Repository) -> None:
        """Initialize generator with repository.

        Args:
            repository: Repository instance
        """
        self.repo = repository
        self.parser = VerilogParser()

    def generate_from_top(self, top_file: Path, scan_deps: bool = True) -> ModuleConfig:
        """Generate TOML from top-level module.

        Args:
            top_file: Path to top module file
            scan_deps: Whether to scan for dependencies

        Returns:
            Generated module configuration
        """
        top_path = self.repo.resolve_path(top_file)

        # Parse top module
        module = self.parser.parse_file(top_path)

        # Find sources
        sources = self._find_sources(top_path, module, scan_deps)

        # Convert parameters
        parameters = {}
        for param in module.parameters:
            param_type = self._determine_param_type(param.type)
            parameters[param.name] = Parameter(
                default=self.parser.parse_default_value(param.default),
                type=param_type,
            )

        # Build configuration
        config = ModuleConfig(
            name=module.name,
            top=module.name,
            type=ModuleType.RTL,
            sources=ModuleSources(
                modules=[str(self.repo.relative_path(s)) for s in sources],
                includes=[str(self.repo.relative_path(Path(inc))) for inc in module.includes],
            ),
            parameters=parameters,
            configurations={
                "default": Configuration(name="default", parameters={}, defines={}),
            },
            simulation=SimulationConfig(
                configurations=["default"],
            ),
            lint=LintConfig(
                tool="verilator",
                configurations=["default"],
            ),
        )

        return config

    def _determine_param_type(self, verilog_type: str) -> ParameterType:
        """Convert Verilog type to parameter type.

        Args:
            verilog_type: Verilog parameter type

        Returns:
            ASD parameter type
        """
        if verilog_type == "string":
            return ParameterType.STRING
        elif verilog_type == "boolean":
            return ParameterType.BOOLEAN
        elif verilog_type == "real":
            return ParameterType.REAL
        else:
            return ParameterType.INTEGER

    def _find_sources(self, top_file: Path, module: Any, scan_deps: bool) -> list[Path]:
        """Find all source files.

        Args:
            top_file: Top module file
            module: Parsed module
            scan_deps: Whether to scan for dependencies

        Returns:
            List of source file paths
        """
        sources = [top_file]

        if not scan_deps:
            return sources

        # Search directories
        search_dirs = [
            top_file.parent,
            top_file.parent.parent / "rtl",
            top_file.parent.parent / "src",
            self.repo.root / "src",
            self.repo.root / "rtl",
        ]

        visited: set[str] = set()
        to_visit = module.instances.copy()

        # Show progress if we have dependencies to scan
        if to_visit:
            console.print(f"[dim]Scanning {len(to_visit)} dependencies...[/dim]")

        while to_visit:
            inst = to_visit.pop(0)
            if inst in visited:
                continue
            visited.add(inst)

            # Try to find module file
            found = False
            for dir_path in search_dirs:
                if not dir_path.exists():
                    continue

                possible_files = [
                    dir_path / f"{inst}.sv",
                    dir_path / f"{inst}.v",
                    dir_path / f"{inst}.svh",
                    dir_path / f"{inst}.vh",
                ]

                for pf in possible_files:
                    if pf.exists() and pf not in sources:
                        sources.append(pf)
                        found = True

                        # Parse for more dependencies
                        try:
                            sub_module = self.parser.parse_file(pf)
                            to_visit.extend(sub_module.instances)
                        except Exception:  # nosec B110
                            # Not a module file, might be package or include
                            pass
                        break

                if found:
                    break

        return sources

    def write_toml(self, config: ModuleConfig, output: Path) -> None:
        """Write configuration to TOML file.

        Args:
            config: Module configuration
            output: Output file path
        """
        output = self.repo.resolve_path(output)

        # Build TOML structure
        data: dict[str, Any] = {
            "asd": {
                "version": "1.0",
                "generated": True,
            },
            "module": {
                "name": config.name,
                "top": config.top,
                "type": config.type.value,
            },
        }

        # Add sources if present
        if config.sources.modules or config.sources.packages:
            data["module"]["sources"] = {}
            if config.sources.packages:
                data["module"]["sources"]["packages"] = config.sources.packages
            if config.sources.modules:
                data["module"]["sources"]["modules"] = config.sources.modules
            if config.sources.includes:
                data["module"]["sources"]["includes"] = config.sources.includes

        # Add parameters
        if config.parameters:
            data["parameters"] = {}
            for name, param in config.parameters.items():
                param_dict = {"default": param.default}
                if param.type and param.type != ParameterType.INTEGER:
                    param_dict["type"] = param.type.value
                if param.description:
                    param_dict["description"] = param.description
                if param.range:
                    param_dict["range"] = list(param.range)
                if param.values:
                    param_dict["values"] = param.values
                data["parameters"][name] = param_dict

        # Add configurations
        if config.configurations:
            data["configurations"] = {}
            for name, cfg in config.configurations.items():
                cfg_data: dict[str, Any] = {}
                if cfg.parameters:
                    cfg_data["parameters"] = cfg.parameters
                if cfg.defines:
                    cfg_data["defines"] = cfg.defines
                if cfg.inherit:
                    cfg_data["inherit"] = cfg.inherit
                if cfg.description:
                    cfg_data["description"] = cfg.description
                data["configurations"][name] = cfg_data if cfg_data else {}

        # Add tools
        data["tools"] = {}

        if config.simulation:
            data["tools"]["simulation"] = {}
            if config.simulation.configurations:
                data["tools"]["simulation"]["configurations"] = config.simulation.configurations

        if config.lint:
            data["tools"]["lint"] = {}
            if config.lint.configurations:
                data["tools"]["lint"]["configurations"] = config.lint.configurations

        # Write file
        with open(output, "wb") as f:
            tomli_w.dump(data, f)

    def interactive_generate(self, top_file: Path) -> ModuleConfig:
        """Interactive TOML generation with prompts.

        Args:
            top_file: Top module file

        Returns:
            Generated module configuration
        """
        console.print("\n[bold]ASD Configuration Wizard[/bold]\n")

        # Start with automatic generation
        config = self.generate_from_top(top_file, scan_deps=True)

        # Ask for module name
        config.name = Prompt.ask(
            "Module name",
            default=config.name,
        )

        # Ask for description
        description = Prompt.ask(
            "Module description (optional)",
            default="",
        )
        if description:
            config.description = description

        # Ask about parameter sets
        if Confirm.ask("Add parameter sets for different configurations?", default=False):
            # Add test parameter set
            if Confirm.ask("Add 'test' parameter set with smaller values?", default=True):
                test_params = {}
                for param_name, param in config.parameters.items():
                    if param.type == ParameterType.INTEGER:
                        current = param.default
                        new_val = IntPrompt.ask(
                            f"  {param_name} (test value)",
                            default=min(current, 8) if isinstance(current, int) else 8,
                        )
                        if new_val != current:
                            test_params[param_name] = new_val

                if test_params:
                    config.configurations["test"] = Configuration(
                        name="test",
                        parameters=test_params,
                        defines={},
                    )

        # Ask about simulation tests
        if Confirm.ask("Add simulation test configuration?", default=False):
            test_module = Prompt.ask(
                "Test module name (Python module)",
                default="test_module",
            )

            if not config.simulation:
                config.simulation = SimulationConfig()

            config.simulation.tests = {
                "default": TestConfig(
                    test_module=test_module,
                    timeout=60,
                )
            }

        # Ask about synthesis
        if Confirm.ask("Add synthesis configuration?", default=False):
            from ..core.config import SynthesisConfig

            config.synthesis = SynthesisConfig(
                tool="vivado",
                configurations=["default"],
            )

            part = Prompt.ask("FPGA part (optional)", default="")
            if part:
                config.synthesis.part = part

        console.print("\n[green]Configuration complete![/green]")

        return config
