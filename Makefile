.PHONY: help install install-dev test format lint type-check clean all

help:
	@echo "Available commands:"
	@echo "  make install       - Install the package"
	@echo "  make install-dev   - Install the package with dev dependencies"
	@echo "  make test          - Run tests with coverage"
	@echo "  make format        - Format code with black and isort"
	@echo "  make lint          - Run flake8 linter"
	@echo "  make type-check    - Run mypy type checker"
	@echo "  make all           - Format, lint, type-check, and test"
	@echo "  make clean         - Remove build artifacts and cache files"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	pytest

format:
	black storage_tools tests
	isort storage_tools tests

lint:
	flake8 storage_tools tests

type-check:
	mypy storage_tools

all: format lint type-check test

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
