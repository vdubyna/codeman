# Architecture Patterns

This document describes how to extend the current codebase without introducing parallel structures or duplicate responsibilities.

- For stable architecture decisions, see [`decisions.md`](decisions.md).
- For agent implementation rules, see [`../project-context.md`](../project-context.md).

## Layering Pattern

The current implementation follows a narrow layered flow:

`cli` -> `application` use cases -> `application/ports` -> `infrastructure` adapters -> `contracts` / `config` / `runtime`

Use this layering as the default extension path.

## Current Extension Patterns

### Add a CLI Command

- Add the command to the appropriate module under `src/codeman/cli/`.
- Keep the command thin: parse input, resolve the container, call one use case, render text or JSON.
- Reuse shared envelope helpers and stable exit-code handling.

### Add or Extend a Use Case

- Put orchestration and business flow in `src/codeman/application/`.
- Depend on ports rather than concrete adapters.
- Keep runtime provisioning, metadata attribution, and deterministic ordering explicit.

### Add an Adapter

- Put adapters in `src/codeman/infrastructure/`.
- Keep adapter-specific logic out of CLI handlers and out of contract DTOs.
- Match adapter behavior to the relevant port interface instead of inventing a second integration style.

### Add a Contract

- Put machine-readable DTOs in `src/codeman/contracts/`.
- Prefer additive, explicit fields with stable names and defaults.
- Keep JSON-facing shapes predictable for both automation and tests.

### Add Runtime-Managed Artifacts

- Store generated artifacts under `.codeman/`.
- Keep repository snapshots, chunk payloads, indexes, caches, logs, and temp files within runtime-managed boundaries.
- Avoid writing generated state into `src/`, `tests/fixtures/`, or the indexed target repository.

## Testing Alignment

- `tests/unit/` covers isolated logic and DTO/CLI formatting behavior.
- `tests/integration/` covers adapter seams and persistence behavior.
- `tests/e2e/` covers real CLI flows through `uv run codeman ...`.

## Anti-Patterns to Avoid

- bypassing `bootstrap.py` and instantiating infrastructure directly in CLI handlers
- mixing user-facing CLI docs into architecture documents
- letting planned features create parallel patterns before the implementation exists
- weakening deterministic ordering or metadata attribution for convenience
