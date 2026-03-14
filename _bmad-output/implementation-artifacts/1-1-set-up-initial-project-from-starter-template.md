# Story 1.1: Set Up Initial Project from Starter Template

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want a working codeman package and CLI skeleton,
so that I can run and extend the platform consistently from day one.

## Acceptance Criteria

1. Given a clean project workspace, when the foundation story is implemented, then the project is initialized with `uv init --package codeman`, Python `3.13.x`, `src/codeman/` package layout, and a Typer-based CLI entrypoint, and `uv run codeman --help` succeeds.
2. Given the same initialized workspace, when a developer inspects the baseline structure, then `bootstrap.py`, `runtime.py`, config models, contracts skeletons, and test/lint foundations for `pytest` and `Ruff` are present in the expected architecture locations, and the layout matches the approved architecture baseline closely enough for future stories to build on it without restructuring.

## Tasks / Subtasks

- [x] Align the repository scaffold with the official uv packaged-application baseline. (AC: 1)
  - [x] Reconcile `pyproject.toml` with an official `uv init --package` style packaged project: keep the `codeman` console entrypoint, move the Python requirement to the `3.13` line, and use a packaged-project build configuration rather than the current ad hoc starter metadata.
  - [x] Add `.python-version` pinned to the agreed Python `3.13.x` baseline and ensure the repo is meant to be operated through `uv` only.
  - [x] Ensure `uv run codeman --help` is the primary smoke check and that the first uv project command will generate `uv.lock`.
  - [x] Update `README.md` quick start instructions to use `uv` workflows instead of manual `venv` + `pip` + `unittest`.

- [x] Replace the current `argparse` scaffold with a Typer-based CLI package. (AC: 1, 2)
  - [x] Remove the future import collision between the existing module `src/codeman/cli.py` and the architecture-required package `src/codeman/cli/`; do not keep both names active.
  - [x] Create a root Typer app in `src/codeman/cli/app.py` and expose a callable `main()` wrapper for both `[project.scripts]` and `python -m codeman`.
  - [x] Seed the CLI package with placeholder command modules for `repo`, `index`, `query`, `eval`, `compare`, and `config` so later stories can extend the command tree without restructuring.
  - [x] Keep the MVP CLI help-oriented and skeletal in this story; do not implement retrieval behavior yet.

- [x] Add the baseline architecture files and package skeletons required by the approved structure. (AC: 2)
  - [x] Create `src/codeman/bootstrap.py` as the single composition root for CLI and test wiring.
  - [x] Create `src/codeman/runtime.py` to centralize runtime path resolution for `.codeman/` workspaces.
  - [x] Create skeletal packages for `application`, `domain`, `infrastructure`, `config`, and `contracts` under `src/codeman/` with minimal `__init__.py` files.
  - [x] Add initial `src/codeman/config/models.py` using Pydantic models for configuration placeholders and `src/codeman/contracts/common.py` plus `src/codeman/contracts/errors.py` for response-envelope and error-shape placeholders.
  - [x] Reserve, but do not implement, the future MCP surface in `src/codeman/mcp/`.

- [x] Establish the test and lint foundations expected by the architecture. (AC: 2)
  - [x] Migrate the current `unittest` smoke coverage to `pytest` and place tests in the architecture-aligned hierarchy, at minimum `tests/unit/` and one CLI smoke path that proves the console entrypoint works.
  - [x] Add Ruff configuration and make `uv run ruff check` and `uv run ruff format --check` part of the foundation workflow.
  - [x] Ensure `uv run pytest` passes after the scaffold refactor.
  - [x] Remove or rewrite imports/tests that currently depend on `codeman.cli` being a single file module.

- [x] Match the approved architecture baseline closely enough to avoid a later restructure, while explicitly avoiding scope creep. (AC: 2)
  - [x] Create only the top-level structure and placeholders needed for future work; do not stub every retrieval implementation module from the full architecture tree in this story.
  - [x] Keep this story CLI-first: no HTTP API, no MCP runtime implementation, no persistence schema, and no retrieval logic beyond skeleton boundaries.

### Review Follow-ups (AI)

- [x] [AI-Review][Medium] Replace the hardcoded `UV_CACHE_DIR` path with a repo-relative or temporary path so `tests/e2e/test_cli_help.py` runs on any machine or checkout path. [tests/e2e/test_cli_help.py:11]
- [x] [AI-Review][Medium] Refactor CLI container access so future command modules reuse the callback-initialized `ctx.obj` container instead of calling `bootstrap()` again and silently discarding per-invocation context. [src/codeman/cli/app.py:20]

## Dev Notes

- This is the first story in Epic 1, so there are no prior story learnings to inherit.
- The repository is not actually starting from an empty workspace. The implementation must refactor the current minimal scaffold rather than assuming a clean `uv init` output.

### Current Repo State

- `pyproject.toml` currently uses `setuptools.build_meta`, `requires-python = ">=3.11"`, and a console script pointing at `codeman.cli:main`. This does not yet match the approved Python `3.13.x` + Typer + uv-packaged baseline.
- `src/codeman/cli.py` is an `argparse`-based single-file CLI with a `greet()` helper. If the CLI is moved to `src/codeman/cli/` as required by the architecture, the old module name must be removed or renamed first to avoid a Python import/package collision.
- `src/codeman/__main__.py` currently imports `main` from `codeman.cli`. That import path must be updated when the CLI becomes a package.
- `tests/test_cli.py` is `unittest`-based and imports `greet` from `codeman.cli`. Those tests will break after the CLI package refactor unless migrated deliberately.
- `README.md` still documents `python3 -m venv`, `pip install -e .`, and `unittest`; the architecture and PRD require uv as the official workflow.
- The repo currently does not contain `.python-version`, `uv.lock`, `alembic.ini`, or `.env.example`. For this story, `.python-version` is required, `uv.lock` should appear after the first uv command, and the rest should only be added if they are necessary to satisfy the agreed baseline without inventing future implementation detail.

### Technical Guardrails

- Use the modular-monolith boundaries from the architecture immediately: CLI code belongs under `src/codeman/cli/`, orchestration boundaries under `application/`, pure models/policies under `domain/`, concrete IO under `infrastructure/`, boundary DTOs under `contracts/`, and settings models/loaders under `config`. Do not place business logic in CLI modules. [Source: _bmad-output/planning-artifacts/architecture.md - Structure Patterns; Architectural Boundaries]
- `bootstrap.py` must be the only composition root. Avoid constructing adapters directly inside CLI commands. [Source: _bmad-output/planning-artifacts/architecture.md - Architectural Boundaries]
- `runtime.py` must own workspace path resolution for `.codeman/` runtime state. Do not hardcode runtime directories in command modules. [Source: _bmad-output/planning-artifacts/architecture.md - Data Boundaries]
- Keep CLI naming aligned with the architecture now: top-level command groups should be `repo`, `index`, `query`, `eval`, `compare`, and `config`. [Source: _bmad-output/planning-artifacts/architecture.md - Naming Patterns]
- Keep the interface CLI-only. Do not introduce HTTP routes, web UI, or real MCP transport in this story. The future MCP surface may be reserved as a placeholder only. [Source: _bmad-output/planning-artifacts/prd.md - API Surface; _bmad-output/planning-artifacts/implementation-readiness-report-2026-03-13.md - UX Alignment Assessment]
- Use Pydantic-based skeleton models for config/contracts rather than ad hoc dictionaries so later stories inherit the intended validation boundary. [Source: _bmad-output/planning-artifacts/architecture.md - Decision Priority Analysis; https://docs.pydantic.dev/latest/]

### File / Structure Guidance

- Preferred CLI entry pattern:
  - `src/codeman/cli/app.py` defines `app = typer.Typer(...)`
  - `src/codeman/cli/app.py` also exposes `def main() -> None: app()`
  - `src/codeman/__main__.py` imports and calls that `main()`
  - `[project.scripts]` points to the wrapper function, not the legacy `argparse` module
- Seed only the top-level architecture skeleton in this story. The goal is to make future stories additive, not to pre-create every leaf file from the architecture document.
- Keep `_bmad/` and `_bmad-output/` untouched by application scaffolding changes.
- Keep runtime-managed artifacts outside `src/`, under `.codeman/`, and gitignored. [Source: _bmad-output/planning-artifacts/architecture.md - File Structure Patterns; Project Structure & Boundaries]

### Testing Guidance

- Replace `unittest` usage with `pytest` as the baseline test runner for the project. [Source: _bmad-output/planning-artifacts/architecture.md - Selected Starter; Structure Patterns; https://docs.pytest.org/en/stable/getting-started.html]
- Add at least one smoke test that proves the installed CLI help works via uv, plus unit-level coverage for the Typer bootstrap path.
- Use Ruff as the lint/format foundation and ensure the developer workflow runs through `uv run ruff check` and `uv run ruff format --check`. [Source: https://docs.astral.sh/ruff/tutorial/]

### Latest Tooling Notes

- Official uv packaged applications created with `uv init --package` use a `src/` layout, a `.python-version` file, a `README.md`, a `pyproject.toml`, a console script, and a packaged-project build system. `uv run` then creates `.venv` and `uv.lock` on first project use. The current repo only partially matches that baseline and needs deliberate reconciliation. [Source: https://docs.astral.sh/uv/concepts/projects/init/; https://docs.astral.sh/uv/guides/projects/]
- As of 2026-03-13, Python `3.13.12` is the latest released Python 3.13 bugfix listed in PEP 719, and Python 3.13 remains in its regular bugfix window through the scheduled `3.13.16` release on 2026-10-06. Use the `3.13` line, not `3.11`, for the project baseline. [Source: https://peps.python.org/pep-0719/]
- Typer `0.20.0` is the architecture-selected CLI framework version. Its release notes confirm command typo suggestions are enabled by default and that the release adds Python 3.14 support, which is compatible with the architecture goal of a modern multi-command CLI. [Source: https://typer.tiangolo.com/release-notes/; https://typer.tiangolo.com/reference/typer/]

### Project Structure Notes

- Do not keep both `src/codeman/cli.py` and `src/codeman/cli/` after the refactor. Choose the package layout required by the architecture and migrate imports in one pass.
- Do not leave stale tests importing `greet` from the old module path.
- Do not overbuild retrieval modules, database repositories, or benchmark flows in Story 1.1. This foundation story exists to set boundaries and tooling, not to implement product behavior.
- If placeholder directories such as `docs/architecture/`, `tests/integration/`, or `tests/e2e/` are created, do it in a way that survives version control and makes the intended structure obvious.

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Epic 1 / Story 1.1]
- [Source: _bmad-output/planning-artifacts/prd.md - Developer Tool Specific Requirements; CLI Operations & Troubleshooting; API Surface]
- [Source: _bmad-output/planning-artifacts/architecture.md - Starter Template Evaluation; Core Architectural Decisions; Implementation Patterns & Consistency Rules; Project Structure & Boundaries]
- [Source: _bmad-output/planning-artifacts/implementation-readiness-report-2026-03-13.md]
- [Source: pyproject.toml]
- [Source: src/codeman/cli.py]
- [Source: src/codeman/__main__.py]
- [Source: tests/test_cli.py]
- [Source: README.md]
- [Source: https://docs.astral.sh/uv/concepts/projects/init/]
- [Source: https://docs.astral.sh/uv/guides/projects/]
- [Source: https://docs.astral.sh/uv/concepts/python-versions/]
- [Source: https://peps.python.org/pep-0719/]
- [Source: https://typer.tiangolo.com/release-notes/]
- [Source: https://typer.tiangolo.com/reference/typer/]
- [Source: https://docs.astral.sh/ruff/tutorial/]
- [Source: https://docs.pytest.org/en/stable/getting-started.html]
- [Source: https://docs.pydantic.dev/latest/]

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Implementation Plan

- Rebuild the package around an official uv-style baseline with Python 3.13 pinning, uv-managed lockfile generation, and dependency groups for dev tooling.
- Replace the single-file `argparse` entrypoint with a Typer package and placeholder command groups that match the architecture command surface.
- Add only the top-level architecture skeleton needed for future stories: bootstrap, runtime paths, config/contracts DTOs, layer packages, MCP placeholder, docs placeholders, and pytest/Ruff foundations.

### Debug Log References

- Red phase: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --with pytest pytest -q tests/unit/cli/test_app.py tests/unit/test_runtime.py tests/unit/test_scaffold.py tests/e2e/test_cli_help.py`
- Scaffold baseline check: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv init --package uv-sample` in `/private/tmp/codeman-story1/uv-sample`
- Dependency sync: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv sync --group dev`
- Validation: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev pytest`
- Validation: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev ruff check`
- Validation: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev ruff format --check`
- Review follow-up validation: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev pytest -q tests/unit/cli/test_app.py tests/e2e/test_cli_help.py`

### Completion Notes List

- Replaced the legacy `setuptools` / `argparse` starter with an uv-oriented Python 3.13 scaffold, committed `.python-version`, and generated `uv.lock`.
- Rebuilt the CLI as a Typer package with root `app.py` plus placeholder groups for `repo`, `index`, `query`, `eval`, `compare`, and `config`.
- Added `bootstrap.py`, `runtime.py`, configuration models, contract envelopes, layer package placeholders, MCP placeholder, and documentation placeholders without prematurely implementing retrieval behavior.
- Migrated test coverage to pytest, added a `uv run codeman --help` end-to-end smoke test, and removed the old single-file `unittest` coverage.
- Verified the story with `uv run --group dev pytest`, `uv run --group dev ruff check`, and `uv run --group dev ruff format --check`.
- Resolved review finding [Medium]: replaced the machine-specific `UV_CACHE_DIR` in the e2e smoke test with a repo-relative cache directory.
- Resolved review finding [Medium]: updated the CLI container helper to reuse the callback-initialized `ctx.obj` container and added unit coverage for that behavior.

### File List

- .gitignore
- .python-version
- README.md
- _bmad-output/implementation-artifacts/1-1-set-up-initial-project-from-starter-template.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- docs/architecture/decisions.md
- docs/architecture/patterns.md
- docs/benchmarks.md
- docs/cli-reference.md
- pyproject.toml
- src/codeman/__init__.py
- src/codeman/__main__.py
- src/codeman/application/__init__.py
- src/codeman/bootstrap.py
- src/codeman/cli/__init__.py
- src/codeman/cli/app.py
- src/codeman/cli/common.py
- src/codeman/cli/compare.py
- src/codeman/cli/config.py
- src/codeman/cli/eval.py
- src/codeman/cli/index.py
- src/codeman/cli/query.py
- src/codeman/cli/repo.py
- src/codeman/config/__init__.py
- src/codeman/config/models.py
- src/codeman/contracts/__init__.py
- src/codeman/contracts/common.py
- src/codeman/contracts/errors.py
- src/codeman/domain/__init__.py
- src/codeman/infrastructure/__init__.py
- src/codeman/mcp/README.md
- src/codeman/runtime.py
- tests/e2e/test_cli_help.py
- tests/integration/.gitkeep
- tests/unit/cli/test_app.py
- tests/unit/test_runtime.py
- tests/unit/test_scaffold.py
- uv.lock
- Deleted: src/codeman/cli.py
- Deleted: tests/test_cli.py

## Change Log

- 2026-03-13: Reworked the project scaffold to Python 3.13 + uv + Typer, added architecture skeleton packages, migrated tests to pytest, and validated the baseline with Ruff and pytest.
- 2026-03-14: Code review requested changes; added two medium-severity follow-up items and returned the story to in-progress.
- 2026-03-14: Resolved both code-review follow-ups, reran pytest and Ruff, and returned the story to review.
- 2026-03-14: Re-review passed with no remaining HIGH or MEDIUM findings; story accepted as done.

## Senior Developer Review (AI)

### Outcome

Changes Requested

### Review Date

2026-03-14

### Summary

- Acceptance criteria coverage is broadly in place: Python 3.13 baseline, uv-managed scaffold, Typer CLI, bootstrap/runtime/config/contracts placeholders, and pytest/Ruff foundations are all present.
- Two medium-severity issues remain before this story should be considered done.

### Findings

1. `tests/e2e/test_cli_help.py` hardcodes `UV_CACHE_DIR` to `/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache`. That makes the end-to-end test machine-specific and violates the story's repeatable uv workflow goal for any other user or checkout path.
2. `src/codeman/cli/app.py` bootstraps a container in the Typer callback and then exposes `get_container()` that creates a brand-new container instead of returning the callback-initialized one. Once command modules start using that helper, per-run context or test-injected state will be lost, undermining the intended shared composition-root pattern.

### Action Items

- [x] [Medium] Replace the hardcoded `UV_CACHE_DIR` path with a repo-relative or temporary path so `tests/e2e/test_cli_help.py` runs on any machine or checkout path. [tests/e2e/test_cli_help.py:11]
- [x] [Medium] Refactor CLI container access so future command modules reuse the callback-initialized `ctx.obj` container instead of calling `bootstrap()` again and silently discarding per-invocation context. [src/codeman/cli/app.py:20]

### Re-review Date

2026-03-14

### Re-review Outcome

Approved

### Re-review Notes

- Verified `src/codeman/cli/app.py` now reuses the callback-initialized `ctx.obj` container via `get_container(ctx)`.
- Verified `tests/e2e/test_cli_help.py` now derives `UV_CACHE_DIR` from the repository root instead of using a machine-specific absolute path.
- Re-ran `uv run --group dev pytest` and `uv run --group dev ruff check`; both passed.
- No remaining HIGH or MEDIUM issues found in the Story 1.1 scaffold implementation.
