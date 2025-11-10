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

- **Repository-centric** - Clear project boundaries with `.asd-root` or `.git`
- **Hierarchical sources** - Packages → modules → includes compilation order
- **Dependency management** - Track inter-module dependencies in TOML
- **Build isolation** - Each config gets its own `build-{module}-{config}` directory
- **Resource management** - Memory files, test data tracked alongside HDL

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

# Create the .asd-root marker file
asd init
```

**What `asd init` does:**

- Creates a `.asd-root` marker file in the current directory
- This marks the repository root - all paths in TOML files will be relative to this
  location
- You must run `asd` commands from within this directory (or its subdirectories)
- Similar to how Git uses `.git`, ASD uses `.asd-root` to identify the project
  boundary

**Important:** If you're already using Git, ASD will automatically detect the `.git`
directory as the repository root - running `asd init` is optional in this case.

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
instantiations. All paths in the generated TOML will be relative to the `.asd-root`
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

Initialize a new ASD repository by creating a `.asd-root` marker file.

```bash
# Navigate to your project directory first
cd /path/to/your/project

# Create the .asd-root marker
asd init
```

This creates a `.asd-root` file in the current directory, marking it as the repository
root for all path resolution.

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

All paths in the generated TOML will be relative to the repository root (`.asd-root` or `.git`).

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

## Repository Detection and Path Resolution

### How ASD Finds the Repository Root

ASD automatically detects the repository root using (in priority order):

1. **Explicit `--root` parameter** - Override via CLI: `asd --root /path/to/root sim module.toml`
2. **`ASD_ROOT` environment variable** - Set project root: `export ASD_ROOT=/path/to/root`
3. **`.asd-root` marker file** - Created by `asd init` in your project directory
4. **Git repository root** (`.git`) - Automatically uses Git root if no `.asd-root` exists
5. **Current directory** - Fallback if none of the above are found

### Path Resolution Rules

**All paths in TOML files are relative to the repository root.** This means:

```toml
# If .asd-root is at /home/user/my_project/
# These paths resolve as:
[module.sources]
modules = [
    "src/counter.sv",           # → /home/user/my_project/src/counter.sv
    "rtl/uart/uart_tx.sv",      # → /home/user/my_project/rtl/uart/uart_tx.sv
]

[tools.simulation]
tests = [
    "tests/sim_basic.py",       # → /home/user/my_project/tests/sim_basic.py
]
```

**You can run `asd` commands from any subdirectory:**

```bash
cd /home/user/my_project
asd init                        # Creates .asd-root here

cd src
asd sim ../rtl/module.toml      # Works! Finds .asd-root in parent directory

cd ../tests
asd lint ../rtl/module.toml     # Works! All paths resolved from .asd-root location
```

**Important Notes:**

- The `.asd-root` file is just a marker - it can be empty
- If using Git, `.asd-root` is optional (ASD will use `.git` directory)
- TOML file paths (in `asd sim module.toml`) can be absolute or relative to your current directory
- But paths *inside* TOML files are always relative to the repository root
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
