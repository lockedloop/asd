.PHONY: help install test lint format type-check pre-commit ci clean

help:
	@echo "ASD Development Commands:"
	@echo ""
	@echo "  make install       Install dependencies and pre-commit hooks"
	@echo "  make test          Run tests with pytest"
	@echo "  make lint          Run linters (ruff, bandit, pydocstyle)"
	@echo "  make format        Auto-format code (black, isort, ruff --fix)"
	@echo "  make type-check    Run mypy type checker"
	@echo "  make pre-commit    Run all pre-commit hooks"
	@echo "  make ci            Run full CI test suite (pre-commit + tests + mypy)"
	@echo "  make clean         Clean build artifacts and caches"
	@echo ""

install:
	@echo "Installing dependencies..."
	poetry install --with dev
	@echo "Installing pre-commit hooks..."
	poetry run pre-commit install
	@echo "✓ Installation complete"

test:
	@echo "Running tests..."
	poetry run pytest

test-cov:
	@echo "Running tests with coverage..."
	poetry run pytest --cov=asd --cov-report=term-missing --cov-report=html

lint:
	@echo "Running linters..."
	poetry run ruff check asd/
	poetry run pydocstyle asd/

format:
	@echo "Formatting code..."
	poetry run black asd/ tests/
	poetry run isort asd/ tests/
	poetry run ruff check --fix asd/ tests/
	@echo "✓ Code formatted"

type-check:
	@echo "Running type checker..."
	poetry run mypy asd/

pre-commit:
	@echo "Running pre-commit hooks..."
	poetry run pre-commit run --all-files

pre-commit-update:
	@echo "Updating pre-commit hooks..."
	poetry run pre-commit autoupdate

ci:
	@echo "==================== Running CI Test Suite ===================="
	@echo ""
	@echo "→ Step 1/3: Running pre-commit hooks..."
	@poetry run pre-commit run --all-files
	@echo ""
	@echo "→ Step 2/3: Running tests with coverage..."
	@poetry run pytest tests/ -v --cov=asd --cov-report=term --cov-report=xml
	@echo ""
	@echo "→ Step 3/3: Running type checks..."
	@poetry run mypy asd
	@echo ""
	@echo "✓ All CI checks passed!"

clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf build/ dist/ htmlcov/ .coverage
	@echo "✓ Cleaned"
