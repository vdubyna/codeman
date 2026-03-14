# Story 1.3: Create a Normalized Repository Snapshot

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want to create an immutable snapshot of a registered repository,
so that indexing and later evaluation runs are attributable to a specific repository state.

## Acceptance Criteria

1. Given a registered repository, when I run snapshot creation, then codeman records a snapshot entry with repository identity, timestamp, and revision identity, and writes a normalized snapshot manifest artifact to local storage.
2. Given a repository without resolvable Git metadata, when snapshot creation runs, then codeman still creates a usable snapshot using a deterministic fallback identity strategy, and marks the revision source clearly in stored metadata.

## Tasks / Subtasks

- [x] Introduce the snapshot creation use case, contracts, and error mapping. (AC: 1, 2)
  - [x] Extend the existing repository-ingestion contract layer with snapshot request/result DTOs and the minimal new error codes needed for repository lookup and snapshot creation failures.
  - [x] Add `src/codeman/application/repo/create_snapshot.py` as the new use-case entrypoint and keep CLI modules limited to argument parsing plus response formatting.
  - [x] Accept an explicit registered repository selector for the first snapshot command surface, preferably `repository_id`, so snapshot attribution is anchored to metadata-store state instead of ad hoc path re-resolution.

- [x] Add snapshot metadata persistence and artifact-writing boundaries that fit the approved architecture. (AC: 1, 2)
  - [x] Introduce the minimal snapshot-specific persistence port(s) needed without destabilizing the already-working repository registration flow from Story 1.2.
  - [x] Add a new `snapshots` table plus repository lookup support in the SQLite adapter, using SQLAlchemy Core statements and Alembic migrations rather than ORM-heavy models.
  - [x] Persist at minimum snapshot identity, repository identity, created timestamp, revision identity, revision source, and manifest artifact path so later indexing and evaluation runs can attribute work to a specific snapshot.

- [x] Implement deterministic revision identity resolution with clear source labeling. (AC: 1, 2)
  - [x] Add a Git-aware snapshotting adapter under `src/codeman/infrastructure/snapshotting/` that resolves the current revision when local Git metadata is available.
  - [x] When Git metadata is unavailable or unresolved, generate a deterministic fallback revision identity from a normalized repository fingerprint rather than a random UUID or wall-clock-only token.
  - [x] Record a clear `revision_source` value such as `git` or `filesystem_fingerprint` in both persisted metadata and the generated manifest.

- [x] Write a normalized snapshot manifest into the runtime artifact workspace. (AC: 1)
  - [x] Store snapshot manifests under runtime-managed `.codeman/artifacts/` paths, not under `src/` or committed docs directories.
  - [x] Keep the manifest machine-readable and stable, including snapshot ID, repository ID, canonical repository path, creation timestamp, revision identity, revision source, and a manifest schema/version marker.
  - [x] Do not overreach into Story 1.4 by embedding extracted source inventories or chunk payloads in this story's manifest.

- [x] Expose snapshot creation through the CLI and protect Story 1.2 behavior with automated tests. (AC: 1, 2)
  - [x] Add a thin `repo snapshot` command that reuses the shared bootstrap container, response envelopes, and JSON/text output conventions already established for `repo register`.
  - [x] Add unit tests for revision resolution and fallback identity determinism, integration tests for metadata-plus-manifest persistence, and end-to-end CLI tests for happy-path and fallback-path snapshot creation.
  - [x] Re-run existing repository registration tests to prove Story 1.3 does not regress the working registration and runtime-provisioning flow.

## Dev Notes

### Previous Story Intelligence

- Story 1.2 already established the first real repository-ingestion slice: runtime workspace provisioning, Alembic-backed metadata initialization, canonical repository registration, stable JSON/text CLI output, and isolated test workspaces driven by `CODEMAN_WORKSPACE_ROOT`.
- Story 1.2 review feedback fixed an important failure mode where persistence lookups could happen before the metadata store was initialized. Story 1.3 must preserve that ordering discipline for any new snapshot persistence and repository lookup path.
- `repo register` now returns a persisted repository identifier plus the runtime root and metadata database path. Snapshot creation should build on that persisted repository state instead of recreating registration semantics or accepting arbitrary unregistered directories as equivalent input.
- The completed registration flow already uses `get_container(ctx)`, `build_command_meta()`, `emit_json_response()`, SQLAlchemy Core, and Alembic migrations. Story 1.3 should extend those patterns rather than inventing parallel wiring or a second JSON contract style.

### Current Repo State

- `src/codeman/bootstrap.py` currently wires only repository registration dependencies: config, runtime paths, the SQLite repository metadata store, and `RegisterRepositoryUseCase`.
- `src/codeman/cli/repo.py` currently exposes only `repo register`; there is no snapshot command or repository lookup command yet.
- `src/codeman/contracts/repository.py` contains repository registration DTOs only. No snapshot request/result models exist yet.
- `src/codeman/application/ports/metadata_store_port.py` is still repository-registration-specific. Snapshot creation should add the next persistence seam carefully instead of forcing a broad rename unless the refactor is clearly low-risk.
- `src/codeman/infrastructure/persistence/sqlite/tables.py` defines only the `repositories` table, and `src/codeman/infrastructure/persistence/sqlite/repositories/` contains only `repository_repository.py`.
- No `src/codeman/infrastructure/snapshotting/` or `src/codeman/infrastructure/artifacts/` packages exist in the current implementation, even though the architecture reserves those locations.
- Existing automated coverage focuses on runtime helpers and `repo register`; there is no snapshot-specific unit, integration, or end-to-end coverage yet.

### Technical Guardrails

- Keep the public interface CLI-only. Do not introduce HTTP endpoints, MCP runtime behavior, background workers, or hosted-service assumptions in this story. [Source: _bmad-output/planning-artifacts/prd.md - Project Classification; _bmad-output/planning-artifacts/architecture.md - API & Communication Patterns]
- Preserve the modular-monolith boundaries already in use: CLI parses and formats, application orchestrates, infrastructure reads Git/filesystem/SQLite state, and contracts remain the stable serialization boundary. [Source: _bmad-output/planning-artifacts/architecture.md - Architectural Boundaries; Integration Points]
- `bootstrap.py` remains the single composition root. Wire new snapshotting services and adapters there instead of constructing them inside CLI commands or tests. [Source: _bmad-output/planning-artifacts/architecture.md - Component Boundaries]
- Runtime-managed paths must continue to flow through `src/codeman/runtime.py` and config models. Do not hardcode `.codeman/` joins deep inside application or persistence code. [Source: _bmad-output/planning-artifacts/architecture.md - Data Boundaries; File Organization Patterns]
- Continue using the architecture-pinned stack and style already introduced in Story 1.2: Python 3.13.x, Typer 0.20.0 command surfaces, Pydantic 2.12.5 DTO/config models, SQLAlchemy Core 2.0.44 persistence, and Alembic-managed migrations. [Source: _bmad-output/planning-artifacts/architecture.md - Technical Constraints & Dependencies; Data Architecture]
- Keep snapshotting local-first. Snapshot creation must not send repository contents or metadata to external providers, and the manifest should avoid embedding unnecessary raw source content. [Source: _bmad-output/planning-artifacts/prd.md - Security & Data Handling; _bmad-output/planning-artifacts/architecture.md - Authentication & Security]
- The fallback revision identity must be deterministic for the same repository state. Prefer a normalized filesystem fingerprint aligned with the architecture's content-hash-based snapshot reuse strategy, not a random or timestamp-only identifier. [Source: _bmad-output/planning-artifacts/architecture.md - Caching Strategy; _bmad-output/planning-artifacts/prd.md - Reliability & Reproducibility]
- Mark revision provenance explicitly. A later benchmark or indexing run must be able to tell whether a snapshot came from Git HEAD or from a fallback fingerprint without reverse-engineering the manifest. [Source: _bmad-output/planning-artifacts/epics.md - Story 1.3; _bmad-output/planning-artifacts/architecture.md - Decision Priority Analysis]
- Keep the scope bounded to snapshot identity and manifesting. Supported-file extraction, parser selection, and chunk generation belong to Stories 1.4 and 1.5 and should not be implemented here. [Source: _bmad-output/planning-artifacts/epics.md - Story 1.4; Story 1.5]
- Prefer a small adapter around local Git metadata or the `git` CLI for HEAD resolution instead of adding a heavyweight Git dependency unless a concrete blocker appears.

### File / Structure Guidance

- Preferred new or expanded files for this story:
  - `src/codeman/application/repo/create_snapshot.py`
  - `src/codeman/application/ports/snapshot_port.py`
  - `src/codeman/application/ports/artifact_store_port.py`
  - `src/codeman/bootstrap.py`
  - `src/codeman/cli/repo.py`
  - `src/codeman/contracts/repository.py`
  - `src/codeman/contracts/errors.py`
  - `src/codeman/infrastructure/persistence/sqlite/tables.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/snapshot_repository.py`
  - `src/codeman/infrastructure/snapshotting/__init__.py`
  - `src/codeman/infrastructure/snapshotting/git_revision_resolver.py`
  - `src/codeman/infrastructure/snapshotting/snapshot_manifest_builder.py`
  - `src/codeman/infrastructure/artifacts/__init__.py`
  - `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py`
  - `migrations/versions/<timestamp>_create_snapshots_table.py`
- Keep the CLI surface additive to the existing command tree. A good initial shape is:
  - `uv run codeman repo snapshot <repository-id>`
  - `uv run codeman repo snapshot <repository-id> --output-format json`
- A pragmatic manifest location is `.codeman/artifacts/snapshots/<snapshot-id>/manifest.json` or an equivalently deterministic path under `.codeman/artifacts/`; choose one pattern and keep it stable.
- Reuse the existing response envelope pattern instead of inventing a command-specific JSON shape. Successful snapshot output should at least expose snapshot ID, repository ID, revision identity, revision source, manifest path, and creation timestamp.
- If repository lookup-by-ID support is missing in the current metadata adapter, add it there rather than bypassing persistence with direct filesystem assumptions.
- Avoid broad churn in Story 1.2 files. Extend the working registration implementation carefully and preserve existing imports, test hooks, and runtime-environment behavior unless the refactor clearly pays for itself.

### Testing Guidance

- Use pytest throughout and keep the same workspace-isolation pattern already used by Story 1.2 (`tmp_path` plus `CODEMAN_WORKSPACE_ROOT` for e2e flows). [Source: _bmad-output/implementation-artifacts/1-2-register-a-local-repository.md - Testing Guidance]
- Add unit coverage for deterministic fallback identity generation. The same repository contents should yield the same fallback revision identity regardless of file traversal order.
- Add unit coverage for Git-resolution behavior, including the branch where Git metadata is unavailable or unresolved and the code must fall back cleanly without crashing.
- Add integration tests proving that a successful snapshot both persists a metadata row and writes a manifest artifact under the resolved runtime workspace.
- Add a negative-path test for an unknown or unregistered repository selector so the CLI exits non-zero with a stable, user-safe message and no partial snapshot row.
- Add an end-to-end test that registers a repository first, then creates a snapshot through `uv run codeman ...`, proving the command chain works in a real uv invocation.
- Re-run existing registration tests or an appropriate regression subset to ensure Story 1.3 does not break `repo register` success/failure behavior, metadata initialization, or JSON output guarantees.

### Implementation Notes for the Dev Agent

- Start by extending the metadata boundary just enough to look up an existing registered repository and create a snapshot row; do not redesign the entire persistence layer before the first snapshot works.
- Treat the snapshot manifest as an explicit artifact, not as an implementation detail hidden inside the database. The architecture expects filesystem artifact storage to complement SQLite metadata, not replace it.
- Keep manifest contents normalized and serializable so future indexing steps can consume them directly without reparsing human-oriented console output.
- Exclude runtime-managed directories such as `.codeman/` and VCS internals such as `.git/` from any fallback fingerprinting algorithm so the snapshot identity reflects the repository state, not the tool's own outputs.
- Be deliberate about timestamp handling and timezone awareness. The current repository registration flow already uses UTC-aware timestamps; snapshot metadata should match that standard.

### Project Context Reference

- No `project-context.md` file was found in the repository, so the authoritative guidance remains the PRD, architecture, epics, and the completed Story 1.2 artifact.
- No separate UX design artifact was found, and this story has only CLI output requirements.

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Epic 1 / Story 1.2 / Story 1.3 / Story 1.4]
- [Source: _bmad-output/planning-artifacts/prd.md - Executive Summary; Product Scope; User Journeys; Domain-Specific Requirements; Non-Functional Requirements]
- [Source: _bmad-output/planning-artifacts/architecture.md - Data Architecture; Authentication & Security; API & Communication Patterns; Project Structure & Boundaries; Requirements to Structure Mapping; Integration Points; File Organization Patterns]
- [Source: _bmad-output/implementation-artifacts/1-2-register-a-local-repository.md]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/cli/repo.py]
- [Source: src/codeman/cli/common.py]
- [Source: src/codeman/config/models.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: src/codeman/contracts/repository.py]
- [Source: src/codeman/runtime.py]
- [Source: src/codeman/application/ports/metadata_store_port.py]
- [Source: src/codeman/application/repo/register_repository.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/tables.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/repository_repository.py]
- [Source: docs/cli-reference.md]
- [Source: tests/unit/cli/test_repo.py]
- [Source: tests/e2e/test_repo_register.py]

## Story Completion Status

- Status set to `done`.
- Snapshot creation and review follow-up fixes are implemented and validated with full regression, lint, and format checks.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Implementation Plan

- Extend repository-ingestion contracts, persistence, and bootstrap wiring so snapshot creation can resolve a registered repository and persist snapshot metadata cleanly.
- Implement Git-first revision resolution with a deterministic filesystem-fingerprint fallback, then write a normalized manifest artifact under `.codeman/artifacts/`.
- Expose the use case through a thin `repo snapshot` CLI command with text/JSON output and add unit, integration, and e2e coverage without regressing `repo register`.

### Debug Log References

- Red phase: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev pytest -q tests/unit/application/test_create_snapshot.py tests/unit/infrastructure/test_git_revision_resolver.py tests/unit/cli/test_repo.py tests/integration/persistence/test_snapshot_creation.py tests/e2e/test_repo_snapshot.py`
- Targeted green phase: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev pytest -q tests/unit/application/test_create_snapshot.py tests/unit/infrastructure/test_git_revision_resolver.py tests/unit/cli/test_repo.py tests/integration/persistence/test_snapshot_creation.py tests/e2e/test_repo_snapshot.py`
- Full regression: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev pytest -q`
- Lint: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev ruff check`
- Format: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev ruff format src/codeman/infrastructure/artifacts/__init__.py src/codeman/infrastructure/artifacts/filesystem_artifact_store.py src/codeman/infrastructure/snapshotting/__init__.py src/codeman/infrastructure/snapshotting/git_revision_resolver.py tests/integration/persistence/test_snapshot_creation.py tests/unit/application/test_create_snapshot.py tests/unit/infrastructure/test_git_revision_resolver.py`
- Format check: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev ruff format --check`
- Review-fix validation: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev pytest -q tests/unit/infrastructure/test_git_revision_resolver.py tests/unit/cli/test_repo.py`
- Review-fix regression: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev pytest -q`

### Completion Notes List

- Added snapshot DTOs, error contracts, and the `CreateSnapshotUseCase` so registered repositories can produce immutable snapshot records and normalized manifest artifacts.
- Implemented SQLite snapshot persistence, repository lookup by ID, and a new Alembic migration for the `snapshots` table.
- Added a Git-first revision resolver with deterministic `filesystem_fingerprint` fallback that ignores runtime-managed `.codeman/` artifacts.
- Added a filesystem artifact store and a thin `repo snapshot` CLI command with text/JSON output that reuses the existing envelope and bootstrap patterns.
- Added unit, integration, and end-to-end coverage for snapshot creation while preserving Story 1.2 registration behavior.
- Resolved review findings for missing `git` binary fallback, dirty Git worktree attribution, and incorrect `repo.snapshot` JSON failure metadata.
- Verified the story with 33 passing pytest tests, clean `ruff check`, and clean `ruff format --check`.

### File List

- _bmad-output/implementation-artifacts/1-3-create-a-normalized-repository-snapshot.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- migrations/versions/202603140815_create_snapshots_table.py
- src/codeman/application/ports/artifact_store_port.py
- src/codeman/application/ports/metadata_store_port.py
- src/codeman/application/ports/snapshot_port.py
- src/codeman/application/repo/create_snapshot.py
- src/codeman/bootstrap.py
- src/codeman/cli/repo.py
- src/codeman/contracts/errors.py
- src/codeman/contracts/repository.py
- src/codeman/infrastructure/artifacts/__init__.py
- src/codeman/infrastructure/artifacts/filesystem_artifact_store.py
- src/codeman/infrastructure/persistence/sqlite/repositories/repository_repository.py
- src/codeman/infrastructure/persistence/sqlite/repositories/snapshot_repository.py
- src/codeman/infrastructure/persistence/sqlite/tables.py
- src/codeman/infrastructure/snapshotting/__init__.py
- src/codeman/infrastructure/snapshotting/git_revision_resolver.py
- tests/e2e/test_repo_snapshot.py
- tests/integration/persistence/test_snapshot_creation.py
- tests/unit/application/test_create_snapshot.py
- tests/unit/cli/test_repo.py
- tests/unit/infrastructure/test_git_revision_resolver.py

## Change Log

- 2026-03-14: Story created and marked `ready-for-dev` with architecture, prior-story, persistence, runtime, and testing guidance for normalized snapshot creation.
- 2026-03-14: Implemented `repo snapshot` with SQLite snapshot persistence, normalized manifest artifacts, Git/fingerprint revision resolution, and unit/integration/e2e coverage; story moved to `review`.
- 2026-03-14: Addressed code review findings for git-binary fallback, dirty worktree attribution, and snapshot JSON error metadata; story moved to `done`.
