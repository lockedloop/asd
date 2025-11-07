# ASD

ASD is the name of the tool, because I learned blind typing by playing
computer games, so by default I rest my left hand on the (W)ASD keys,
instead of SDF.
A TOML-based build system for HDL projects that provides a unified CLI
for all HDL development tasks, with Verilator as the default simulator.

## Features

- ⚡ **Verilator first** - Fast, open-source simulation and linting by default
- Relies on Cocotb heavily
- 🚀 **TOML-based configuration** - Single source of truth for module configuration
- 🛠️ **Unified CLI** - Single tool for all HDL tasks (simulate, lint, build)
- 🐍 **No pytest dependency** - Run simulations without pytest

## TODO

[] 🔍 **Smart discovery** - Automatically find and analyze HDL sources

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd asd

# Install with pip (recommended for development)
pip install -e .

# Or install with poetry
poetry install
```

## Quick Start

### 1. Initialize a new project

```bash
asd init --name my_project
```

This creates:

- Project directory structure
- Example TOML configuration
- Sample SystemVerilog module

### 2. Generate TOML from existing Verilog

```bash
asd generate --top src/my_module.sv --scan
```

The `--scan` flag automatically discovers dependencies.

### 3. Run simulation

```bash
asd sim my_module.toml
```

### 4. Lint your code

```bash
asd lint my_module.toml
```

## TOML Configuration Format

```toml
[asd]
version = "1.0"

[module]
name = "uart_controller"
top = "uart_top"
type = "rtl"

[module.sources]
packages = ["src/uart_pkg.sv"]
modules = ["src/uart_tx.sv", "src/uart_rx.sv", "src/uart_top.sv"]

[parameters]
CLK_FREQ = { default = 100000000, type = "integer" }
BAUD_RATE = { default = 115200, values = [9600, 115200, 921600] }
FIFO_DEPTH = { default = 16, range = [8, 128] }

[configurations.default]
# Uses all defaults

[configurations.test]
parameters = { CLK_FREQ = 1000000, FIFO_DEPTH = 8 }

[tools.simulation]
configurations = ["default", "test"]

[tools.lint]
configurations = ["default"]
```

## CLI Commands

### `asd init`

Initialize a new ASD project in the current directory.

```bash
asd init --name my_project
```

### `asd generate`

Generate TOML configuration from HDL sources.

```bash
# Basic generation
asd generate --top src/top_module.sv

# With dependency scanning
asd generate --top src/top_module.sv --scan

# Interactive mode
asd generate --top src/top_module.sv --interactive
```

### `asd sim`

Run simulation with specified configuration.

```bash
# Basic simulation
asd sim module.toml

# With parameter overrides
asd sim module.toml --param WIDTH=16 --param DEPTH=32

# Use specific parameter set
asd sim module.toml --param-set test

# Generate waveforms
asd sim module.toml --waves

# List available tests
asd sim module.toml --list-tests

# Run specific test
asd sim module.toml --test my_test
```

### `asd lint`

Run lint checks on HDL sources.

```bash
# Basic linting
asd lint module.toml

# With auto-fix (if supported)
asd lint module.toml --fix

# With parameter set
asd lint module.toml --param-set test
```

### `asd clean`

Clean build artifacts.

```bash
# Clean all artifacts
asd clean --all

# Clean specific simulator artifacts
asd clean --simulator verilator
```

### `asd info`

Display information about a TOML configuration.

```bash
# Table format (default)
asd info module.toml

# JSON format
asd info module.toml --format json

# YAML format
asd info module.toml --format yaml
```

## Parameter Composition

ASD's parameter composition system allows you to define parameters once
and reuse them across different contexts:

1. **Base defaults** - Defined in `[parameters]`
2. **Configurations** - Named collections of overrides in `[configurations]`
3. **Tool overrides** - Tool-specific values
4. **CLI overrides** - Command-line parameters

Example:

```toml
[parameters]
WIDTH = { default = 8 }

[configurations.test]
parameters = { WIDTH = 4 }

[tools.simulation]
configurations = ["test"]  # Tool supports test configuration
parameters = { WIDTH = 2 }  # Further override

# When running: asd sim module.toml -c test
# Final value: WIDTH = 2 (CLI selects config, tool overrides apply)
```

## Repository Detection

ASD automatically detects the repository root using (in order):

1. Explicit `--root` parameter
2. `ASD_ROOT` environment variable
3. `.asd-root` marker file
4. Git repository root (`.git`)
5. Current directory as fallback

All paths in TOML files are relative to the repository root.

## Verilator Integration

ASD uses Verilator as the default simulator:

- Fast compilation and simulation
- Built-in linting capabilities
- VCD waveform generation
- No license required

Verilator must be installed separately:

```bash
# macOS
brew install verilator

# Ubuntu/Debian
apt-get install verilator

# From source
git clone https://github.com/verilator/verilator
cd verilator
autoconf
./configure
make -j$(nproc)
sudo make install
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=asd

# Run specific test
pytest tests/unit/test_repository.py
```

### Code Quality

```bash
# Format code
black asd tests

# Lint
ruff check asd tests

# Type checking
mypy asd
```

## Architecture

```text
asd/
├── core/           # Core components
│   ├── repository.py   # Repository management
│   ├── config.py      # Pydantic models
│   └── loader.py      # TOML loading
├── generators/     # Code generation
│   └── toml_gen.py    # TOML generator
├── simulators/     # Simulator interfaces
│   ├── base.py        # Abstract base
│   ├── verilator.py   # Verilator impl
│   └── runner.py      # Simulation runner
├── tools/          # Tool implementations
│   └── lint.py        # Linting tool
├── utils/          # Utilities
│   └── verilog_parser.py  # HDL parsing
└── cli.py          # CLI interface
```

## License

MIT License - See [LICENSE](./LICENSE) file for details

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Support

For issues and questions:

- Open an issue on GitHub
- Check existing issues first
- Provide minimal reproducible examples
