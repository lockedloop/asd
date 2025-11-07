"""Command-line interface for ASD."""

from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from .core.loader import TOMLLoader
from .core.repository import Repository
from .generators.toml_gen import TOMLGenerator
from .simulators.runner import SimulationRunner
from .tools.lint import Linter

console = Console()


def get_repository(ctx: click.Context) -> Repository:
    """Get or create repository instance.

    Args:
        ctx: Click context

    Returns:
        Repository instance

    Raises:
        FileNotFoundError: If .asd-root not found
    """
    if "repo" not in ctx.obj:
        root = ctx.obj.get("root_option")
        ctx.obj["repo"] = Repository(root)

        if ctx.obj.get("verbose"):
            console.print(f"[dim]Repository root: {ctx.obj['repo'].root}[/dim]")

    repo: Repository = ctx.obj["repo"]
    return repo


def get_loader(ctx: click.Context) -> TOMLLoader:
    """Get or create TOML loader instance.

    Args:
        ctx: Click context

    Returns:
        TOMLLoader instance
    """
    if "loader" not in ctx.obj:
        repo = get_repository(ctx)
        ctx.obj["loader"] = TOMLLoader(repo)

    loader: TOMLLoader = ctx.obj["loader"]
    return loader


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--root", type=Path, help="Repository root directory")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, root: Path | None) -> None:
    """ASD - Automated System Design tool for HDL projects."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["root_option"] = root

    # Don't initialize repository here - let commands do it when needed
    # This allows 'asd init' to run without requiring .asd-root to exist


@cli.command()
def init() -> None:
    """Initialize ASD repository in current directory."""
    marker_path = Path(".asd-root")

    # Check if already initialized
    if marker_path.exists():
        console.print("[yellow]Warning:[/yellow] .asd-root already exists")
        console.print("Repository is already initialized")
        return

    # Create .asd-root marker
    marker_path.touch()
    console.print("[green]✓[/green] Created .asd-root marker")

    console.print("\n[bold green]ASD repository initialized![/bold green]")
    console.print("\nNext steps:")
    console.print("  1. Create your HDL sources and TOML configuration")
    console.print(
        "  2. Or auto-generate from existing HDL: [cyan]asd auto --top src/module.sv[/cyan]"
    )


@cli.command()
@click.option("--top", required=True, help="Top module file")
@click.option("--output", "-o", help="Output TOML file")
@click.option("--scan", is_flag=True, help="Scan for dependencies")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.pass_context
def auto(
    ctx: click.Context,
    top: str,
    output: str | None,
    scan: bool,
    interactive: bool,
) -> None:
    """Automatically generate TOML from HDL sources (experimental)."""
    console.print("[yellow]⚠ Warning:[/yellow] This is an experimental feature")

    repo = get_repository(ctx)
    generator = TOMLGenerator(repo)

    top_path = Path(top)
    if not top_path.exists():
        console.print(f"[red]Error:[/red] File not found: {top}")
        ctx.exit(1)

    if interactive:
        # Interactive wizard
        console.print("[bold]ASD Configuration Generator[/bold]")
        config = generator.interactive_generate(top_path)
    else:
        # Automatic generation
        with console.status("[bold green]Analyzing HDL sources..."):
            config = generator.generate_from_top(top_path, scan_deps=scan)

    # Determine output file
    if not output:
        output = str(top_path.with_suffix(".toml"))

    # Write TOML
    generator.write_toml(config, Path(output))
    console.print(f"[green]✓[/green] Generated {output}")

    # Show summary
    if ctx.obj["verbose"]:
        console.print("\n[bold]Configuration Summary:[/bold]")
        console.print(f"  Module: {config.name}")
        console.print(f"  Top: {config.top}")
        console.print(f"  Sources: {len(config.sources.modules)} files")
        console.print(f"  Parameters: {len(config.parameters)}")


def _parse_param_value(value: str) -> int | float | bool | str:
    """Parse parameter value with type inference.

    Attempts to infer the most appropriate type for the value.
    Order: bool -> int -> float -> str

    Args:
        value: String value to parse

    Returns:
        Parsed value with inferred type
    """
    # Check for boolean values
    if value.lower() in ("true", "false"):
        return value.lower() == "true"

    # Try integer
    try:
        return int(value)
    except ValueError:
        pass

    # Try float
    try:
        return float(value)
    except ValueError:
        pass

    # Default to string
    return value


def parse_params(params: tuple[str, ...]) -> dict[str, Any]:
    """Parse parameter overrides from CLI.

    Supports automatic type inference for integers, floats, booleans, and strings.
    Boolean values should be specified as "true" or "false" (case-insensitive).

    Args:
        params: Tuple of KEY=VALUE strings

    Returns:
        Dictionary of parameter overrides with inferred types
    """
    overrides: dict[str, Any] = {}
    for param in params:
        if "=" not in param:
            console.print(f"[yellow]Warning:[/yellow] Invalid parameter format: {param}")
            continue
        key, value = param.split("=", 1)
        overrides[key] = _parse_param_value(value)
    return overrides


def expand_configurations(
    config_names: tuple[str, ...],
    module_config: Any,
    validator_func: Any,
    ctx: click.Context,
) -> list[str]:
    """Expand configuration names into a list of configurations to run.

    Handles the special "all" keyword by expanding it to all available
    configurations. Validates each configuration using the provided
    validator function.

    Args:
        config_names: Tuple of configuration names (may include "all")
        module_config: Module configuration object
        validator_func: Validation function that takes (module_config, config_name)
                       and returns (is_valid, error_message)
        ctx: Click context for error handling

    Returns:
        List of validated configuration names to run

    Raises:
        SystemExit: If validation fails for any configuration
    """
    configs_to_run: list[str] = []

    # Handle "all" keyword
    if "all" in config_names:
        # Validate that "all" is allowed
        is_valid, error_msg = validator_func(module_config, "all")
        if not is_valid:
            console.print(f"[red]Error:[/red] {error_msg}")
            ctx.exit(1)

        # Expand to all module configurations
        configs_to_run = (
            list(module_config.configurations.keys())
            if module_config.configurations
            else ["default"]
        )
    else:
        # Use specified configurations
        configs_to_run = list(config_names)

        # Validate each requested configuration
        for cfg in configs_to_run:
            is_valid, error_msg = validator_func(module_config, cfg)
            if not is_valid:
                console.print(f"[red]Error:[/red] {error_msg}")
                ctx.exit(1)

    return configs_to_run


@cli.command()
@click.argument("toml_file", type=Path)
@click.option(
    "--config",
    "-c",
    multiple=True,
    default=["default"],
    help="Configuration(s) to run (can specify multiple: -c default -c wide, or use -c all)",
)
@click.option("--param", multiple=True, help="Override parameter (KEY=VALUE)")
@click.option(
    "--simulator", "-s", default="verilator", help="Simulator to use (verilator, icarus, etc.)"
)
@click.option("--test", "-t", help="Specific test to run")
@click.option("--gui", is_flag=True, help="Run with GUI")
@click.option("--no-waves", is_flag=True, help="Disable waveform generation")
@click.option("--parallel", type=int, help="Run tests in parallel")
@click.option("--list-tests", is_flag=True, help="List available tests")
@click.option("--log", help="Custom log filename (default: asd-YYYY-MM-DD-HH-MM-SS.log)")
@click.option(
    "--seed",
    type=int,
    default=0xDEADBEEF,
    help="Random seed for simulation (default: 0xDEADBEEF)",
)
@click.pass_context
def sim(
    ctx: click.Context,
    toml_file: Path,
    config: tuple[str, ...],
    param: tuple[str, ...],
    simulator: str,
    test: str | None,
    gui: bool,
    no_waves: bool,
    parallel: int | None,
    list_tests: bool,
    log: str | None,
    seed: int,
) -> None:
    """Run simulation with cocotb.

    Examples:
        asd sim module.toml                    # Run with default configuration
        asd sim module.toml -c wide            # Run with wide configuration
        asd sim module.toml -c default -c wide # Run multiple configurations
        asd sim module.toml -c all             # Run all configurations
        asd sim module.toml --seed 12345       # Run with custom random seed
    """
    loader = get_loader(ctx)
    repo = get_repository(ctx)

    # Load configuration
    if not toml_file.exists():
        console.print(f"[red]Error:[/red] File not found: {toml_file}")
        ctx.exit(1)

    with console.status("[bold green]Loading configuration..."):
        module_config = loader.load(toml_file)

    # List tests if requested
    if list_tests:
        runner = SimulationRunner(repo, loader)
        tests = runner.list_tests(module_config)
        if tests:
            console.print("[bold]Available tests:[/bold]")
            for test_name in tests:
                console.print(f"  • {test_name}")
        else:
            console.print("No tests defined in configuration")
        return

    # Parse parameter overrides
    param_overrides = parse_params(param)

    # Get TOML file stem for build directory naming
    toml_stem = toml_file.stem

    # Create runner
    runner = SimulationRunner(repo, loader)

    # Waves enabled by default, disabled by --no-waves
    waves = not no_waves

    # Determine which configurations to run using shared helper
    configs_to_run = expand_configurations(
        config, module_config, runner.validate_configuration, ctx
    )

    # Show what we're running
    if len(configs_to_run) > 1:
        console.print(
            f"[bold]Running simulation for configurations: {', '.join(configs_to_run)}[/bold]"
        )

    # Run simulations
    all_passed = True
    for cfg in configs_to_run:
        if len(configs_to_run) > 1:
            console.print(f"\n[cyan]→ Configuration: {cfg}[/cyan]")
        elif ctx.obj["verbose"]:
            console.print(f"[dim]Module: {module_config.name}[/dim]")
            console.print(f"[dim]Top: {module_config.top}[/dim]")
            console.print(f"[dim]Simulator: {simulator}[/dim]")
            console.print(f"[dim]Configuration: {cfg}[/dim]")

        result = runner.run(
            module_config,
            toml_stem=toml_stem,
            simulator=simulator,
            configuration=cfg,
            param_overrides=param_overrides,
            test_name=test,
            gui=gui,
            waves=waves,
            parallel=parallel,
            log_filename=log,
            seed=seed,
        )

        if result != 0:
            all_passed = False
            if len(configs_to_run) > 1:
                console.print(f"[red]✗[/red] Simulation failed for configuration '{cfg}'")
            else:
                console.print(f"[red]✗[/red] Simulation failed with code {result}")
        else:
            if len(configs_to_run) > 1:
                console.print(f"[green]✓[/green] Simulation passed for configuration '{cfg}'")
            else:
                console.print("[green]✓[/green] Simulation passed")

    if not all_passed:
        ctx.exit(1)


@cli.command()
@click.argument("toml_file", type=Path)
@click.option(
    "--config",
    "-c",
    multiple=True,
    default=["default"],
    help="Configuration(s) to lint (can specify multiple: -c default -c wide, or use -c all)",
)
@click.option(
    "--param",
    multiple=True,
    help="Override parameters (KEY=VALUE, can be specified multiple times)",
)
@click.option(
    "--extra-args",
    help='Pass additional arguments to linter (e.g., "-Wno-WIDTH -Wno-UNUSED")',
)
@click.option("--verbose", "-v", is_flag=True, help="Print the full linter command being executed")
@click.pass_context
def lint(
    ctx: click.Context,
    toml_file: Path,
    config: tuple[str, ...],
    param: tuple[str, ...],
    extra_args: str | None,
    verbose: bool,
) -> None:
    """Lint HDL sources.

    Examples:
        asd lint module.toml                    # Lint with default configuration
        asd lint module.toml -c wide            # Lint with wide configuration
        asd lint module.toml -c default -c wide # Lint multiple configurations
        asd lint module.toml -c all             # Lint all configurations
    """
    loader = get_loader(ctx)
    repo = get_repository(ctx)

    # Load configuration
    if not toml_file.exists():
        console.print(f"[red]Error:[/red] File not found: {toml_file}")
        ctx.exit(1)

    with console.status("[bold green]Loading configuration..."):
        module_config = loader.load(toml_file)

    # Parse parameter overrides
    param_overrides = parse_params(param)

    # Create linter
    linter = Linter(repo, loader)

    # Parse extra arguments from quoted string
    extra_args_list: list[str] = []
    if extra_args:
        import shlex

        extra_args_list = shlex.split(extra_args)

    # Determine which configurations to run using shared helper
    configs_to_run = expand_configurations(
        config, module_config, linter.validate_configuration, ctx
    )

    # Show what we're running
    if len(configs_to_run) > 1:
        console.print(f"[bold]Linting configurations: {', '.join(configs_to_run)}[/bold]")

    # Run linting
    all_passed = True
    for cfg in configs_to_run:
        if len(configs_to_run) > 1:
            console.print(f"\n[cyan]→ Configuration: {cfg}[/cyan]")

        result = linter.lint(
            module_config,
            configuration=cfg,
            param_overrides=param_overrides,
            extra_args=extra_args_list,
            verbose=verbose,
        )

        if result != 0:
            all_passed = False
            if len(configs_to_run) > 1:
                console.print(
                    f"[red]✗[/red] Lint failed for configuration '{cfg}' with {result} issue(s)"
                )
            else:
                console.print(f"[red]✗[/red] Lint failed with {result} issue(s)")
        else:
            if len(configs_to_run) > 1:
                console.print(f"[green]✓[/green] No lint issues found for configuration '{cfg}'")
            else:
                console.print("[green]✓[/green] No lint issues found")

    if not all_passed:
        ctx.exit(1)


@cli.command()
@click.option("--all", "clean_all", is_flag=True, help="Clean all artifacts")
@click.option("--simulator", help="Clean specific simulator")
def clean(clean_all: bool, simulator: str | None) -> None:
    """Clean build artifacts."""
    build_dir = Path("build")

    if clean_all:
        if build_dir.exists():
            import shutil

            shutil.rmtree(build_dir)
            console.print("[green]✓[/green] Cleaned all build artifacts")
    elif simulator:
        sim_dir = build_dir / simulator
        if sim_dir.exists():
            import shutil

            shutil.rmtree(sim_dir)
            console.print(f"[green]✓[/green] Cleaned {simulator} artifacts")
    else:
        # List what would be cleaned
        if build_dir.exists():
            console.print("[bold]Build artifacts:[/bold]")
            for item in build_dir.iterdir():
                if item.is_dir():
                    console.print(f"  • {item.name}/")
        else:
            console.print("No build artifacts found")


@cli.command()
@click.argument("toml_file", type=Path)
@click.option("--format", "-f", type=click.Choice(["table", "json", "yaml"]), default="table")
@click.pass_context
def info(ctx: click.Context, toml_file: Path, format: str) -> None:
    """Show TOML file information."""
    loader = get_loader(ctx)

    if not toml_file.exists():
        console.print(f"[red]Error:[/red] File not found: {toml_file}")
        ctx.exit(1)

    # Load configuration
    config = loader.load(toml_file)

    if format == "table":
        # Module info table
        table = Table(title="Module Information")
        table.add_column("Property", style="cyan")
        table.add_column("Value")

        table.add_row("Name", config.name)
        table.add_row("Top", config.top)
        table.add_row("Type", config.type.value)

        console.print(table)

        # Parameters table
        if config.parameters:
            param_table = Table(title="Parameters")
            param_table.add_column("Name", style="cyan")
            param_table.add_column("Default")
            param_table.add_column("Type")
            param_table.add_column("Description")

            for name, param in config.parameters.items():
                param_table.add_row(
                    name,
                    str(param.default),
                    param.type.value if param.type else "auto",
                    param.description or "",
                )

            console.print(param_table)

        # Configurations
        if config.configurations:
            configs_table = Table(title="Configurations")
            configs_table.add_column("Name", style="cyan")
            configs_table.add_column("Parameters")
            configs_table.add_column("Defines")
            configs_table.add_column("Description")

            for config_name, cfg in config.configurations.items():
                params_str = ", ".join(f"{k}={v}" for k, v in cfg.parameters.items())
                if not params_str:
                    params_str = "(defaults)"
                defines_str = ", ".join(f"{k}={v}" for k, v in cfg.defines.items())
                if not defines_str:
                    defines_str = "(defaults)"

                configs_table.add_row(
                    config_name,
                    params_str,
                    defines_str,
                    cfg.description or "",
                )

            console.print(configs_table)

        # Sources
        if config.sources.modules:
            console.print("\n[bold]Source Files:[/bold]")
            for src in config.sources.modules:
                console.print(f"  • {src}")

    elif format == "json":
        import json

        print(json.dumps(config.model_dump(), indent=2))

    elif format == "yaml":
        import yaml  # type: ignore[import-untyped]

        print(yaml.dump(config.model_dump(), default_flow_style=False))


def main() -> None:
    """Main entry point for ASD CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
