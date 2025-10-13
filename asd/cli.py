"""Command-line interface for ASD."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

    return ctx.obj["repo"]


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

    return ctx.obj["loader"]


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--root", type=Path, help="Repository root directory")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, root: Optional[Path]) -> None:
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
    console.print("  2. Or auto-generate from existing HDL: [cyan]asd auto --top src/module.sv[/cyan]")


@cli.command()
@click.option("--top", required=True, help="Top module file")
@click.option("--output", "-o", help="Output TOML file")
@click.option("--scan", is_flag=True, help="Scan for dependencies")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.pass_context
def auto(
    ctx: click.Context,
    top: str,
    output: Optional[str],
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


def parse_params(params: Tuple[str, ...]) -> Dict[str, Any]:
    """Parse parameter overrides from CLI.

    Args:
        params: Tuple of KEY=VALUE strings

    Returns:
        Dictionary of parameter overrides
    """
    overrides = {}
    for param in params:
        if "=" not in param:
            console.print(f"[yellow]Warning:[/yellow] Invalid parameter format: {param}")
            continue
        key, value = param.split("=", 1)
        # Try to parse as number
        try:
            overrides[key] = int(value)
        except ValueError:
            try:
                overrides[key] = float(value)
            except ValueError:
                # Keep as string
                overrides[key] = value
    return overrides


@cli.command()
@click.argument("toml_file", type=Path)
@click.option("--config", "-c", default="default", help="Configuration name")
@click.option("--param-set", "-p", help="Parameter set to use")
@click.option("--param", multiple=True, help="Override parameter (KEY=VALUE)")
@click.option("--simulator", "-s", default="verilator", help="Simulator")
@click.option("--test", "-t", help="Specific test to run")
@click.option("--gui", is_flag=True, help="Run with GUI")
@click.option("--waves", is_flag=True, default=True, help="Generate waveforms")
@click.option("--parallel", type=int, help="Run tests in parallel")
@click.option("--list-tests", is_flag=True, help="List available tests")
@click.pass_context
def sim(
    ctx: click.Context,
    toml_file: Path,
    config: str,
    param_set: Optional[str],
    param: Tuple[str, ...],
    simulator: str,
    test: Optional[str],
    gui: bool,
    waves: bool,
    parallel: Optional[int],
    list_tests: bool,
) -> None:
    """Run simulation."""
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

    # Show configuration if verbose
    if ctx.obj["verbose"]:
        console.print(f"[dim]Module: {module_config.name}[/dim]")
        console.print(f"[dim]Top: {module_config.top}[/dim]")
        console.print(f"[dim]Simulator: {simulator}[/dim]")
        if param_set:
            console.print(f"[dim]Parameter set: {param_set}[/dim]")

    # Create runner
    runner = SimulationRunner(repo, loader)

    # Run simulation
    result = runner.run(
        module_config,
        simulator=simulator,
        param_set=param_set,
        param_overrides=param_overrides,
        test_name=test,
        gui=gui,
        waves=waves,
        parallel=parallel,
    )

    if result == 0:
        console.print("[green]✓[/green] Simulation passed")
    else:
        console.print(f"[red]✗[/red] Simulation failed with code {result}")
        ctx.exit(result)


@cli.command()
@click.argument("toml_file", type=Path)
@click.option("--param-set", "-p", default="default", help="Parameter set to use (default: 'default', use 'all' for all sets)")
@click.option("--param", multiple=True, help="Override parameters (KEY=VALUE, can be specified multiple times)")
@click.option("--extra-args", help="Pass additional arguments to underlying linter (quoted string, e.g., \"-Wno-WIDTH -Wno-UNUSED\")")
@click.option("--verbose", "-v", is_flag=True, help="Print the full linter command being executed")
@click.pass_context
def lint(
    ctx: click.Context,
    toml_file: Path,
    param_set: str,
    param: Tuple[str, ...],
    extra_args: Optional[str],
    verbose: bool,
) -> None:
    """Lint HDL sources."""
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
    extra_args_list: List[str] = []
    if extra_args:
        import shlex
        extra_args_list = shlex.split(extra_args)

    # Check if linting all parameter sets
    if param_set == "all":
        console.print("[bold]Linting all parameter sets...[/bold]")
        # Get all parameter sets from config
        param_sets = list(module_config.parameter_sets.keys()) if module_config.parameter_sets else ["default"]

        all_passed = True
        for pset in param_sets:
            console.print(f"\n[cyan]→ Parameter set: {pset}[/cyan]")
            result = linter.lint(
                module_config,
                param_set=pset,
                param_overrides=param_overrides,
                extra_args=extra_args_list,
                verbose=verbose,
            )
            if result != 0:
                all_passed = False
                console.print(f"[red]✗[/red] Lint failed for parameter set '{pset}' with {result} issue(s)")
            else:
                console.print(f"[green]✓[/green] No lint issues found for parameter set '{pset}'")

        if not all_passed:
            ctx.exit(1)
    else:
        # Run linting for single parameter set
        console.print(f"[bold]Running lint checks with parameter set '{param_set}'...[/bold]")
        result = linter.lint(
            module_config,
            param_set=param_set,
            param_overrides=param_overrides,
            extra_args=extra_args_list,
            verbose=verbose,
        )

        if result == 0:
            console.print("[green]✓[/green] No lint issues found")
        else:
            console.print(f"[red]✗[/red] Lint failed with {result} issue(s)")
            ctx.exit(1)


@cli.command()
@click.option("--all", "clean_all", is_flag=True, help="Clean all artifacts")
@click.option("--simulator", help="Clean specific simulator")
def clean(clean_all: bool, simulator: Optional[str]) -> None:
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
        table.add_row("Language", config.language.value)

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
                    param.type.value,
                    param.description or "",
                )

            console.print(param_table)

        # Parameter Sets
        if config.parameter_sets:
            psets_table = Table(title="Parameter Sets")
            psets_table.add_column("Set Name", style="cyan")
            psets_table.add_column("Overrides")
            psets_table.add_column("Description")

            for set_name, pset in config.parameter_sets.items():
                overrides_str = ", ".join(f"{k}={v}" for k, v in pset.parameters.items())
                if not overrides_str:
                    overrides_str = "(uses all defaults)"
                psets_table.add_row(
                    set_name,
                    overrides_str,
                    pset.description or "",
                )

            console.print(psets_table)

        # Sources
        if config.sources.modules:
            console.print("\n[bold]Source Files:[/bold]")
            for src in config.sources.modules:
                console.print(f"  • {src}")

    elif format == "json":
        import json

        print(json.dumps(config.model_dump(), indent=2))

    elif format == "yaml":
        import yaml

        print(yaml.dump(config.model_dump(), default_flow_style=False))


def main() -> None:
    """Main entry point for ASD CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()