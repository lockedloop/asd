# ASD

[![CI](https://github.com/lockedloop/asd/workflows/CI/badge.svg)](https://github.com/lockedloop/asd/actions)

A TOML-based build system for HDL projects that provides a unified CLI
for all hardware development tasks. Features Verilator as the default simulator,
cocotb for testing, and a configuration composition system that
eliminates parameter repetition.

> **Why "ASD"?** The name comes from the WASD keys - the default home position
> for gamers. Having learned touch typing through gaming, my left hand naturally
> rests on WASD instead of the traditional ASDF. It's just three letters, not an
> acronym.
>
> This project was created for personal use as a way to quickly bootstrap hardware
> development on any machine. It comes without any guarantees and is provided as-is.

## Examples

Check out [**asd-examples**](https://github.com/lockedloop/asd-examples) for working examples.

## Features

### 🚀 Configuration Management

- **TOML-based single source of truth** - All module configuration in one place
- **Inline configuration syntax** - Define parameter values once, eliminate repetition
- **Automatic composition** - Parameters inherit across configurations seamlessly
- **Configuration inheritance** - Build complex configs from simpler base configs
- **Multi-configuration support** - Test multiple parameter sets in one command
- **Type-safe validation** - Pydantic models ensure correctness at load time
- **Expression evaluation** - Computed parameters (e.g., `log2(WIDTH)`)

### ⚡ Simulation & Testing

- **Verilator first** - Fast, open-source simulation with no license fees
- **Cocotb integration** - Pure Python testbenches, no SystemVerilog TB required
- **No pytest dependency** - Direct test execution via cocotb runner
- **Test auto-discovery** - Finds `sim_*.py` test files automatically
- **VCD waveform generation** - Enabled by default for debugging
- **Multi-simulator support** - Verilator, ModelSim, Questa (via CLI flag)
- **Configuration per test** - Override parameters for specific test cases
- **Parallel execution** - Run multiple configurations simultaneously

### 🛠️ Development Experience

- **Unified CLI** - Single tool (`asd`) for all HDL development tasks
- **Smart repository detection** - Finds project root automatically
- **Relative path handling** - All paths relative to repository root
- **Makefile integration** - Common tasks via `make test`, `make lint`, etc.
- **Pre-commit hooks** - Automatic code quality enforcement
- **Comprehensive error messages** - Clear feedback when things go wrong
- **Rich terminal output** - Colored, formatted output for better readability

### 🔍 Code Quality

- **Verilator lint** - Built-in HDL linting with configurable warnings
- **Parameter validation** - Range checks, allowed values, type enforcement
- **Strict type checking** - Python code validated with mypy in strict mode
- **Auto-formatting** - Black, isort, ruff maintain consistent code style
- **Security scanning** - Bandit checks for common security issues
- **Documentation checks** - Google-style docstrings enforced

### 📦 Project Organization

- **Repository-centric** - Clear project boundaries with `.asd/` directory
- **Hierarchical sources** - Packages → modules → includes compilation order
- **Dependency management** - Track inter-module dependencies in TOML
- **Build isolation** - Each config gets its own `build-{module}-{config}` directory
- **Resource management** - Memory files, test data tracked alongside HDL

### 📚 Library Management

- **External RTL libraries** - Use RTL modules from separate Git repositories
- **Simple syntax** - Reference library sources with `@libname/path` prefix
- **Transitive dependencies** - Libraries can depend on other libraries
- **Git-based versioning** - Pin libraries to tags, branches, or commits
- **Auto-include directories** - Include paths from libraries added automatically
- **Isolated storage** - Libraries cloned to `.asd/libs/` (gitignored)

### 🎯 Workflow Integration

- **CI/CD friendly** - Poetry-based, reproducible builds
- **Git-aware** - Respects `.git` for repository boundaries
- **Environment variables** - Override parameters from CI environment
- **JSON/YAML export** - Configuration introspection via `asd info`
- **Flexible overrides** - CLI → Tool → Config → Inline → Defaults priority

## Installation

### Prerequisites

- **Python 3.12 or higher**
- **Poetry** - Dependency management and packaging
- **Verilator** - HDL simulator and linter (optional, but recommended)
- **cocotb** - Installed automatically via poetry

### Quick Install (Users)

```bash
# Clone the repository
git clone https://github.com/lockedloop/asd.git
cd asd

# Install with poetry
poetry install

# Verify installation
poetry run asd --help
```

### Development Install

For development with pre-commit hooks and all dev tools:

```bash
# Clone the repository
git clone https://github.com/lockedloop/asd.git
cd asd

# Option 1: Using Makefile (recommended)
make install
# This runs:
#   - poetry install --with dev
#   - poetry run pre-commit install

# Option 2: Manual installation
poetry install --with dev
poetry run pre-commit install
```

### Install Verilator

ASD uses [Verilator](https://verilator.org) as the default simulator and linter.
Verilator is a free, open-source HDL simulator that compiles Verilog/SystemVerilog to
optimized C++ or SystemC.

```bash
# macOS
brew install verilator

# Ubuntu/Debian
sudo apt-get install verilator

# Arch Linux
sudo pacman -S verilator

# From source (for latest version)
git clone https://github.com/verilator/verilator
cd verilator
autoconf
./configure
make -j$(nproc)
sudo make install
```

For more information and detailed installation instructions, see the [Verilator documentation](https://verilator.org/guide/latest/install.html).

### Verify Installation

```bash
# Check ASD is installed
asd --help

# Check Verilator is available
verilator --version

# Run a quick test
cd examples/counter
asd info rtl/counter.toml
```

## Quick Start

### 1. Initialize a new project

```bash
# Navigate to your project directory
cd /path/to/your/project

# Create the .asd/ directory structure
asd init
```

**What `asd init` does:**

- Creates a `.asd/` directory in the current directory with:
  - `libraries.toml` - Empty library manifest for managing dependencies
  - `libs/` - Directory for cloned library repositories (gitignored)
- This marks the repository root - all paths in TOML files will be relative to this
  location
- You must run `asd` commands from within this directory (or its subdirectories)
- Similar to how Git uses `.git/`, ASD uses `.asd/` to identify the project boundary

### 2. Generate TOML from existing Verilog (Experimental)

**Note:** TOML auto-generation is an experimental feature and may not capture all
module details perfectly. Review and edit the generated TOML as needed.

```bash
# Basic generation - creates my_module.toml from my_module.sv
asd auto --top src/my_module.sv

# With dependency scanning - automatically finds and includes instantiated modules
asd auto --top src/my_module.sv --scan

# Interactive mode - prompts for configuration details
asd auto --top src/my_module.sv --scan --interactive

# Specify output file
asd auto --top src/my_module.sv --scan --output configs/my_module.toml
```

The `--scan` flag automatically discovers dependencies by parsing module
instantiations. All paths in the generated TOML will be relative to the `.asd/`
location.

### 3. Run simulation

Simulate your HDL module with cocotb tests using Verilator (or other simulators).

```bash
# Run with default configuration
asd sim rtl/my_module.toml

# Use a specific configuration (e.g., "wide" with different parameters)
asd sim rtl/my_module.toml -c wide

# Run multiple configurations sequentially
asd sim rtl/my_module.toml -c default -c wide -c narrow

# Run all configurations defined in TOML
asd sim rtl/my_module.toml -c all

# Override parameters from command line
asd sim rtl/my_module.toml --param WIDTH=32 --param DEPTH=1024

# Run specific test
asd sim rtl/my_module.toml --test stress

# Use different simulator
asd sim rtl/my_module.toml --simulator modelsim

# Disable waveform generation (faster simulation)
asd sim rtl/my_module.toml --no-waves
```

**Example workflow:**

```bash
# List available tests
asd sim rtl/counter.toml --list-tests

# Run smoke test with narrow configuration
asd sim rtl/counter.toml -c narrow --test smoke

# Run all tests with wide configuration and custom parameters
asd sim rtl/counter.toml -c wide --param MAX_COUNT=65535
```

Simulation results and VCD waveforms are saved to `build-{module}-{config}/` directory.

### 4. Lint your code

Check your HDL code for lint warnings and errors using Verilator's built-in linter.

```bash
# Lint with default configuration
asd lint rtl/my_module.toml

# Lint with specific configuration
asd lint rtl/my_module.toml -c wide

# Lint multiple configurations
asd lint rtl/my_module.toml -c default -c wide

# Lint all configurations
asd lint rtl/my_module.toml -c all

# Override parameters to lint with maximum values
asd lint rtl/my_module.toml --param WIDTH=32 --param FIFO_DEPTH=128

# Suppress specific warnings
asd lint rtl/my_module.toml --extra-args "-Wno-WIDTH -Wno-UNUSED"

# Verbose output (shows full Verilator command)
asd lint rtl/my_module.toml --verbose
```

**Example workflow:**

```bash
# Lint all configurations to catch issues across parameter ranges
asd lint rtl/fifo.toml -c all

# Lint with maximum parameter values and verbose output
asd lint rtl/fifo.toml --param DEPTH=1024 --param WIDTH=64 --verbose

# Lint while ignoring specific warnings common in your codebase
asd lint rtl/uart.toml --extra-args "-Wno-UNUSED -Wno-PINMISSING"
```

Verilator will report any syntax errors, lint warnings, or potential issues in your HDL code.

## TOML Configuration Format

ASD uses TOML files as the single source of truth for HDL module configuration.
All paths in TOML files are **relative to the repository root**.

### Configuration Composition System

The key innovation in ASD is **inline configuration syntax** that eliminates
parameter repetition. Define parameter values once, reuse everywhere:

```toml
[parameters.WIDTH]
default = 8
wide = 16      # Automatically creates configurations.wide.parameters.WIDTH = 16
narrow = 4     # Automatically creates configurations.narrow.parameters.WIDTH = 4
```

### Complete TOML Reference

#### `[asd]` Section - Metadata

Required version information for the TOML format.

```toml
[asd]
version = "1.0"         # TOML format version (required)
generated = true        # True if auto-generated (optional)
```

#### `[module]` Section - Module Definition

Core module identification and classification.

```toml
[module]
name = "counter"              # Module name (required)
top = "counter"               # Top-level module name (required)
type = "rtl"                  # Module type (optional, default: "rtl")
                              # Options: rtl, testbench, ip, primitive
description = "8-bit counter" # Module description (optional)
```

#### `[module.sources]` Section - Source Files

All source file paths are relative to repository root.
Files are compiled in order: packages → modules.

```toml
[module.sources]
# SystemVerilog packages (compiled first, contain type definitions)
packages = [
    "src/pkg/types_pkg.sv",
    "src/pkg/functions_pkg.sv"
]

# HDL module files (main source files)
modules = [
    "src/submodule_a.sv",
    "src/submodule_b.sv",
    "src/top_module.sv"
]

# Include/header files (added to include path)
includes = [
    "src/defines.svh",
    "src/config.vh"
]

# Additional resources (memory init files, test data)
resources = [
    "data/rom_init.mem",
    "data/test_vectors.dat"
]
```

#### `[parameters.PARAM_NAME]` Section - Parameters with Inline Configs

Parameters support **inline configuration values** - any extra field automatically
creates a configuration with that parameter value.

**Basic Parameter:**

```toml
[parameters.WIDTH]
default = 8                    # Default value (required)
type = "integer"               # Type (optional, auto-inferred from default)
                              # Options: integer, string, boolean, real
description = "Data width"     # Description (optional)
```

**Parameter with Validation:**

```toml
[parameters.FIFO_DEPTH]
default = 16
type = "integer"
range = [8, 128]              # Min/max validation
values = [8, 16, 32, 64, 128] # Allowed values list
description = "FIFO depth in entries"
```

**Parameter with Inline Configurations:**

```toml
[parameters.WIDTH]
default = 8       # Default configuration uses this
wide = 16         # configurations.wide.parameters.WIDTH = 16
narrow = 4        # configurations.narrow.parameters.WIDTH = 4
ultra_wide = 32   # configurations.ultra_wide.parameters.WIDTH = 32
```

**Computed Parameter with Expressions:**

```toml
[parameters.DATA_WIDTH]
default = 32

[parameters.ADDR_WIDTH]
expr = "log2(${DATA_WIDTH})"  # Evaluated expression
type = "integer"
description = "Computed from DATA_WIDTH"
# Supported functions: log2, log10, log, sqrt, ceil, floor, min, max, abs
```

**Parameter from Environment Variable:**

```toml
[parameters.BUILD_ID]
default = "dev"
env = "CI_BUILD_ID"  # Override from environment variable
type = "string"
```

#### `[defines.DEFINE_NAME]` Section - Preprocessor Defines

Defines work identically to parameters but are used for preprocessor directives.
Also support inline configuration syntax.

```toml
[defines.SIMULATION]
default = false
fast_sim = true       # configurations.fast_sim.defines.SIMULATION = true
debug = true          # configurations.debug.defines.SIMULATION = true

[defines.VERILATOR]
default = false
description = "Enable Verilator-specific code"

[defines.DEBUG_LEVEL]
default = 0
debug = 2
type = "integer"
values = [0, 1, 2, 3]
```

#### `[configurations.NAME]` Section - Named Configurations

Configurations are named collections of parameter and define values.
Values from inline definitions are automatically merged.

**Simple Configuration (uses defaults):**

```toml
[configurations.default]
# Uses all default parameter/define values
description = "Default configuration"
```

**Configuration with Overrides:**

```toml
[configurations.fast_sim]
description = "Fast simulation configuration"
parameters = {
    CLK_FREQ = 1000000,   # Override specific parameters
    FIFO_DEPTH = 8
}
defines = {
    SIMULATION = true,     # Override specific defines
    FAST_SIM = true
}
```

**Configuration with Inheritance:**

```toml
[configurations.base]
parameters = { WIDTH = 32, DEPTH = 1024 }

[configurations.base_shallow]
inherit = "base"              # Start from base configuration
parameters = { DEPTH = 64 }   # Override only DEPTH
# Result: WIDTH=32 (inherited), DEPTH=64 (overridden)
```

**Automatic Configuration from Inline Values:**

When you use inline configuration syntax in parameters/defines,
configurations are automatically created:

```toml
[parameters.WIDTH]
default = 8
wide = 16
narrow = 4

# This automatically creates:
# - configurations.default (WIDTH=8)
# - configurations.wide (WIDTH=16)
# - configurations.narrow (WIDTH=4)

# You can add explicit overrides:
[configurations.wide]
defines = { WIDE_MODE = true }  # Add to auto-created config
```

#### `[tools.simulation]` Section - Simulation Configuration

Configure cocotb-based simulation with Verilator.

**Note:** Simulator is specified via CLI `--simulator verilator|modelsim`,
NOT in the TOML file.

```toml
[tools.simulation]
# Configurations this tool supports
configurations = ["default", "fast_sim"]  # Specific list
# OR
configurations = ["all"]                   # Support all configurations

# Tool-specific parameter overrides (highest priority)
parameters = {
    TIMEOUT_CYCLES = 10000
}

# Tool-specific define overrides
defines = {
    SIMULATION = true,
    VERILATOR = true
}
```

**Test Specification - Simple List Format:**

```toml
[tools.simulation]
# List of test file paths (auto-generates test names from filenames)
tests = [
    "tests/sim_basic.py",
    "tests/sim_advanced.py"
]
# Creates tests named: sim_basic, sim_advanced
```

**Test Specification - Explicit Dict Format:**

```toml
[tools.simulation.tests.smoke]
test_module = "tests/sim_smoke.py"
timeout = 30                              # Timeout in seconds
parameters = { WIDTH = 8 }                # Test-specific parameters
env = { TEST_LEVEL = "smoke" }            # Environment variables

[tools.simulation.tests.stress]
test_module = "tests/sim_stress.py"
timeout = 300
parameters = { WIDTH = 32, DEPTH = 1024 }
env = {
    TEST_ITERATIONS = "10000",
    VERBOSE = "1"
}
```

**Verilator-Specific Settings:**

```toml
[tools.simulation.verilator]
compile_args = [
    "--timing",           # Enable timing
    "-O3",                # Optimization level
    "--trace-fst",        # FST waveform format
    "--threads", "4"      # Parallel compilation
]
sim_args = [
    "+trace"              # Runtime trace enable
]
defines = {
    VERILATOR_TIMING = true
}
```

**ModelSim-Specific Settings:**

```toml
[tools.simulation.modelsim]
compile_args = ["-work", "work"]
sim_args = ["-c", "-do", "run -all"]
```

#### `[tools.lint]` Section - Linting Configuration

Configure Verilator lint checking.

```toml
[tools.lint]
configurations = ["all"]      # Support all configurations
tool = "verilator"            # Linter tool (default: verilator)

# Lint-specific parameter overrides (e.g., use max values)
parameters = {
    WIDTH = 32,               # Lint with maximum width
    FIFO_DEPTH = 128
}

defines = {
    LINT_MODE = true,
    SYNTHESIS = false
}
```

#### `[tools.synthesis]` Section - Synthesis Configuration

Configure FPGA synthesis (optional).

```toml
[tools.synthesis]
tool = "vivado"                          # Synthesis tool
configurations = ["high_performance"]    # Supported configs
part = "xcvu37p-fsvh2892-2L-e"          # FPGA part
strategy = "Performance_ExploreWithRemap" # Synthesis strategy

parameters = {
    PIPELINE_STAGES = 4  # Synthesis-specific overrides
}

defines = {
    SYNTHESIS = true,
    XILINX = true
}
```

### Complete Working Examples

**Note:** When using inline configuration syntax (defining values directly in
parameter/define sections), you do **not** need to explicitly create
`[configurations.X]` sections. The configurations are automatically created and merged
from all inline values. Only add explicit `[configurations.X]` sections when you need
to override values or add additional defines that aren't in the inline definitions.

#### Example 1: Simple Counter with Inline Configurations

```toml
[asd]
version = "1.0"

[module]
name = "counter"
top = "counter"
type = "rtl"

[module.sources]
modules = ["examples/counter/rtl/counter.sv"]

# Inline configuration syntax - define once, reuse everywhere
[parameters.WIDTH]
default = 8
wide = 16      # Automatically creates "wide" configuration
narrow = 4     # Automatically creates "narrow" configuration

[parameters.MAX_COUNT]
default = 255
wide = 65535   # Automatically merges into "wide" configuration

# No need to explicitly define configurations - they're auto-created!
# The following configurations are automatically available:
# - "default": WIDTH=8, MAX_COUNT=255
# - "wide": WIDTH=16, MAX_COUNT=65535
# - "narrow": WIDTH=4, MAX_COUNT=255

[tools.simulation]
configurations = ["default", "wide", "narrow"]
tests = ["examples/counter/sim/sim_counter.py"]

[tools.lint]
configurations = ["all"]  # Lint supports any configuration
```

#### Example 2: UART Controller with Explicit Tests

```toml
[asd]
version = "1.0"

[module]
name = "uart_controller"
top = "uart_top"
type = "rtl"
description = "UART controller with configurable baud rate"

[module.sources]
packages = ["src/uart/pkg/uart_pkg.sv"]
modules = [
    "src/uart/rtl/uart_tx.sv",
    "src/uart/rtl/uart_rx.sv",
    "src/uart/rtl/uart_top.sv"
]
includes = ["src/uart/include/uart_defines.svh"]

[parameters.CLK_FREQ]
default = 100000000
fast_sim = 1000000
description = "System clock frequency in Hz"

[parameters.BAUD_RATE]
default = 115200
type = "integer"
values = [9600, 19200, 38400, 57600, 115200, 921600]
description = "UART baud rate"

[parameters.DATA_BITS]
default = 8
type = "integer"
range = [5, 9]

[defines.SIMULATION]
default = false
fast_sim = true
debug = true

[defines.ENABLE_PARITY]
default = false

[configurations.default]
description = "Production configuration"

[configurations.fast_sim]
description = "Fast simulation with reduced clock frequency"

[configurations.debug]
description = "Debug configuration with extra checks"
parameters = { DATA_BITS = 8 }
defines = { ENABLE_PARITY = true }

[tools.simulation]
configurations = ["fast_sim", "debug"]

# Explicit test configuration
[tools.simulation.tests.smoke]
test_module = "tests/sim_smoke.py"
timeout = 30
parameters = { BAUD_RATE = 9600 }
description = "Basic smoke test"

[tools.simulation.tests.stress]
test_module = "tests/sim_stress.py"
timeout = 300
parameters = { BAUD_RATE = 921600 }
env = {
    TEST_ITERATIONS = "10000",
    VERBOSE = "1"
}

[tools.simulation.verilator]
compile_args = ["--timing", "-O3", "--trace-fst"]
sim_args = ["+trace"]

[tools.lint]
configurations = ["default"]
parameters = { DATA_BITS = 9 }  # Lint with maximum value
```

#### Example 3: Configuration Inheritance

```toml
[parameters.WIDTH]
default = 8

[parameters.DEPTH]
default = 16

[parameters.PIPELINE_STAGES]
default = 1

[configurations.default]
description = "Basic configuration"

[configurations.large]
description = "Large configuration"
parameters = {
    WIDTH = 32,
    DEPTH = 1024,
    PIPELINE_STAGES = 4
}

[configurations.large_shallow]
inherit = "large"
description = "Large width but shallow depth"
parameters = { DEPTH = 64 }
# Result: WIDTH=32 (inherited), DEPTH=64 (overridden),
#         PIPELINE_STAGES=4 (inherited)

[tools.simulation]
configurations = ["default", "large_shallow"]
```

### Configuration Resolution Priority

When running a tool with a configuration, values are resolved in this order
(highest priority last):

1. **Parameter defaults** from `[parameters]`
2. **Inline configuration values** (extra fields in parameters/defines)
3. **Explicit configuration overrides** from `[configurations.NAME]`
4. **Inherited configuration values** (if using `inherit`)
5. **Tool-specific overrides** from `[tools.TOOL.parameters]`
6. **CLI overrides** from `--param KEY=VALUE` (highest priority)

Example:

```bash
# With WIDTH default=8, wide=16, tools.simulation.parameters.WIDTH=12
asd sim module.toml -c wide --param WIDTH=32
# Resolution: 8 → 16 (inline) → 12 (tool) → 32 (CLI)
# Final: WIDTH=32
```

## CLI Commands

### `asd init`

Initialize a new ASD repository by creating the `.asd/` directory structure.

```bash
# Navigate to your project directory first
cd /path/to/your/project

# Create the .asd/ directory
asd init
```

This creates a `.asd/` directory containing:

- `libraries.toml` - Empty library manifest for dependencies
- `libs/` - Directory for cloned library repositories

This marks the current directory as the repository root for all path resolution.

### `asd auto` (Experimental)

Automatically generate TOML configuration from HDL sources. This is an experimental feature.

```bash
# Basic generation
asd auto --top src/top_module.sv

# With dependency scanning
asd auto --top src/top_module.sv --scan

# Interactive mode with prompts
asd auto --top src/top_module.sv --interactive

# Specify output file
asd auto --top src/top_module.sv --output my_module.toml
```

All paths in the generated TOML will be relative to the repository root (`.asd/` directory).

### `asd sim`

Run simulation with specified configuration.

```bash
# Basic simulation (uses default configuration)
asd sim module.toml

# Use specific configuration
asd sim module.toml -c wide

# Multiple configurations
asd sim module.toml -c default -c wide -c narrow

# Use all configurations
asd sim module.toml -c all

# With parameter overrides
asd sim module.toml --param WIDTH=16 --param DEPTH=32

# With specific simulator
asd sim module.toml --simulator modelsim

# Disable waveforms
asd sim module.toml --no-waves

# List available tests
asd sim module.toml --list-tests

# Run specific test
asd sim module.toml --test smoke
```

### `asd lint`

Run lint checks on HDL sources.

```bash
# Basic linting (uses default configuration)
asd lint module.toml

# Use specific configuration
asd lint module.toml -c wide

# Multiple configurations
asd lint module.toml -c default -c wide

# With parameter overrides
asd lint module.toml --param WIDTH=32

# Pass extra arguments to Verilator
asd lint module.toml --extra-args "-Wno-WIDTH -Wno-UNUSED"

# Verbose output
asd lint module.toml --verbose
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

### `asd lib`

Manage external RTL library dependencies. See [Library Management](#library-management)
for full details.

```bash
# Add a library
asd lib add https://github.com/user/mylib.git --tag v1.0.0
asd lib add git@github.com:user/lib.git --branch main
asd lib add https://github.com/user/lib.git --commit abc123 --name custom-name

# Install all libraries from manifest
asd lib install

# Install specific library
asd lib install mylib

# Update libraries
asd lib update        # Update all
asd lib update mylib  # Update specific

# List libraries
asd lib list

# Remove a library
asd lib remove mylib
```

## How Configuration Composition Works

ASD eliminates parameter repetition through **inline configuration syntax**.
Define parameter values once, reuse everywhere without duplication.

### The Problem (Traditional Approach)

```toml
# ❌ Traditional: Repeat parameters for each configuration
[parameters]
WIDTH = { default = 8 }

[configurations.default]
parameters = { WIDTH = 8 }    # Repetition!

[configurations.wide]
parameters = { WIDTH = 16 }   # Repetition!

[configurations.narrow]
parameters = { WIDTH = 4 }    # Repetition!
```

### The Solution (ASD Inline Syntax)

```toml
# ✅ ASD: Define once, no repetition
[parameters.WIDTH]
default = 8
wide = 16      # Automatically creates configurations.wide.parameters.WIDTH = 16
narrow = 4     # Automatically creates configurations.narrow.parameters.WIDTH = 4

# Configurations automatically inherit these values
[configurations.default]
# Gets WIDTH=8 automatically

[configurations.wide]
# Gets WIDTH=16 automatically, can add more overrides
defines = { WIDE_MODE = true }
```

### Resolution Priority

Values are resolved in priority order (lowest to highest):

1. **Parameter defaults** - Base values from `[parameters.NAME.default]`
2. **Inline configuration** - Extra fields in parameters/defines sections
3. **Explicit configuration** - Values in `[configurations.NAME]`
4. **Configuration inheritance** - Values from `inherit` parent
5. **Tool overrides** - Tool-specific `[tools.TOOL.parameters]`
6. **CLI overrides** - Command-line `--param` flags (highest priority)

### Example: Multi-Level Override

```toml
[parameters.WIDTH]
default = 8        # Priority 1: Base default
wide = 16          # Priority 2: Inline config

[configurations.wide]
parameters = { WIDTH = 32 }  # Priority 3: Explicit override

[tools.simulation]
configurations = ["wide"]
parameters = { WIDTH = 64 }  # Priority 5: Tool override

# Command line:
# asd sim module.toml -c wide --param WIDTH=128

# Resolution chain:
# 8 (default) → 16 (inline) → 32 (explicit) → 64 (tool) → 128 (CLI)
# Final result: WIDTH = 128
```

### Benefits

- **Zero repetition** - Define parameter values once
- **Automatic composition** - Configurations inherit from inline values
- **Flexible overrides** - Each level can override as needed
- **Type safety** - Values validated at load time
- **Clear precedence** - Explicit resolution order

## Library Management

ASD supports external RTL libraries that can be shared across multiple projects. Libraries
are Git repositories containing reusable HDL modules that you can reference in your TOML
configurations using the `@libname/path` syntax.

### Overview

The library system allows you to:

- **Create reusable RTL libraries** - Any ASD project can be used as a library
- **Share code across projects** - Use the same modules in multiple projects
- **Version control dependencies** - Pin libraries to specific tags, branches, or commits
- **Handle transitive dependencies** - Libraries can depend on other libraries
- **Auto-resolve include paths** - Include directories from libraries are added automatically

### Directory Structure

When you run `asd init`, the following structure is created:

```bash
your-project/
├── .asd/
│   ├── libraries.toml    # Library manifest (tracks dependencies)
│   └── libs/             # Cloned library repositories (gitignored)
│       ├── mylib/        # Cloned from github.com/user/mylib.git
│       └── otherlib/     # Cloned from github.com/user/otherlib.git
├── rtl/
│   └── my_module.sv
└── ...
```

The `.asd/libs/` directory is automatically added to `.gitignore` - libraries are
downloaded fresh on each machine using `asd lib install`.

### Library Manifest Format

The library manifest (`.asd/libraries.toml`) tracks all library dependencies:

```toml
[asd]
version = "1.0"

[libraries.mylib]
git = "https://github.com/user/mylib.git"
tag = "v1.0.0"

[libraries.otherlib]
git = "git@github.com:user/otherlib.git"
branch = "main"

[libraries.specific]
git = "https://github.com/user/specific.git"
commit = "abc123def456789"
```

Each library requires:

- `git` - The Git repository URL (HTTPS or SSH)
- One of: `tag`, `branch`, or `commit` for version specification

### Using Library Sources in TOML

Reference library sources using the `@libname/path` prefix:

```toml
[module]
name = "my_project"
top = "my_top"

[module.sources]
packages = [
    "rtl/pkg/local_pkg.sv",           # Local source
    "@mylib/src/pkg/types_pkg.sv",    # From library 'mylib'
]

modules = [
    "rtl/my_module.sv",               # Local source
    "@mylib/rtl/counter.sv",          # From library 'mylib'
    "@otherlib/src/fifo.sv",          # From library 'otherlib'
]

includes = [
    "rtl/defines.svh",                # Local include
    "@mylib/include/common.svh",      # From library 'mylib'
]
```

The `@libname/` prefix is resolved to the library's location in `.asd/libs/libname/`.

### Library CLI Commands

#### `asd lib add` - Add a Library

Add a new library dependency to your project:

```bash
# Add library with specific tag
asd lib add https://github.com/user/counter-lib.git --tag v1.0.0

# Add library tracking a branch
asd lib add https://github.com/user/utils-lib.git --branch main

# Add library at specific commit
asd lib add https://github.com/user/fifo-lib.git --commit abc123def

# Add with custom name (default: derived from URL)
asd lib add https://github.com/user/hdl-library.git --tag v2.0 --name myhdl

# SSH URL
asd lib add git@github.com:user/private-lib.git --tag v1.0.0
```

**Library name derivation:**

- `https://github.com/user/mylib.git` → `mylib`
- `git@github.com:user/my-utils.git` → `my-utils`
- Use `--name` to override the derived name

#### `asd lib install` - Install Libraries

Download and checkout all libraries from the manifest:

```bash
# Install all libraries
asd lib install

# Install specific library only
asd lib install mylib
```

This clones repositories to `.asd/libs/` and checks out the specified version.

#### `asd lib update` - Update Libraries

Fetch and update libraries to their specified versions:

```bash
# Update all libraries
asd lib update

# Update specific library
asd lib update mylib
```

For branches, this fetches the latest commits. For tags/commits, this ensures
the correct version is checked out.

#### `asd lib list` - List Libraries

Show all libraries in the project:

```bash
asd lib list
```

Output:

```text
                    Libraries
┏━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ Name      ┃ Version      ┃ Git URL                               ┃ Status        ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ mylib     │ tag: v1.0.0  │ https://github.com/user/mylib.git     │ installed     │
│ otherlib  │ branch: main │ git@github.com:user/otherlib.git      │ not installed │
└───────────┴──────────────┴───────────────────────────────────────┴───────────────┘
```

#### `asd lib remove` - Remove a Library

Remove a library from the project:

```bash
asd lib remove mylib
```

This removes the library from the manifest and deletes it from `.asd/libs/`.

### Transitive Dependencies

Libraries can have their own dependencies. If a library contains its own
`.asd/libraries.toml`, those dependencies are resolved recursively.

**Example:**

Your project depends on `mylib`:

```toml
# .asd/libraries.toml
[libraries.mylib]
git = "https://github.com/user/mylib.git"
tag = "v1.0.0"
```

And `mylib` depends on `utils`:

```toml
# mylib/.asd/libraries.toml
[libraries.utils]
git = "https://github.com/user/utils.git"
tag = "v2.0.0"
```

When you run `asd lib install`, both `mylib` and `utils` are installed.
Circular dependencies are detected and reported as errors.

### Auto-Include Directories

When you use library sources, ASD automatically adds common include directories
from those libraries to the compiler's include path. The following directories
are checked in each referenced library:

- `include/`
- `inc/`
- `rtl/`
- `src/`

This means you typically don't need to explicitly list include paths from libraries.

### Creating a Library

Any ASD project can be used as a library. To create a reusable library:

1. **Create a standard ASD project:**

   ```bash
   mkdir my-rtl-lib
   cd my-rtl-lib
   asd init
   ```

2. **Organize your HDL sources:**

   ```text
   my-rtl-lib/
   ├── .asd/
   │   └── libraries.toml
   ├── rtl/
   │   ├── counter.sv
   │   └── fifo.sv
   ├── include/
   │   └── common.svh
   └── src/
       └── pkg/
           └── types_pkg.sv
   ```

3. **Push to Git and tag releases:**

   ```bash
   git init
   git add .
   git commit -m "Initial library release"
   git tag v1.0.0
   git remote add origin https://github.com/user/my-rtl-lib.git
   git push -u origin main --tags
   ```

4. **Use in other projects:**

   ```bash
   cd other-project
   asd lib add https://github.com/user/my-rtl-lib.git --tag v1.0.0
   asd lib install
   ```

### Complete Example Workflow

#### Step 1: Initialize project and add libraries

```bash
cd my-project
asd init

# Add some libraries
asd lib add https://github.com/hdl-libs/counter.git --tag v1.2.0
asd lib add https://github.com/hdl-libs/fifo.git --branch main
asd lib add git@github.com:company/proprietary-ip.git --tag v3.0.0 --name company-ip

# Install all libraries
asd lib install
```

#### Step 2: Create TOML configuration using library sources

```toml
# rtl/my_design.toml
[asd]
version = "1.0"

[module]
name = "my_design"
top = "top_wrapper"

[module.sources]
packages = [
    "@counter/src/pkg/counter_pkg.sv",
    "@company-ip/rtl/pkg/ip_pkg.sv",
]

modules = [
    "@counter/rtl/counter.sv",
    "@fifo/src/sync_fifo.sv",
    "@company-ip/rtl/special_ip.sv",
    "rtl/top_wrapper.sv",              # Local top-level
]

includes = [
    "@counter/include/counter_defs.svh",
]

[parameters.WIDTH]
default = 8

[tools.simulation]
configurations = ["default"]
tests = ["tests/sim_top.py"]

[tools.lint]
configurations = ["all"]
```

#### Step 3: Run simulation and lint

```bash
# Run simulation
asd sim rtl/my_design.toml

# Run lint
asd lint rtl/my_design.toml
```

### Best Practices

1. **Use semantic versioning** - Tag library releases with semver (v1.0.0, v1.1.0, etc.)

2. **Pin to tags for stability** - Use `--tag` for production projects to ensure reproducible builds

3. **Use branches for development** - Use `--branch main` when actively developing against a library

4. **Document library interfaces** - Include README and example usage in your libraries

5. **Keep libraries focused** - Create small, single-purpose libraries rather than monolithic ones

6. **Run `asd lib install` in CI** - Ensure libraries are installed before running tests in CI/CD

7. **Add `.asd/libs/` to `.gitignore`** - This is done automatically, but verify it's not tracked

## Repository Detection and Path Resolution

### How ASD Finds the Repository Root

ASD automatically detects the repository root using (in priority order):

1. **Explicit `--root` parameter** - Override via CLI: `asd --root /path/to/root sim module.toml`
2. **`ASD_ROOT` environment variable** - Set project root: `export ASD_ROOT=/path/to/root`
3. **`.asd/` directory** - Created by `asd init` in your project directory

If none are found, ASD raises an error instructing you to run `asd init`.

### Path Resolution Rules

**All paths in TOML files are relative to the repository root.** This means:

```toml
# If .asd/ is at /home/user/my_project/
# These paths resolve as:
[module.sources]
modules = [
    "src/counter.sv",           # → /home/user/my_project/src/counter.sv
    "rtl/uart/uart_tx.sv",      # → /home/user/my_project/rtl/uart/uart_tx.sv
    "@mylib/rtl/fifo.sv",       # → /home/user/my_project/.asd/libs/mylib/rtl/fifo.sv
]

[tools.simulation]
tests = [
    "tests/sim_basic.py",       # → /home/user/my_project/tests/sim_basic.py
]
```

**You can run `asd` commands from any subdirectory:**

```bash
cd /home/user/my_project
asd init                        # Creates .asd/ here

cd src
asd sim ../rtl/module.toml      # Works! Finds .asd/ in parent directory

cd ../tests
asd lint ../rtl/module.toml     # Works! All paths resolved from .asd/ location
```

**Important Notes:**

- The `.asd/` directory contains library manifest and cloned dependencies
- TOML file paths (in `asd sim module.toml`) can be absolute or relative to your current directory
- But paths *inside* TOML files are always relative to the repository root
- Paths starting with `@libname/` are resolved from `.asd/libs/libname/`
- Build directories are created relative to repository root: `build-{module}-{config}/`

## Development

ASD uses a comprehensive development setup with pre-commit hooks, type checking,
linting, and testing. The Makefile provides convenient commands for all common tasks.

### Makefile Commands

```bash
make help          # Show all available commands

# Setup
make install       # Install dependencies and pre-commit hooks
make clean         # Clean build artifacts and caches

# Testing
make test          # Run all tests with pytest
make test-cov      # Run tests with coverage report

# Code Quality
make format        # Auto-format code (black, isort, ruff --fix)
make lint          # Run linters (ruff, bandit, pydocstyle)
make type-check    # Run mypy type checker (strict mode)

# Pre-commit
make pre-commit         # Run all pre-commit hooks
make pre-commit-update  # Update pre-commit hook versions
```

### Manual Commands

If you prefer to run commands directly without the Makefile:

```bash
# Testing
poetry run pytest                           # Run all tests
poetry run pytest --cov=asd --cov-report=html  # Coverage report
poetry run pytest tests/unit/test_config.py    # Specific test

# Formatting
poetry run black asd/ tests/
poetry run isort asd/ tests/
poetry run ruff check --fix asd/ tests/

# Linting
poetry run ruff check asd/
poetry run bandit -r asd/ -c pyproject.toml
poetry run pydocstyle asd/

# Type Checking (strict mode)
poetry run mypy asd/

# Pre-commit
poetry run pre-commit run --all-files       # Run all hooks
poetry run pre-commit autoupdate            # Update hook versions
```

### Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`. They enforce:

- **Code formatting** - black, isort
- **Linting** - ruff (replaces flake8, pylint)
- **Type checking** - mypy in strict mode
- **Security** - bandit security scanner
- **Documentation** - pydocstyle for docstrings
- **Markdown** - markdownlint for README/docs

To skip hooks (not recommended):

```bash
git commit --no-verify
```

### Development Workflow

1. **Make changes** to code
2. **Run tests** - `make test` or `poetry run pytest`
3. **Check formatting** - `make format`
4. **Run linters** - `make lint`
5. **Type check** - `make type-check`
6. **Commit** - Pre-commit hooks run automatically
7. **Fix any issues** that hooks report

Or simply run everything at once:

```bash
make pre-commit  # Runs format, lint, type-check, and all hooks
```

## Architecture

```text
asd/
├── core/               # Core components
│   ├── repository.py       # Repository root detection & path resolution
│   ├── config.py           # Pydantic models for module configuration
│   ├── loader.py           # TOML loading with composition
│   ├── library.py          # Library management (LibraryManager, LibraryResolver)
│   └── library_config.py   # Pydantic models for library manifest
├── generators/         # Code generation
│   └── toml_gen.py         # TOML generator from HDL
├── simulators/         # Simulator interfaces
│   ├── base.py             # Abstract simulator base
│   ├── verilator.py        # Verilator implementation
│   └── runner.py           # Simulation runner (cocotb integration)
├── tools/              # Tool implementations
│   └── lint.py             # Verilator lint wrapper
├── utils/              # Utilities
│   ├── sources.py          # Source file management (@libname/ resolution)
│   ├── validation.py       # Configuration validation
│   └── verilog_parser.py   # Basic HDL parsing
├── sims/               # Simulation utilities
│   ├── __init__.py         # Package exports
│   └── axis.py             # AXI-Stream Driver, Monitor, Scoreboard
└── cli.py              # Click-based CLI (includes lib command group)
```

## AXI-Stream Simulation Utilities

ASD provides ergonomic wrappers around cocotbext-axi for AXI-Stream verification
in cocotb testbenches.

### Classes

- **Driver**: Wraps AxiStreamSource for driving transactions with duty cycle control
- **Monitor**: Wraps AxiStreamSink for receiving transactions with backpressure simulation
- **Scoreboard**: Byte or frame-level comparison with automatic logging

### Basic Usage

```python
from asd.sims.axis import Driver, Monitor, Scoreboard
from cocotbext.axi import AxiStreamBus

@cocotb.test()
async def test_loopback(dut):
    driver = Driver(AxiStreamBus.from_prefix(dut, "s_axis"), dut.clk)
    monitor = Monitor(AxiStreamBus.from_prefix(dut, "m_axis"), dut.clk)
    scoreboard = Scoreboard("Test")

    # Optional: set duty cycles for traffic shaping
    driver.set_duty_cycle(0.8)   # 80% valid
    monitor.set_duty_cycle(0.5)  # 50% ready (backpressure)

    await driver.send(b'\x01\x02\x03')
    scoreboard.add_expected(b'\x01\x02\x03')

    result = await monitor.recv(timeout_ns=10000)
    scoreboard.add_actual(result)

    assert scoreboard.check(), scoreboard.report()
```

### Frame-Level Verification

For designs using tid, tdest, tkeep, or tuser sideband signals:

```python
from cocotbext.axi import AxiStreamFrame

scoreboard = Scoreboard("FrameTest", compare_mode="frame")
frame = AxiStreamFrame(tdata=b'\xDE\xAD', tid=5, tdest=3)
scoreboard.add_expected(frame)

result = await monitor.recv_raw()  # Returns full AxiStreamFrame
scoreboard.add_actual(result)
```

### Duty Cycle Control

Control traffic shaping and backpressure with simple duty cycle values:

```python
# Driver: controls tvalid assertion rate
driver.set_duty_cycle(0.5)   # Assert valid 50% of the time

# Monitor: controls tready assertion rate (backpressure)
monitor.set_duty_cycle(0.25)  # Assert ready 25% of the time (heavy backpressure)

# Full speed (default)
driver.set_duty_cycle(1.0)   # Always valid when data available
monitor.set_duty_cycle(1.0)  # Always ready
```

## License

MIT License - See [LICENSE](./LICENSE) file for details

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed guidelines on:

- Development setup and prerequisites
- Running tests and code quality checks
- Pre-commit hooks and coding standards
- Commit message format
- Pull request process

Quick start for contributors:

```bash
# Install dependencies and pre-commit hooks
make install

# Run all quality checks before committing
make pre-commit
```

## Support

For issues and questions:

- Open an issue on GitHub
- Check existing issues first
- Provide minimal reproducible examples

## Roadmap & TODO

### Planned Features

#### 🔍 Smart Discovery & Analysis

- [ ] Automatic HDL source file discovery
- [ ] Dependency graph generation
- [ ] Module hierarchy visualization
- [ ] Unused module detection

#### 🎯 Enhanced TOML Generation

- [ ] Interactive wizard for TOML creation
- [ ] Auto-detection of parameter types from HDL
- [ ] Smart defaults based on module analysis
- [ ] Bulk TOML generation for existing projects

#### 🧪 Testing & Verification

- [ ] Coverage report integration
- [ ] Assertion-based verification support
- [ ] Regression test suite management
- [ ] Test result visualization

#### 📚 Library & Dependency Management

- [x] External RTL library support via Git
- [x] `@libname/path` source syntax
- [x] Transitive dependency resolution
- [x] Auto-include directory detection
- [ ] Lock file for reproducible builds
- [ ] Semver version constraints

#### 🏗️ Build & Integration

- [ ] Multi-simulator support (ModelSim, Questa, VCS)
- [ ] FPGA synthesis integration (Vivado, Quartus)
- [ ] CI/CD pipeline templates
- [ ] Docker container support

#### 📊 Reporting & Documentation

- [ ] HTML documentation generation from TOML
- [ ] Timing report parsing and analysis
- [ ] Resource utilization tracking
- [ ] Build artifact management

#### 🔧 Developer Experience

- [ ] VSCode extension for TOML editing
- [ ] Syntax highlighting and validation
- [ ] Auto-completion for parameter names
- [ ] Configuration diff viewer

### Contributing to Roadmap

Have ideas for features? Open an issue with the `enhancement` label to discuss!
