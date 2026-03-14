# Architecture Decisions

This document captures the stable implementation-level decisions contributors should preserve.

- For extension patterns and code organization, see [`patterns.md`](patterns.md).
- For user-facing CLI contracts, see [`../cli-reference.md`](../cli-reference.md).
- For the full BMAD rationale and future-facing design detail, see [`../../_bmad-output/planning-artifacts/architecture.md`](../../_bmad-output/planning-artifacts/architecture.md).

## Current Decisions

- `codeman` is a CLI-first developer tool in the current implementation; there is no HTTP service or active MCP runtime surface yet.
- The root application is a Typer command tree composed in `src/codeman/cli/app.py`.
- `bootstrap.py` is the composition root for CLI execution and test wiring.
- Boundary DTOs and configuration models use strict Pydantic models.
- Metadata persistence uses SQLAlchemy Core plus Alembic migrations.
- Runtime-managed artifacts, indexes, caches, logs, and metadata live under the workspace `.codeman/` tree.
- Machine-readable command output uses a stable JSON envelope contract on `stdout`; progress and operator diagnostics stay on `stderr`.
- The project remains local-first by default; external-provider-backed behavior must stay explicit and opt-in.
- Retrieval and evaluation behavior should remain attributable through deterministic metadata, fingerprints, and stable run context.

## What Belongs Here

- stable technical decisions that contributors should preserve
- architectural invariants that shape implementation choices
- explicit decisions that are more durable than day-to-day coding patterns

## What Does Not Belong Here

- detailed command examples already owned by `cli-reference.md`
- low-level coding rules already owned by `project-context.md`
- temporary implementation notes that are not yet stable enough to count as decisions
