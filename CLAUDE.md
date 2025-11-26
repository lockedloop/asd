# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ASD is a TOML-based build system for HDL (Hardware Description Language) projects. It
provides a unified CLI for Verilog/SystemVerilog development using Verilator as the
default simulator and cocotb for testing. The key innovation is a configuration
composition system that eliminates parameter repetition across tools and test
configurations.

## Development Commands

### Setup

```bash
make install              # Install dependencies and pre-commit hooks
poetry install --with dev # Install without make
```

### Testing

```bash
make test                 # Run all tests
make test-cov            # Run tests with coverage report
poetry run pytest tests/unit/test_specific.py  # Run specific test
```

### Code Quality

```bash
make format              # Auto-format with black, isort, ruff
make lint                # Run ruff, pydocstyle
make type-check          # Run mypy (strict mode)
make pre-commit          # Run all pre-commit hooks
```

### Pre-commit Notes

- All Python code must pass strict mypy type checking
- Pre-commit hooks run automatically on commit
- Line length: 100 characters
- Docstring style: Google format
- Type hints required for all functions

## Architecture Overview

### Configuration Composition System

The core innovation is **inline configuration syntax** where parameter/define values
can be specified directly as extra fields:

```toml
[parameters.WIDTH]
default = 8
wide = 16      # Automatically creates configurations.wide.parameters.WIDTH
narrow = 4     # Automatically creates configurations.narrow.parameters.WIDTH

[configurations.default]
# Uses all default values

[configurations.wide]
# Automatically gets parameters.WIDTH = 16 from inline definition

[tools.simulation]
configurations = ["default", "wide"]  # Tool supports these configs
```

This eliminates repetition - parameters defined once, composed everywhere.

### Configuration Resolution Order

When a tool runs with a configuration:

1. Start with parameter/define defaults
2. Apply inline configuration values from extra fields
3. Apply explicit `[configurations.X]` overrides
4. Apply tool-specific overrides
5. Apply CLI overrides (highest priority)

### Simulator Field Removed

**IMPORTANT**: The `simulator` field was removed from `SimulationConfig`. The
simulator is now specified ONLY via CLI:

```bash
asd sim module.toml --simulator verilator  # Default
asd sim module.toml --simulator modelsim
```

Never add `simulator` to TOML files or `SimulationConfig.__init__()`.

### Build Directory Pattern

Simulations create build directories with the pattern:

```text
build-{toml_stem}-{configuration}/
```

For example: `counter.toml` with config `wide` creates `build-counter-wide/`

## Core Components

### 1. Repository Management (`core/repository.py`)

Finds repository root using (in order):

1. Explicit `--root` CLI parameter
2. `ASD_ROOT` environment variable
3. `.asd/` directory (searches upward)
4. **Never** falls back to current directory - raises error if no root found

All paths in TOML files are relative to repository root.

The `.asd/` directory structure:

```bash
.asd/
├── libraries.toml    # Library manifest
└── libs/             # Cloned library repositories (gitignored)
    ├── mylib/
    └── otherlib/
```

### 2. Configuration Models (`core/config.py`)

Uses Pydantic v2 with strict typing. Key models:

- `Parameter` - Has `model_config = {"extra": "allow"}` for inline configs
- `Define` - Similar to Parameter, supports inline configs
- `Configuration` - Named collections of parameter/define values, supports inheritance
- `ToolConfig` - Base class with `configurations` field (list of config names)
- `SimulationConfig` - Tool config for simulation (NO simulator field)
- `ModuleConfig` - Top-level configuration model

### 3. TOML Loader (`core/loader.py`)

Handles composition and inheritance:

- `_extract_inline_configurations()` - Pulls config values from Parameter/Define extra fields
- `compose()` - Composes final parameters for a tool + configuration
- Detects circular dependencies with loading stack
- Validates configuration subsets (CLI configs must be in tool configs)

### 4. Cocotb Integration (`simulators/runner.py`)

Uses `cocotb.runner` API (NOT manual Verilator calls):

- Test files MUST be named `sim_*.py` (not `test_*.py` to avoid pytest)
- VCD waves enabled by default (disable with `--no-waves`)
- Configuration passed via `COCOTB_TEST_VAR_*` environment variables
- Utilities in `simulators/cocotb_utils.py` (NO clock/reset helpers, just config access)

Test specification in TOML supports two formats:

```toml
# Simple list format (auto-generates test names from filenames)
[tools.simulation]
tests = ["examples/counter/sim/sim_counter.py"]

# Dict format (explicit test configuration)
[tools.simulation.tests.smoke]
test_module = "examples/counter/sim/sim_counter.py"
timeout = 60
parameters = { WIDTH = 8 }
```

### 5. CLI Implementation (`cli.py`)

Key patterns:

- Context object stores `repo`, `loader` instances
- Use `ctx.exit(code)` not `raise click.Exit(code)`
- Multi-config support: `-c default -c wide` or `-c all`
- CLI loops over configs, runner executes ONE config at a time
- Parameter overrides: `--param WIDTH=16 --param DEPTH=32`

## Important Patterns

### Type Annotations

All code uses Python 3.12+ type hints with strict mypy:

```python
def compose(
    self,
    config: ModuleConfig,
    tool_name: str,
    configuration: str | None = None,
    param_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose configuration."""
    # Use explicit type annotations for all variables
    params: dict[str, Any] = {}
    # ...
```

### Configuration Validation

Tools can specify `configurations = ["all"]` to support all configs, or a specific list:

```python
# In validation logic
if "all" in tool_config.configurations:
    # Tool supports any configuration
    return (True, "")

# Otherwise, validate subset
if requested_config not in tool_config.configurations:
    return (False, f"Configuration '{requested_config}' not supported")
```

### Inline Configuration Extraction

Parameters and Defines use Pydantic `extra="allow"` to capture inline config values:

```python
def get_configuration_values(self) -> dict[str, Any]:
    """Get all extra fields as configuration values."""
    if hasattr(self, '__pydantic_extra__') and self.__pydantic_extra__:
        return dict(self.__pydantic_extra__)
    return {}
```

## Common Pitfalls

### 1. Simulator Field in TOML

- Do NOT add `simulator` field to `SimulationConfig`
- Do NOT write `simulator` to TOML files
- Simulator is CLI-only: `--simulator verilator`

### 2. Test File Naming

- Test files MUST be `sim_*.py` not `test_*.py`
- This avoids pytest auto-discovery conflicts
- Tests use cocotb decorators: `@cocotb.test()`

### 3. Circular Dependencies

- TOML loader tracks loading stack to detect cycles
- Always check `self._loading_stack` before loading dependencies

### 4. Path Resolution

- Always use `pathlib.Path`, never string concatenation
- Use `repository.resolve_path()` for TOML-relative paths
- Use `repository.relative_path()` when writing TOML

### 5. Type Safety

- All functions require return type annotations
- Pydantic models use v2 API (`model_config`, `field_validator`)
- Import from `typing`: `Any`, `Callable`, etc.

### 6. Library Management (`core/library.py`)

Manages external RTL library dependencies:

- `LibraryResolver` - Resolves `@libname/path` syntax to absolute paths
- `LibraryManager` - Manages library installation via git
- `DependencyResolver` - Handles transitive dependencies with cycle detection

Library manifest format (`.asd/libraries.toml`):

```toml
[asd]
version = "1.0"

[libraries.mylib]
git = "https://github.com/user/mylib.git"
tag = "v1.0.0"

[libraries.otherlib]
git = "git@github.com:user/otherlib.git"
branch = "main"
```

Using library sources in TOML files:

```toml
[module.sources]
modules = [
    "rtl/my_module.sv",           # Local source
    "@mylib/rtl/counter.sv",      # Library source
    "@otherlib/src/fifo.sv",      # Another library
]
```

CLI commands:

- `asd lib add <git-url> --tag v1.0.0` - Add a library
- `asd lib remove <name>` - Remove a library
- `asd lib install` - Install all libraries
- `asd lib update [name]` - Update libraries
- `asd lib list` - List libraries

## File Structure

```text
asd/
├── core/              # Core configuration and repository management
│   ├── config.py      # Pydantic models (Parameter, Define, Configuration)
│   ├── library.py     # Library management (LibraryManager, LibraryResolver)
│   ├── library_config.py # Library Pydantic models (LibrarySpec, LibraryManifest)
│   ├── loader.py      # TOML loading with composition
│   └── repository.py  # Repository root detection
├── simulators/        # Simulation execution
│   ├── runner.py      # Cocotb runner (uses cocotb.runner API)
│   ├── cocotb_utils.py # Test utilities (config access only)
│   ├── base.py        # Abstract simulator interface
│   └── verilator.py   # Verilator implementation
├── tools/             # Tool implementations
│   └── lint.py        # Verilator lint wrapper
├── generators/        # TOML generation
│   └── toml_gen.py    # Generate TOML from HDL sources
├── utils/             # Utilities
│   ├── sources.py     # Source file management (handles @libname/ paths)
│   ├── validation.py  # Configuration validation
│   └── verilog_parser.py # Basic Verilog parsing
└── cli.py             # Click-based CLI (includes lib command group)
```

## Testing Strategy

- Unit tests in `tests/unit/`
- Use pytest fixtures for repository/loader setup
- Mock file system operations with `tmp_path`
- Test configuration composition thoroughly
- Validate error messages and edge cases

## Working with Examples

- Development happens in `/Users/danilo/Git/asd`
- Examples are in `/Users/danilo/Git/asd-examples`
- **NEVER** run commands in `asd-examples` directory
- When showing example commands, just print them - user will run manually
- Example structure: `examples/{project}/rtl/{project}.toml`

## Pre-commit Hook Configuration

All hooks must pass before commit:

- black (formatting)
- isort (import sorting)
- ruff (linting)
- mypy (strict type checking)
- pydocstyle (docstring style)
- markdownlint (documentation)
