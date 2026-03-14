# codeman

CLI-first retrieval experimentation scaffold with a BMAD-planned delivery flow.

## What Is Here

- `src/codeman/` - application package with CLI, config/contracts placeholders, and runtime/bootstrap skeletons
- `tests/` - pytest-based unit and end-to-end coverage for the current scaffold
- `_bmad/` - BMAD workflows and module configuration
- `_bmad-output/` - generated planning and implementation artifacts
- `docs/` - canonical human-facing and agent-facing project documentation

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

## Documentation

- [`docs/README.md`](docs/README.md) - documentation ownership map
- [`docs/project-context.md`](docs/project-context.md) - canonical implementation rules for AI agents
- [`docs/cli-reference.md`](docs/cli-reference.md) - supported CLI commands and output contracts
- [`docs/benchmarks.md`](docs/benchmarks.md) - benchmark and evaluation policy
- [`docs/architecture/decisions.md`](docs/architecture/decisions.md) - stable architecture decisions
- [`docs/architecture/patterns.md`](docs/architecture/patterns.md) - current extension and layering patterns
- [`AGENTS.md`](AGENTS.md) - short repo instructions for coding agents

## BMAD

Planning artifacts stay in `_bmad/` and `_bmad-output/`, while production code stays under `src/` and tests stay under `tests/`.
