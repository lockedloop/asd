# Contributing to ASD

Thank you for your interest in contributing to ASD!

## Development Setup

### Prerequisites

- Python 3.12 or higher
- Poetry (for dependency management)
- Git

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/asd.git
   cd asd
   ```

1. Install dependencies and pre-commit hooks:

   ```bash
   make install
   # or manually:
   poetry install --with dev
   poetry run pre-commit install
   ```

## Development Workflow

### Running Tests

```bash
make test                # Run all tests
make test-cov            # Run tests with coverage report
poetry run pytest -k test_name  # Run specific test
```

### Code Quality

```bash
make format              # Auto-format code (black, isort, ruff)
make lint                # Run linters (ruff, bandit, pydocstyle)
make type-check          # Run mypy type checker
make pre-commit          # Run all pre-commit hooks
```

### Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`. They will:

- Format code with Black
- Sort imports with isort
- Lint with Ruff
- Type check with mypy (strict mode)
- Check for security issues with Bandit
- Validate docstrings with pydocstyle
- Check YAML/TOML syntax
- Fix trailing whitespace and line endings

To run manually on all files:

```bash
make pre-commit
# or
poetry run pre-commit run --all-files
```

To skip pre-commit hooks (not recommended):

```bash
git commit --no-verify
```

### Code Style Guidelines

- **Line length**: 100 characters
- **Docstrings**: Google style
- **Type hints**: Required for all functions (mypy strict mode)
- **Import order**: Black-compatible isort profile
- **Formatting**: Automatic with Black

### Type Checking

All code must pass strict mypy type checking:

```bash
make type-check
```

Common mypy issues:

- Add type hints to all function arguments and return values
- Use `Optional[T]` for values that can be None
- Use `Any` sparingly and only when necessary
- Import types from `typing` module

### Testing

- Test files must match `test_*.py` pattern
- Use pytest fixtures for setup/teardown
- Aim for >80% code coverage
- Test both success and error cases

### Making Changes

1. Create a new branch:

   ```bash
   git checkout -b feature/your-feature-name
   ```

1. Make your changes and commit:

   ```bash
   git add .
   git commit -m "feat: add your feature"
   ```

1. Push and create a pull request:

   ```bash
   git push origin feature/your-feature-name
   ```

### Commit Message Format

Follow conventional commits:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

Example:

```text
feat: add cocotb simulation support

- Implement SimulationRunner with cocotb integration
- Add configuration validation
- Support multiple configurations
```

## Project Structure

```text
asd/
├── asd/                    # Main package
│   ├── core/              # Core functionality
│   ├── generators/        # TOML generators
│   ├── simulators/        # Simulation infrastructure
│   ├── tools/             # Tool integrations (lint, etc.)
│   └── utils/             # Utilities
├── tests/                 # Test suite
├── examples/              # Example projects
└── docs/                  # Documentation
```

## Getting Help

- Check existing issues on GitHub
- Read the documentation in `docs/`
- Ask questions in discussions

## License

By contributing, you agree that your contributions will be licensed under
the MIT License.
