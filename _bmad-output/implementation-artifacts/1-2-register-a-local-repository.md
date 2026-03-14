# Story 1.2: Register a Local Repository

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want to register a local repository as an indexing target,
so that codeman can track it and prepare runtime storage for retrieval workflows.

## Acceptance Criteria

1. Given a valid local repository path, when I run the repository registration command, then codeman stores repository identity and path metadata in the metadata store, and creates the required runtime directories under `.codeman/`.
2. Given an invalid or unreadable repository path, when I attempt registration, then the command fails with a stable non-zero exit outcome and user-safe diagnostic output, and no partial repository record is persisted.

## Tasks / Subtasks

- [x] Introduce the repository registration boundary and typed validation flow. (AC: 1, 2)
  - [x] Add repository-specific request/response DTOs under `src/codeman/contracts/repository.py` so the first real command uses explicit contracts instead of ad hoc dictionaries.
  - [x] Create the application use case in `src/codeman/application/repo/register_repository.py` and keep CLI modules thin.
  - [x] Normalize input paths to one canonical absolute path before persistence and reject non-existent, non-directory, unreadable, or duplicate registrations with typed project errors.
  - [x] Keep repository registration independent from Git revision resolution; readable local directories may register even if Git metadata is unavailable, because fallback revision handling belongs to Story 1.3.

- [x] Add the first metadata persistence slice for repositories using the approved architecture stack. (AC: 1)
  - [x] Introduce the minimal SQLite metadata-store foundation under `src/codeman/infrastructure/persistence/sqlite/`, using SQLAlchemy Core statements rather than ORM-heavy models.
  - [x] Add `alembic.ini`, `migrations/`, and the first migration/revision required to create a `repositories` table in a runtime-resolved SQLite database.
  - [x] Persist at minimum a generated repository identifier, canonical path metadata, a human-readable name, and audit timestamps needed for future snapshot attribution.
  - [x] Enforce a uniqueness boundary on canonical repository path so the same target cannot be registered repeatedly via relative, absolute, or symlinked spellings.

- [x] Provision runtime workspace state through the runtime/bootstrap layer instead of inside CLI commands. (AC: 1)
  - [x] Extend `src/codeman/runtime.py` with an explicit provisioning helper that creates `.codeman/`, `artifacts/`, `indexes/`, `cache/`, `logs/`, and `tmp/` on demand.
  - [x] Add a runtime-resolved metadata database path and wire it through `src/codeman/bootstrap.py`.
  - [x] Keep runtime directory provisioning idempotent so repeated registrations do not fail just because `.codeman/` already exists.

- [x] Implement the `repo register` CLI flow with stable output and failure handling. (AC: 1, 2)
  - [x] Replace the placeholder-only `src/codeman/cli/repo.py` implementation with a thin `register` command that uses `get_container(ctx)` and delegates to the application layer.
  - [x] Support human-readable success output and a JSON mode that uses the project's success/failure envelopes without mixing logs into JSON `stdout`.
  - [x] Map registration failures to stable non-zero exit behavior and user-safe diagnostics without exposing stack traces or repository contents by default.
  - [x] Update user-facing command documentation in `README.md` and/or `docs/cli-reference.md` once the interface is finalized.

- [x] Cover successful, duplicate, and invalid-path flows with automated tests. (AC: 1, 2)
  - [x] Add unit tests for path normalization, validation, and typed error mapping.
  - [x] Add integration tests for SQLite persistence, migration/bootstrap wiring, and runtime directory provisioning in an isolated temp workspace.
  - [x] Add CLI or end-to-end tests for successful registration and for invalid or unreadable paths proving the command exits non-zero and does not leave a persisted repository row behind.

## Dev Notes

### Previous Story Intelligence

- Story 1.1 established the non-negotiable foundation for this story: Typer command groups, `bootstrap.py` as the composition root, `runtime.py` as the runtime path boundary, Pydantic-based config/contracts placeholders, and pytest/Ruff as the validation baseline.
- Story 1.1 review feedback explicitly corrected a bad pattern where command modules might call `bootstrap()` directly instead of reusing the callback-initialized `ctx.obj`. Story 1.2 must keep that fix intact and reuse `get_container(ctx)` from `src/codeman/cli/app.py`.
- The scaffold was intentionally kept thin in Story 1.1. This story should add only the first real repository-ingestion slice required for registration and metadata persistence, not the full snapshotting, parsing, or indexing pipeline.
- The end-to-end CLI smoke test now derives cache paths from the repository root. New tests should follow the same "isolated, repo-relative, no machine-specific paths" rule.

### Current Repo State

- `src/codeman/cli/repo.py` is still only a Typer group placeholder with no registration command or command options.
- `src/codeman/bootstrap.py` currently builds a minimal container with config and resolved runtime paths only; it does not wire application services, persistence adapters, or migrations.
- `src/codeman/runtime.py` resolves `.codeman/` directory paths but intentionally does not create them and does not expose a metadata database path yet.
- `src/codeman/contracts/` currently contains only generic success/failure envelopes. There is no repository DTO file yet.
- `src/codeman/application/` is still an empty package placeholder; there is no `application/repo/` or `application/ports/` implementation yet.
- There is no SQLite metadata store, no `alembic.ini`, no `migrations/`, and no persistence adapter package in the current codebase.
- Current automated coverage proves only scaffold behavior (`uv run codeman --help`, runtime-path resolution, and container reuse). Story 1.2 must introduce the first persistence-aware tests.

### Technical Guardrails

- Keep the public interface CLI-only. This story must not introduce HTTP endpoints, an MCP runtime, or background services. [Source: _bmad-output/planning-artifacts/prd.md - API Surface; _bmad-output/planning-artifacts/architecture.md - API & Communication Patterns]
- Follow the modular-monolith boundaries already established: CLI parses input and formats output, application orchestrates use cases, domain/application errors describe business failures, and infrastructure owns SQLite/filesystem details. [Source: _bmad-output/planning-artifacts/architecture.md - Structure Patterns; Architectural Boundaries]
- `bootstrap.py` remains the single composition root. Do not instantiate SQLAlchemy engines, repository adapters, or migration helpers directly inside `src/codeman/cli/repo.py`. [Source: _bmad-output/planning-artifacts/architecture.md - Component Boundaries]
- `runtime.py` must stay the owner of runtime path resolution. If this story introduces a metadata database path or directory-provisioning helper, put that logic there instead of scattering `.codeman/` path joins across modules. [Source: _bmad-output/planning-artifacts/architecture.md - Data Boundaries]
- Use the architecture-approved persistence stack: SQLite-compatible metadata storage, SQLAlchemy Core 2.0.x access patterns, and Alembic-managed schema evolution. Do not skip straight to handwritten SQL files or an ORM-heavy model graph. [Source: _bmad-output/planning-artifacts/architecture.md - Decision Priority Analysis; Data Architecture]
- Registration must remain local-first and must not send repository information to external providers. This story only records repository metadata and prepares local runtime state. [Source: _bmad-output/planning-artifacts/prd.md - Security & Data Handling]
- Failures must produce stable non-zero CLI outcomes and safe messages. This story can introduce the first minimal exit-code mapping needed for repository registration, but it should keep the mapping intentionally small so Epic 5 can expand it rather than replace it. [Source: _bmad-output/planning-artifacts/epics.md - Story 1.2; _bmad-output/planning-artifacts/architecture.md - Error Handling Standard]
- Do not require a valid Git repository at registration time. Story 1.3 explicitly handles snapshot creation when Git metadata is missing, so Story 1.2 should accept a readable local directory and defer revision identity concerns. [Source: _bmad-output/planning-artifacts/epics.md - Story 1.3]
- Handle duplicate registration deliberately. Canonicalize paths early and avoid creating multiple repository rows for the same target via relative path variants or symlinks.

### File / Structure Guidance

- Preferred new or expanded files for this story:
  - `src/codeman/contracts/repository.py`
  - `src/codeman/application/repo/__init__.py`
  - `src/codeman/application/repo/register_repository.py`
  - `src/codeman/application/ports/metadata_store_port.py`
  - `src/codeman/infrastructure/persistence/sqlite/__init__.py`
  - `src/codeman/infrastructure/persistence/sqlite/engine.py`
  - `src/codeman/infrastructure/persistence/sqlite/tables.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/repository_repository.py`
  - `alembic.ini`
  - `migrations/env.py`
  - `migrations/versions/<timestamp>_create_repositories_table.py`
- A pragmatic runtime database default for this story is a SQLite file directly under `.codeman/` (for example `.codeman/metadata.sqlite3`), resolved through runtime/config rather than hardcoded in persistence code.
- The CLI surface should remain additive to the existing command tree:
  - `uv run codeman repo register /path/to/local/repository`
  - optional machine mode should align with the existing response-envelope contracts instead of inventing a command-specific JSON shape
- `src/codeman/cli/common.py` already has `build_command_meta()`. Reuse it rather than creating a second metadata helper when adding JSON output support.
- Keep this story bounded to repository registration. Do not implement snapshot manifests, parser adapters, chunking, or retrieval engines here.

### Testing Guidance

- Use pytest for all new coverage. Keep unit tests fast and isolated, and use temp workspaces for any filesystem or SQLite integration tests. [Source: _bmad-output/implementation-artifacts/1-1-set-up-initial-project-from-starter-template.md - Testing Guidance]
- Add at least one integration-level assertion that a successful registration creates the `.codeman/` directory tree and persists a repository row to the metadata store.
- Add a negative-path test proving an invalid or unreadable path does not persist a repository row.
- Add a duplicate-registration test so canonical-path uniqueness is protected from regressions.
- If JSON output is introduced for this command, verify that `stdout` contains only the final JSON payload and that any diagnostics stay on `stderr`. [Source: _bmad-output/planning-artifacts/architecture.md - Format Patterns]
- Keep end-to-end tests repo-relative and machine-independent, following the Story 1.1 fix that removed hardcoded developer-specific cache paths.

### Git Intelligence Summary

- Git history currently provides only one commit, `Initial commit`, so commit-level intelligence is limited.
- The relevant implementation baseline for this story is therefore the current scaffold already present in the working tree plus the completed Story 1.1 artifact, not a rich multi-commit history of prior repository-registration work.
- Because there is no meaningful historical implementation of repository registration yet, Story 1.2 should establish the first durable pattern for:
  - thin Typer command modules
  - runtime-path provisioning through `runtime.py`
  - SQLAlchemy Core + Alembic persistence setup
  - pytest coverage across unit, integration, and CLI layers

### Latest Tooling Notes

- The official uv docs continue to treat `uv init` and `uv run` as the primary project workflow, and `uv run` ensures the project environment stays up to date before executing commands. Keep uv as the only supported local workflow in this story. [Source: https://docs.astral.sh/uv/concepts/projects/init/; https://docs.astral.sh/uv/guides/projects/]
- Typer release notes now extend past the scaffold's `0.20.x` line, but the project architecture explicitly selected Typer `0.20.0`. Do not silently jump to a newer minor while implementing Story 1.2 unless the architecture is updated intentionally. [Source: https://typer.tiangolo.com/release-notes/]
- The SQLAlchemy 2.0 documentation currently lists newer 2.0 patch releases than the architecture-pinned `2.0.44`. Stay on the architecture-approved `2.0.x` Core style for this story and avoid ORM-specific design drift. [Source: https://docs.sqlalchemy.org/en/20/changelog/changelog_20.html; https://docs.sqlalchemy.org/en/20/core/metadata.html]
- Alembic documentation has advanced beyond the architecture-pinned `1.17.2`, but the architectural requirement remains "Alembic-managed schema evolution." Introduce migrations in a way that respects the pinned architecture instead of mixing migration strategies. [Source: https://alembic.sqlalchemy.org/en/latest/changelog.html]
- Pydantic documentation continues to use the `BaseModel` + `ConfigDict` style already present in the scaffold. Extend that existing pattern for repository DTOs and configuration rather than introducing a second validation approach. [Source: https://docs.pydantic.dev/changelog/]
- Python `3.13.12` remains the architecture baseline carried forward from Story 1.1. Do not relax the runtime requirement while adding persistence or CLI behavior in this story. [Source: https://peps.python.org/pep-0719/]

### Project Context Reference

- No `project-context.md` file was found in the repository, so this story relies on the PRD, architecture, epics, and Story 1.1 artifact as the authoritative guidance set.
- No separate UX document was found, and no UI-specific behavior is expected beyond clear CLI output.

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Epic 1 / Story 1.2 / Story 1.3]
- [Source: _bmad-output/planning-artifacts/prd.md - Product Scope; User Journeys; Repository Ingestion & Content Structuring; Security & Data Handling; Reliability & Reproducibility]
- [Source: _bmad-output/planning-artifacts/architecture.md - Core Architectural Decisions; Data Architecture; API & Communication Patterns; Structure Patterns; Format Patterns; Project Structure & Boundaries]
- [Source: _bmad-output/planning-artifacts/implementation-readiness-report-2026-03-13.md]
- [Source: _bmad-output/implementation-artifacts/1-1-set-up-initial-project-from-starter-template.md]
- [Source: pyproject.toml]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/runtime.py]
- [Source: src/codeman/cli/app.py]
- [Source: src/codeman/cli/repo.py]
- [Source: src/codeman/cli/common.py]
- [Source: src/codeman/config/models.py]
- [Source: src/codeman/contracts/common.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: tests/unit/cli/test_app.py]
- [Source: tests/e2e/test_cli_help.py]
- [Source: README.md]
- [Source: https://docs.astral.sh/uv/concepts/projects/init/]
- [Source: https://docs.astral.sh/uv/guides/projects/]
- [Source: https://typer.tiangolo.com/release-notes/]
- [Source: https://docs.sqlalchemy.org/en/20/changelog/changelog_20.html]
- [Source: https://docs.sqlalchemy.org/en/20/core/metadata.html]
- [Source: https://alembic.sqlalchemy.org/en/latest/changelog.html]
- [Source: https://docs.pydantic.dev/changelog/]
- [Source: https://peps.python.org/pep-0719/]

## Story Completion Status

- Status set to `done`.
- Code review findings resolved and repository registration implementation validated again with full regression coverage.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Implementation Plan

- Validate and canonicalize the requested repository path before any runtime or persistence side effects.
- Provision the `.codeman/` runtime workspace, apply Alembic migrations against a runtime-resolved SQLite database, and persist repository metadata through SQLAlchemy Core.
- Expose the use case through a thin `repo register` Typer command with stable text/JSON output and dedicated tests across unit, integration, CLI, and end-to-end levels.

### Debug Log References

- Red phase: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev pytest -q tests/unit/test_runtime.py tests/unit/application/test_register_repository.py tests/unit/cli/test_repo.py tests/integration/persistence/test_repository_registration.py`
- Dependency sync: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv sync --group dev`
- Targeted validation: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev pytest -q tests/unit/test_runtime.py tests/unit/application/test_register_repository.py tests/unit/cli/test_repo.py tests/integration/persistence/test_repository_registration.py`
- Full regression: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev pytest -q`
- Lint: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev ruff check`
- Format check: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev ruff format --check`
- Review-fix validation: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev pytest -q tests/unit/application/test_register_repository.py tests/unit/cli/test_repo.py tests/integration/persistence/test_repository_registration.py`
- Review-fix regression: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev pytest -q`

### Completion Notes List

- Added repository registration contracts, typed application errors, and a thin `RegisterRepositoryUseCase` that validates/canonicalizes paths before side effects.
- Introduced runtime workspace provisioning plus a runtime-resolved SQLite metadata database path under `.codeman/`.
- Added SQLAlchemy Core persistence and Alembic migrations for the first `repositories` table.
- Implemented `uv run codeman repo register <path>` with human-readable and JSON output modes plus stable non-zero exit mapping for registration failures.
- Added isolated workspace support through `CODEMAN_WORKSPACE_ROOT` for tests and future interface reuse.
- Verified the story with 16 passing pytest tests plus clean Ruff lint/format checks.
- Resolved review finding [P1]: registration now initializes/migrates the metadata store before duplicate lookup, so an existing empty metadata DB no longer crashes the CLI with a traceback.
- Resolved review finding [P2]: added explicit coverage for `not a directory` and `not readable` failure paths, including CLI JSON error mapping.
- Re-verified the story with 21 passing pytest tests plus clean Ruff lint/format checks.

### File List

- README.md
- _bmad-output/implementation-artifacts/1-2-register-a-local-repository.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- alembic.ini
- docs/cli-reference.md
- migrations/env.py
- migrations/script.py.mako
- migrations/versions/202603140040_create_repositories_table.py
- pyproject.toml
- src/codeman/application/ports/__init__.py
- src/codeman/application/ports/metadata_store_port.py
- src/codeman/application/repo/__init__.py
- src/codeman/application/repo/register_repository.py
- src/codeman/bootstrap.py
- src/codeman/cli/common.py
- src/codeman/cli/repo.py
- src/codeman/config/models.py
- src/codeman/contracts/errors.py
- src/codeman/contracts/repository.py
- src/codeman/infrastructure/persistence/__init__.py
- src/codeman/infrastructure/persistence/sqlite/__init__.py
- src/codeman/infrastructure/persistence/sqlite/engine.py
- src/codeman/infrastructure/persistence/sqlite/migrations.py
- src/codeman/infrastructure/persistence/sqlite/repositories/__init__.py
- src/codeman/infrastructure/persistence/sqlite/repositories/repository_repository.py
- src/codeman/infrastructure/persistence/sqlite/tables.py
- src/codeman/runtime.py
- tests/e2e/test_repo_register.py
- tests/integration/persistence/test_repository_registration.py
- tests/unit/application/test_register_repository.py
- tests/unit/cli/test_repo.py
- tests/unit/test_runtime.py
- uv.lock

## Change Log

- 2026-03-14: Story created and marked `ready-for-dev` with architecture, prior-story, git, and tooling context for repository registration.
- 2026-03-14: Implemented repository registration with runtime provisioning, SQLite/Alembic metadata persistence, CLI text/JSON output, and automated tests; story moved to `review`.
- 2026-03-14: Addressed code review findings for empty metadata DB initialization order and missing invalid-path coverage; story moved to `done`.
