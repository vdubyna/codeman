# Story 1.4: Extract Supported Source Files into a Source Inventory

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want codeman to identify supported source files from a snapshot,
so that only relevant PHP, JavaScript, HTML, and Twig content enters retrieval indexing.

## Acceptance Criteria

1. Given a completed snapshot, when source extraction runs, then codeman identifies supported files, classifies them by target language, and stores source file metadata for downstream indexing, and preserves enough path and identity information to trace later chunks back to their origin.
2. Given unsupported, ignored, or binary files in the snapshot, when extraction runs, then those files are skipped safely, and diagnostics summarize the exclusion without exposing unnecessary file contents.

## Tasks / Subtasks

- [x] Introduce a snapshot-anchored source-inventory use case, contracts, and CLI command. (AC: 1, 2)
  - [x] Add source-inventory DTOs under `src/codeman/contracts/repository.py` or a focused companion contract module, including at minimum `ExtractSourceFilesRequest`, `SourceFileRecord`, `ExtractSourceFilesResult`, and a small diagnostics summary payload.
  - [x] Create `src/codeman/application/indexing/extract_source_files.py` as the orchestration entrypoint and keep the CLI layer limited to argument parsing, envelope formatting, and exit handling.
  - [x] Add the first real `index` command surface, preferably `uv run codeman index extract-sources <snapshot-id>` with `--output-format json`, reusing `get_container(ctx)`, `build_command_meta()`, and the existing success/failure envelope patterns.
  - [x] Introduce only the minimal new error codes needed for snapshot lookup, snapshot/source mismatch, and extraction failures so later Epic 5 diagnostics can extend the same contract instead of replacing it.

- [x] Add metadata persistence for extracted source files without collapsing boundaries. (AC: 1)
  - [x] Introduce a focused source-inventory persistence port, similar in scope to Story 1.3's snapshot port, instead of bloating the existing repository-only metadata protocol.
  - [x] Add a `source_files` table plus a SQLite adapter under `src/codeman/infrastructure/persistence/sqlite/repositories/` using SQLAlchemy Core and Alembic migrations, not ORM-heavy models.
  - [x] Persist enough metadata for later chunk traceability and cache keys: deterministic source-file identifier, `snapshot_id`, `repository_id`, normalized relative path, detected language, content hash, file size, and discovery timestamp.
  - [x] Enforce a uniqueness boundary at least on `snapshot_id + relative_path` so repeated extraction cannot silently create duplicate source-file rows for the same immutable snapshot.

- [x] Implement deterministic source scanning, classification, and snapshot fidelity checks. (AC: 1, 2)
  - [x] Add a concrete local-repository scanner under `src/codeman/infrastructure/snapshotting/local_repository_scanner.py` or an equivalently scoped indexing adapter that walks only inside the registered repository root.
  - [x] Resolve the target repository through persisted snapshot metadata first, then verify the live repository state still matches the snapshot revision identity before trusting current files; if the current state no longer matches the snapshot, fail safely and direct the operator to create a new snapshot instead of extracting misleading data.
  - [x] Classify supported files into the four MVP languages and document the exact extension policy in code and tests; at minimum support PHP, JavaScript, HTML, and Twig, including compound Twig template suffixes that still end in `.twig`.
  - [x] Compute deterministic content hashes for supported files during extraction so later parser/chunk caches can key off stable file identity without rereading ambiguous state.
  - [x] Treat symlinks, unreadable files, binary files, and explicitly ignored paths as non-indexable in this story unless they can be proven safe to process without escaping the repository root.

- [x] Produce safe operator diagnostics and a downstream-friendly inventory result. (AC: 2)
  - [x] Return concise counts for persisted files by language plus skipped counts by reason such as `ignored`, `unsupported_extension`, `binary`, `unreadable`, or `snapshot_mismatch`.
  - [x] Keep diagnostics path-oriented and summary-oriented; do not emit raw file contents, long excerpts, or binary payload fragments in default output.
  - [x] Preserve JSON-mode discipline: `stdout` contains only the final success/failure envelope, while any human diagnostics stay on `stderr`.
  - [x] Update `docs/cli-reference.md` once the `index extract-sources` interface is finalized.

- [x] Add automated coverage and realistic mixed-stack fixtures for the new indexing slice. (AC: 1, 2)
  - [x] Add unit tests for language classification, binary detection, ignore behavior, deterministic source-file identifiers, and snapshot/source mismatch handling.
  - [x] Add integration tests that prove successful extraction persists source-file metadata rows and that rerunning extraction for the same snapshot does not create duplicates.
  - [x] Add an end-to-end CLI test that registers a repository, creates a snapshot, runs `index extract-sources`, and verifies both human-readable and JSON output paths.
  - [x] Introduce a small fixture repository under `tests/fixtures/repositories/` containing representative PHP, JavaScript, HTML, Twig, unsupported, ignored, and binary files so Story 1.4 validates the actual mixed-stack target rather than a synthetic single-language case.

## Dev Notes

### Previous Story Intelligence

- Story 1.3 established the core pattern this story must extend: thin Typer commands, application-layer orchestration, SQLAlchemy Core + Alembic persistence, runtime-managed artifact paths, and isolated temp-workspace tests.
- Snapshot creation currently persists only immutable metadata plus a manifest artifact. It does not materialize a frozen copy of the repository tree. Story 1.4 therefore must not silently treat the live working tree as a trustworthy snapshot without first checking that the current repository state still matches the stored snapshot identity.
- Story 1.3 also introduced `FilesystemArtifactStore`, `SqliteSnapshotMetadataStore`, `GitRevisionResolver`, and snapshot-oriented contracts. Reuse those seams where they fit instead of creating parallel snapshot lookup or filesystem logic.
- The most recent review fixes reinforced two behaviors worth preserving here: fail safely when environment assumptions break, and keep JSON error metadata aligned with the command actually being executed.

### Current Repo State

- `src/codeman/cli/index.py` is still only a Typer group placeholder; there is no indexing command surface yet.
- `src/codeman/bootstrap.py` currently wires repository registration plus snapshot creation only. There is no indexing use case, scanner adapter, or source-file persistence in the container.
- `src/codeman/application/` has no `indexing/` package yet, even though the architecture reserves it for extraction, chunking, embedding, and index-build orchestration.
- `src/codeman/application/ports/snapshot_port.py` and `src/codeman/infrastructure/persistence/sqlite/repositories/snapshot_repository.py` support snapshot creation only; there is no snapshot lookup path yet.
- `src/codeman/contracts/repository.py` has repository and snapshot DTOs only; there is no source-file metadata DTO or extraction result shape.
- `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py` currently writes only snapshot manifests under `.codeman/artifacts/snapshots/<snapshot-id>/manifest.json`.
- The runtime SQLite schema currently contains `repositories` and `snapshots` tables only. No `source_files` table or source-inventory repository exists.
- There are no parser adapters, chunkers, or `tests/fixtures/repositories/` assets yet, so Story 1.4 is the first place where mixed-language repository fixtures should appear.

### Technical Guardrails

- Keep the public interface CLI-only. This story must not introduce HTTP endpoints, MCP transport behavior, background workers, or hosted-service assumptions. [Source: _bmad-output/planning-artifacts/prd.md - Project Classification; _bmad-output/planning-artifacts/architecture.md - API & Communication Patterns]
- Preserve the modular-monolith split already working in the repository: CLI parses and formats, application orchestrates, infrastructure scans/filesystem/SQLite details, and contracts remain the stable boundary DTO layer. [Source: _bmad-output/planning-artifacts/architecture.md - Source Organization; Project Structure & Boundaries]
- `bootstrap.py` remains the single composition root. Wire extraction services there instead of constructing scanners, engines, or repositories inside `src/codeman/cli/index.py` or tests. [Source: _bmad-output/planning-artifacts/architecture.md - Project Structure & Boundaries]
- Keep runtime path ownership inside `src/codeman/runtime.py` and existing config/runtime plumbing. Do not scatter `.codeman/` path joins across extraction code. [Source: _bmad-output/planning-artifacts/architecture.md - Data Flow; File Organization Patterns]
- Stay on the architecture-approved foundation already present in the codebase: Python 3.13.x, Typer 0.20.x command patterns, Pydantic 2.12.x DTO/config models, SQLAlchemy Core 2.0.x persistence, and Alembic-managed migrations. [Source: _bmad-output/planning-artifacts/epics.md - Additional Requirements; _bmad-output/planning-artifacts/architecture.md - Core Architectural Decisions]
- Source extraction is metadata-first in this story. Do not parse ASTs, create chunks, build indexes, or introduce embedding providers here; those belong to Stories 1.5 and later. [Source: _bmad-output/planning-artifacts/epics.md - Story 1.5; Story 1.6]
- Preserve future re-index and cache needs by storing deterministic content hashes now. Later parser, chunk, and embedding reuse depends on content-hash identity rather than path-only heuristics. [Source: _bmad-output/planning-artifacts/epics.md - Additional Requirements; _bmad-output/planning-artifacts/architecture.md - Caching Strategy]
- Persist normalized relative paths, not repository-machine-specific absolute paths, as the main source-file identity input. Relative paths plus snapshot identity are what later chunk records and benchmark traces will need. [Source: _bmad-output/planning-artifacts/epics.md - Story 1.4; _bmad-output/planning-artifacts/architecture.md - Data Architecture]
- Keep extraction local-first and privacy-safe. Unsupported/binary-file diagnostics should summarize reasons and counts without exposing repository contents beyond what is required for operator-safe troubleshooting. [Source: _bmad-output/planning-artifacts/prd.md - Domain-Specific Requirements; _bmad-output/planning-artifacts/architecture.md - Authentication & Security]
- Do not follow symlinks outside the repository root. The safest MVP behavior is to skip symlinked files unless their safety and in-repo target boundaries are proven explicitly. [Source: src/codeman/infrastructure/snapshotting/git_revision_resolver.py]
- If you decide to persist a machine-readable source-inventory artifact or summary in addition to SQLite rows, keep it under `.codeman/artifacts/snapshots/<snapshot-id>/` and extend `FilesystemArtifactStore` rather than writing ad hoc files from application code.

### File / Structure Guidance

- Preferred new or expanded files for this story:
  - `src/codeman/application/indexing/__init__.py`
  - `src/codeman/application/indexing/extract_source_files.py`
  - `src/codeman/application/ports/source_inventory_port.py`
  - `src/codeman/application/ports/snapshot_port.py`
  - `src/codeman/bootstrap.py`
  - `src/codeman/cli/index.py`
  - `src/codeman/contracts/repository.py`
  - `src/codeman/contracts/errors.py`
  - `src/codeman/infrastructure/snapshotting/local_repository_scanner.py`
  - `src/codeman/infrastructure/persistence/sqlite/tables.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/source_file_repository.py`
  - `migrations/versions/<timestamp>_create_source_files_table.py`
  - `docs/cli-reference.md`
  - `tests/fixtures/repositories/mixed_stack_fixture/`
- A pragmatic first CLI surface is:
  - `uv run codeman index extract-sources <snapshot-id>`
  - `uv run codeman index extract-sources <snapshot-id> --output-format json`
- A pragmatic row shape for `source_files` is:
  - `id`
  - `snapshot_id`
  - `repository_id`
  - `relative_path`
  - `language`
  - `content_hash`
  - `byte_size`
  - `created_at`
- Keep `source_files` metadata in SQLite and keep raw file contents out of the database. Chunk payload artifacts, parser outputs, and later retrieval artifacts belong in the filesystem/runtime layer, not as text blobs in `metadata.sqlite3`.
- If snapshot lookup support is missing in the current SQLite adapter, add it there rather than bypassing persistence with direct manifest-path guessing.

### Testing Guidance

- Use pytest across unit, integration, and e2e layers and keep the same temp-workspace isolation pattern already used in Stories 1.2 and 1.3. [Source: _bmad-output/implementation-artifacts/1-3-create-a-normalized-repository-snapshot.md - Testing Guidance]
- Add at least one unit test proving deterministic source-file identity and content-hash generation are stable regardless of filesystem traversal order.
- Add explicit coverage for compound Twig filenames such as `*.html.twig` so common template paths are not misclassified or skipped accidentally.
- Add a negative-path test where the repository changes after snapshot creation and extraction refuses to proceed against a stale snapshot instead of inventing trust in mutable live files.
- Add coverage for binary detection and ignored directories without asserting on sensitive file contents; the test should validate summary counts and reasons rather than content leakage.
- Add integration coverage that the `source_files` schema is created via Alembic and that extraction persists metadata tied to the correct `snapshot_id`.
- Add e2e coverage for JSON mode proving `stdout` contains only the final envelope and no progress noise. [Source: _bmad-output/planning-artifacts/architecture.md - Format Patterns]

### Git Intelligence Summary

- The most recent implementation commit, `0230d47`, extended the project through new ports, a new use case, a SQLite repository adapter, CLI wiring, and dedicated unit/integration/e2e coverage. Story 1.4 should follow that same additive pattern instead of introducing a second implementation style.
- Recent history shows a consistent preference for focused new modules over broad rewrites: Story 1.3 added `snapshot_port.py`, `create_snapshot.py`, `snapshot_repository.py`, and targeted tests rather than renaming the whole persistence layer. Use that same restraint for source inventory.
- The current repository has already standardized on:
  - thin command modules under `src/codeman/cli/`
  - explicit use cases under `src/codeman/application/`
  - SQLAlchemy Core repositories under `src/codeman/infrastructure/persistence/sqlite/repositories/`
  - mirrored tests under `tests/unit/`, `tests/integration/`, and `tests/e2e/`

### Project Context Reference

- No `project-context.md` file was found in the repository, so the authoritative guidance remains the PRD, architecture, epics, sprint status, and the completed Stories 1.2 and 1.3 artifacts.
- No separate UX design artifact exists for this project, and Story 1.4 remains a CLI/data-flow story with no dedicated UI requirements.

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Epic 1 / Story 1.4 / Story 1.5 / Story 1.6 / Additional Requirements]
- [Source: _bmad-output/planning-artifacts/prd.md - Executive Summary; Product Scope; User Journeys; Domain-Specific Requirements; Risk Mitigations]
- [Source: _bmad-output/planning-artifacts/architecture.md - Core Architectural Decisions; Data Architecture; API & Communication Patterns; Project Structure & Boundaries; Data Flow; File Organization Patterns]
- [Source: _bmad-output/implementation-artifacts/1-3-create-a-normalized-repository-snapshot.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/cli/app.py]
- [Source: src/codeman/cli/index.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: src/codeman/contracts/repository.py]
- [Source: src/codeman/application/ports/metadata_store_port.py]
- [Source: src/codeman/application/ports/snapshot_port.py]
- [Source: src/codeman/application/repo/create_snapshot.py]
- [Source: src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/tables.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/snapshot_repository.py]
- [Source: src/codeman/infrastructure/snapshotting/git_revision_resolver.py]
- [Source: docs/cli-reference.md]
- [Source: git log --oneline -5]
- [Source: git show --stat --summary 0230d47]
- [Source: git show --stat --summary ca53be4]

## Story Completion Status

- Status set to `done`.
- Snapshot-backed source inventory extraction is implemented and validated with full regression and lint checks.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Implementation Plan

- Extend the existing snapshot/repository contracts and bootstrap wiring with a dedicated source-inventory use case, lookup path, and persistence boundary.
- Implement local scanning plus snapshot fidelity verification so extraction only persists supported PHP, JavaScript, HTML, and Twig files from a still-matching repository state.
- Add SQLite persistence, CLI output handling, mixed-stack fixtures, and automated coverage that proves diagnostics, deduplication, and JSON discipline.

### Debug Log References

- Targeted lint: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev ruff check src tests`
- Targeted validation: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev pytest -q tests/unit/application/test_extract_source_files.py tests/unit/infrastructure/test_local_repository_scanner.py tests/unit/cli/test_index.py tests/integration/persistence/test_source_inventory_extraction.py tests/e2e/test_index_extract_sources.py`
- Review-fix validation: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev pytest -q tests/unit/infrastructure/test_local_repository_scanner.py tests/integration/persistence/test_source_inventory_extraction.py`
- Full regression: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev pytest -q tests`

### Completion Notes List

- Added source-inventory DTOs, error codes, and the `ExtractSourceFilesUseCase`, then wired `index extract-sources` through the shared bootstrap/container and existing success/failure envelopes.
- Added snapshot lookup support, a dedicated source-inventory port and SQLite repository, and an Alembic migration for `source_files` with deterministic source-file identifiers and snapshot/path deduplication.
- Implemented `LocalRepositoryScanner` with supported-language classification, deterministic content hashes, binary detection, safe ignored-path handling, and stale snapshot protection before extraction proceeds.
- Updated runtime migration helpers and Alembic environment wiring so JSON mode stays clean while migrations remain automatic.
- Added mixed-stack repository fixtures plus unit, integration, CLI, and end-to-end coverage for classification, diagnostics, persistence, deduplication, and JSON/text output behavior.
- Resolved review findings by making Git-backed scans honor ignored files and by counting ignored diagnostics per skipped file instead of per directory.
- Verified the story with 47 passing pytest tests and clean `ruff check`.
- Code review issues are resolved and the story is ready for release tracking as `done`.

### File List

- _bmad-output/implementation-artifacts/1-4-extract-supported-source-files-into-a-source-inventory.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- docs/cli-reference.md
- migrations/env.py
- migrations/versions/202603140930_create_source_files_table.py
- src/codeman/application/indexing/__init__.py
- src/codeman/application/indexing/extract_source_files.py
- src/codeman/application/ports/snapshot_port.py
- src/codeman/application/ports/source_inventory_port.py
- src/codeman/bootstrap.py
- src/codeman/cli/index.py
- src/codeman/contracts/errors.py
- src/codeman/contracts/repository.py
- src/codeman/infrastructure/persistence/sqlite/migrations.py
- src/codeman/infrastructure/persistence/sqlite/repositories/snapshot_repository.py
- src/codeman/infrastructure/persistence/sqlite/repositories/source_file_repository.py
- src/codeman/infrastructure/persistence/sqlite/tables.py
- src/codeman/infrastructure/snapshotting/local_repository_scanner.py
- tests/e2e/test_index_extract_sources.py
- tests/fixtures/repositories/mixed_stack_fixture/README.md
- tests/fixtures/repositories/mixed_stack_fixture/assets/app.js
- tests/fixtures/repositories/mixed_stack_fixture/assets/logo.bin
- tests/fixtures/repositories/mixed_stack_fixture/public/index.html
- tests/fixtures/repositories/mixed_stack_fixture/src/Controller/HomeController.php
- tests/fixtures/repositories/mixed_stack_fixture/templates/page.html.twig
- tests/fixtures/repositories/mixed_stack_fixture/vendor/ignored.php
- tests/integration/persistence/test_source_inventory_extraction.py
- tests/unit/application/test_extract_source_files.py
- tests/unit/cli/test_index.py
- tests/unit/infrastructure/test_local_repository_scanner.py

## Change Log

- 2026-03-14: Story created and marked `ready-for-dev` with architecture, persistence, runtime, and testing guidance for source inventory extraction.
- 2026-03-14: Implemented `index extract-sources` with snapshot validation, deterministic local source scanning, SQLite `source_files` persistence, mixed-stack fixtures, and unit/integration/e2e coverage; story moved to `review`.
- 2026-03-14: Fixed code review findings for Git-aware ignored-path filtering and accurate ignored-file diagnostics; story moved to `done`.
