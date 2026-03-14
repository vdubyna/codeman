# codeman

CLI-first retrieval experimentation scaffold with a BMAD-planned delivery flow.

## What is here

- `src/codeman/` - application package with CLI, config/contracts placeholders, and runtime/bootstrap skeletons
- `tests/` - pytest-based unit and end-to-end coverage for the current scaffold
- `_bmad/` - BMAD workflows and module configuration
- `_bmad-output/` - generated planning and implementation artifacts
- `docs/` - placeholder documentation structure for architecture, CLI usage, and benchmarks

## Quick Start

```bash
uv sync --group dev
uv run codeman --help
uv run codeman repo register /path/to/local/repository
uv run --group dev pytest
uv run --group dev ruff check
uv run --group dev ruff format --check
```

`uv` is the official workflow for Python management, dependency installation, CLI execution, testing, and linting in this repository.

## Project Layout

- `src/codeman/cli/` - Typer command tree
- `src/codeman/config/` - configuration models
- `src/codeman/contracts/` - JSON envelope and error DTO placeholders
- `src/codeman/bootstrap.py` - composition root
- `src/codeman/runtime.py` - runtime path resolution for `.codeman/`

## BMAD

Planning artifacts stay in `_bmad/` and `_bmad-output/`, while production code stays under `src/` and tests stay under `tests/`.
