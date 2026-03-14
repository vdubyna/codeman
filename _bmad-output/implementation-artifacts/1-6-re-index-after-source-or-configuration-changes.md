# Story 1.6: Re-index After Source or Configuration Changes

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want to re-index after source or configuration changes,
so that the repository stays current without blindly rebuilding everything every time.

## Acceptance Criteria

1. Given an already indexed repository, when source files or indexing configuration change, then codeman can run a re-index flow that detects what changed and creates a new attributable run outcome, and reuses prior artifacts where change detection allows it.
2. Given a re-index run completes, when I inspect the result metadata, then I can see which repository state and configuration produced the new output, and whether work was rebuilt or reused from cache.

## Tasks / Subtasks

- [x] Introduce the re-index orchestration, DTOs, and CLI surface. (AC: 1, 2)
  - [x] Add focused request/result and diagnostics contracts, preferably in `src/codeman/contracts/reindexing.py`, keeping the current repository and chunk contracts readable.
  - [x] Create `src/codeman/application/repo/reindex_repository.py` as the orchestration entrypoint and keep `src/codeman/cli/index.py` limited to argument parsing, progress reporting, envelopes, and exit handling.
  - [x] Wire the use case through `src/codeman/bootstrap.py` and expose `uv run codeman index reindex <repository-id>` with `--output-format json`.
  - [x] Add only the minimal new stable errors needed for re-indexing, most likely a dedicated failure for "no indexed baseline exists yet" plus a generic re-index failure.

- [x] Add baseline discovery and minimal change-detection primitives without pulling Epic 3 forward. (AC: 1, 2)
  - [x] Teach snapshot persistence to discover the most recent usable baseline for a repository, meaning the latest snapshot that has both extracted source inventory and generated chunks.
  - [x] Introduce a narrow indexing-configuration fingerprint builder for the policies implemented today: source discovery policy version, chunk serialization version, registered parser/chunker policy version(s), and any current CLI-visible indexing knobs.
  - [x] Record both the previous and current fingerprint in the re-index result so runs can be classified deterministically as `no_change`, `source_changed`, `config_changed`, or `source_and_config_changed`.
  - [x] Keep this fingerprint builder deliberately narrow and local to indexing; do not implement the full layered configuration system from Epic 3 in this story.

- [x] Reuse unchanged artifacts safely while keeping snapshots immutable. (AC: 1, 2)
  - [x] When the repository revision or config fingerprint changes, create a fresh snapshot and fresh source inventory for the current repository state instead of mutating the previous snapshot in place.
  - [x] Compare the new source inventory to the previous indexed snapshot by normalized relative path, language, and content hash to identify unchanged, changed, added, removed, and newly unsupported files.
  - [x] Reuse unchanged chunk artifacts only when both source content hash and indexing fingerprint remain compatible; clone or re-materialize prior payload artifacts into the new snapshot namespace and persist new chunk rows with new snapshot-local identifiers.
  - [x] Rebuild chunks only for changed/new files, or for all files when a config fingerprint change invalidates prior chunk reuse.
  - [x] On true no-op runs, create a new attributable run outcome without duplicating snapshots or chunk artifacts.

- [x] Persist attributable re-index outcomes and operator-safe diagnostics. (AC: 1, 2)
  - [x] Add focused persistence for re-index outcomes, preferably a narrow `reindex_runs` table/repository, capturing run id, repository id, previous snapshot id, resulting snapshot id, change reason, previous/current config fingerprint, reuse/rebuild counters, and creation timestamp.
  - [x] Return summary diagnostics for files and chunks scanned, reused, rebuilt, skipped, removed, or invalidated by config.
  - [x] Preserve CLI contract discipline: `stdout` contains only the final success/failure envelope in JSON mode, while progress lines such as `Re-indexing repository` stay on `stderr`.
  - [x] Update `docs/cli-reference.md` once the command shape and result fields are finalized.

- [x] Extend tests for no-op, partial reuse, and config-driven rebuild behavior. (AC: 1, 2)
  - [x] Add unit coverage for baseline selection, fingerprint stability, change classification, reusable chunk eligibility, and no-op re-index behavior.
  - [x] Add integration coverage that a re-index run persists run metadata, creates a new snapshot only when required, clones reusable chunk payload artifacts correctly, and avoids stale chunk rows for removed files.
  - [x] Add an end-to-end CLI test that registers a repository, builds the initial snapshot/source inventory/chunks, mutates a supported file, runs `index reindex`, and verifies reuse vs rebuild counters in both text and JSON output.
  - [x] Add a second end-to-end or integration test that simulates a config fingerprint change and proves the run rebuilds affected artifacts without mutating the previous snapshot's chunk set.

## Dev Notes

### Previous Story Intelligence

- Story 1.5 established the current indexed baseline for this story: source inventories are persisted per snapshot, chunk payloads live under `.codeman/artifacts/snapshots/<snapshot-id>/chunks/`, and chunk metadata is already stored in SQLite with source references, spans, strategy, and content hash.
- Story 1.5 also confirmed the project delivery pattern that should continue here: thin Typer commands, one primary application use case per file, SQLAlchemy Core repositories, Alembic-managed schema changes, and runtime-managed artifacts under `.codeman/`.
- Chunk identifiers are deterministic but snapshot-local because `build_chunk_id()` hashes `source_file_id` plus strategy/span metadata. Cross-snapshot reuse therefore must create new chunk ids for the new snapshot instead of copying old ids blindly.
- The latest Story 1.4 and 1.5 review fixes reinforced two behaviors worth preserving here: use Git-aware repository discovery rules instead of inventing a parallel file-walk policy, and keep operator diagnostics accurate without leaking repository content.

### Current Repo State

- `src/codeman/application/repo/` contains registration and snapshot creation only. There is no re-index orchestration yet.
- `src/codeman/cli/index.py` exposes `extract-sources` and `build-chunks`, but there is no refresh or re-index command.
- `src/codeman/application/indexing/build_chunks.py` always operates on the full source inventory of one snapshot. It has no baseline-diff or selective-rebuild mode today.
- `src/codeman/config/models.py` currently models runtime paths only. There is no indexing-configuration fingerprint or policy version model yet.
- `src/codeman/infrastructure/snapshotting/git_revision_resolver.py` resolves clean Git `HEAD` when possible and falls back to a deterministic filesystem fingerprint for dirty or non-Git repositories. This is already compatible with re-index detection and should be reused.
- `src/codeman/infrastructure/snapshotting/local_repository_scanner.py` already produces deterministic per-file `content_hash` values plus Git-aware candidate discovery, which is the right baseline for change detection in this story.
- `src/codeman/infrastructure/persistence/sqlite/repositories/snapshot_repository.py` can fetch one snapshot by id and mark source extraction complete, but it cannot yet list or choose a latest indexed baseline for a repository.
- `src/codeman/application/ports/chunk_store_port.py` and `src/codeman/infrastructure/persistence/sqlite/repositories/chunk_repository.py` can upsert chunk rows, but they do not yet expose lookup helpers for prior chunk reuse.
- `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py` can write snapshot manifests and chunk payloads, but it cannot yet read or clone prior payload artifacts for reuse.
- The current docs and tests cover repository registration, snapshot creation, source extraction, and chunk generation, but there is no re-index contract, no re-index CLI flow, and no reuse-oriented coverage yet.

### Technical Guardrails

- Keep the public interface CLI-only. This story must not introduce HTTP endpoints, MCP behavior, background workers, or daemonized indexing processes. [Source: _bmad-output/planning-artifacts/prd.md - Project Classification; _bmad-output/planning-artifacts/architecture.md - API & Communication Patterns]
- Re-index orchestration should compose the existing snapshot, extraction, and chunk-generation architecture instead of re-implementing repository scanning or chunk serialization inside the CLI handler. [Source: src/codeman/application/repo/create_snapshot.py; src/codeman/application/indexing/extract_source_files.py; src/codeman/application/indexing/build_chunks.py]
- Preserve snapshot immutability. Do not mutate prior snapshot rows, source inventory rows, chunk rows, or payload artifacts in place. Re-indexed outputs must be attributable to a distinct run outcome, and to a new snapshot when source or config changes justify one. [Source: _bmad-output/planning-artifacts/architecture.md - Data Architecture]
- If configuration changes while the repository revision stays the same, still create a fresh snapshot before rebuilding affected artifacts. The current chunk schema is snapshot-scoped, so rebuilding in place would destroy the prior attributable state. [Source: src/codeman/contracts/repository.py; src/codeman/contracts/chunking.py]
- Reuse eligibility must require matching normalized path, language, source content hash, and compatible indexing fingerprint. Repository revision identity alone is not enough to prove chunk reuse is safe. [Source: _bmad-output/planning-artifacts/architecture.md - Caching Strategy; src/codeman/contracts/repository.py; src/codeman/contracts/chunking.py]
- Baseline selection should use the most recent snapshot for the repository that has both extracted source inventory and generated chunks. If no such baseline exists, fail with a stable error that tells the operator to complete the initial indexing flow first. [Source: _bmad-output/planning-artifacts/epics.md - Story 1.6; src/codeman/cli/index.py]
- Deleted files or files that become unsupported must disappear from the new snapshot's source/chunk set. Do not silently carry stale chunk rows or payload artifacts forward. [Source: _bmad-output/planning-artifacts/prd.md - FR3, FR4, FR5, FR6; src/codeman/infrastructure/snapshotting/local_repository_scanner.py]
- Keep runtime paths under `.codeman/` and avoid writing generated artifacts under `src/`, fixture directories, or the repository root outside runtime-managed storage. [Source: _bmad-output/planning-artifacts/architecture.md - Data Boundaries; File Organization Patterns]
- Preserve CLI JSON discipline: `stdout` contains only the final envelope in machine mode, while progress text and operator diagnostics stay on `stderr`. [Source: _bmad-output/planning-artifacts/architecture.md - Format Patterns; src/codeman/cli/index.py]
- Do not implement the full layered configuration loader, provider settings model, or experiment-profile system in this story. Add only the narrow fingerprint surface needed for current indexing/re-index attribution, and leave richer config composition to Epic 3. [Source: _bmad-output/planning-artifacts/epics.md - Epic 3; _bmad-output/planning-artifacts/prd.md - FR13-FR17]
- If the implementation needs to share chunk serialization logic between full builds and reuse paths, extract a reusable helper or collaborator rather than duplicating the chunk id and payload-writing rules in multiple places. [Source: src/codeman/application/indexing/build_chunks.py; src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]

### File / Structure Guidance

- Preferred new or expanded files for this story:
  - `src/codeman/application/repo/reindex_repository.py`
  - `src/codeman/application/ports/reindex_run_store_port.py`
  - `src/codeman/bootstrap.py`
  - `src/codeman/cli/index.py`
  - `src/codeman/contracts/reindexing.py`
  - `src/codeman/contracts/errors.py`
  - `src/codeman/config/models.py`
  - `src/codeman/config/indexing.py` (only if a small companion module keeps `models.py` from becoming noisy)
  - `src/codeman/infrastructure/persistence/sqlite/tables.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/reindex_run_repository.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/snapshot_repository.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/chunk_repository.py`
  - `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py`
  - `src/codeman/application/indexing/build_chunks.py`
  - `docs/cli-reference.md`
  - `tests/unit/application/test_reindex_repository.py`
  - `tests/unit/cli/test_index.py`
  - `tests/unit/infrastructure/test_filesystem_artifact_store.py`
  - `tests/integration/persistence/test_reindex_runs.py`
  - `tests/e2e/test_index_reindex.py`
- A pragmatic first CLI surface is:
  - `uv run codeman index reindex <repository-id>`
  - `uv run codeman index reindex <repository-id> --output-format json`
- A pragmatic `ReindexResult` shape is:
  - `run_id`
  - `repository`
  - `previous_snapshot_id`
  - `result_snapshot_id`
  - `change_reason`
  - `previous_revision_identity`
  - `result_revision_identity`
  - `previous_config_fingerprint`
  - `current_config_fingerprint`
  - `source_files_reused`
  - `source_files_rebuilt`
  - `source_files_removed`
  - `chunks_reused`
  - `chunks_rebuilt`
  - `noop`
- A pragmatic `reindex_runs` row shape is:
  - `id`
  - `repository_id`
  - `previous_snapshot_id`
  - `result_snapshot_id`
  - `previous_revision_identity`
  - `result_revision_identity`
  - `previous_config_fingerprint`
  - `current_config_fingerprint`
  - `change_reason`
  - `source_files_reused`
  - `source_files_rebuilt`
  - `source_files_removed`
  - `chunks_reused`
  - `chunks_rebuilt`
  - `created_at`
- If chunk payload reuse needs old content, add an artifact-store read helper and keep the existing payload JSON layout as the single source of truth instead of reimplementing that shape ad hoc in the new use case.

### Testing Guidance

- Use pytest across unit, integration, and e2e layers and keep the same temp-workspace isolation pattern already used in Stories 1.3, 1.4, and 1.5. [Source: tests/unit/application/test_create_snapshot.py; tests/unit/application/test_extract_source_files.py; tests/unit/application/test_build_chunks.py]
- Add a baseline-missing negative-path test proving `index reindex` fails with a stable error if the repository has registrations or snapshots but no fully indexed baseline yet.
- Add a no-change test proving the command returns a new attributable run outcome with `noop=true`, zero rebuild counts, and no duplicate snapshot or chunk artifacts.
- Add a source-change test with at least one modified file and one unchanged file to prove selective reuse works and unchanged chunk payloads are copied or re-materialized without re-parsing.
- Add a deleted-file test proving stale chunk rows from removed or newly unsupported files do not leak into the new snapshot.
- Add a config-change test that forces a full rebuild even when source hashes are unchanged, and verify the previous snapshot's chunk set remains intact.
- Add a dirty-worktree or non-Git test proving the filesystem-fingerprint fallback still produces deterministic re-index behavior.
- Add JSON-mode assertions proving `stdout` contains only the final success/failure envelope while progress messages stay on `stderr`. [Source: tests/e2e/test_index_build_chunks.py; _bmad-output/planning-artifacts/architecture.md - Format Patterns]

### Git Intelligence Summary

- Recent implementation history shows a consistent additive pattern: add one focused use case, add or extend a small number of ports, wire the new capability through `bootstrap.py`, and back it with mirrored unit, integration, and e2e tests instead of broad structural rewrites.
- Commit `9f82235` introduced chunk generation through focused modules, a migration, CLI updates, and tight tests rather than a framework-heavy abstraction layer. Re-indexing should continue that style.
- Commit `d1eebe2` established Git-aware repository discovery plus fixture-driven coverage for supported, ignored, binary, and malformed files. Re-index testing should extend those patterns instead of inventing a new fixture model.
- Current history also shows that review fixes land directly in the affected modules rather than through wrappers, so Story 1.6 should prefer explicit ports/repositories/helpers over a broad internal framework.

### Latest Technical Information

- As of March 14, 2026, Python 3.13.12 was released on February 3, 2026. The repository pin `>=3.13,<3.14` remains a deliberate stability choice for this story, not outdated drift. [Source: https://www.python.org/downloads/release/python-31312/]
- Typer `0.20.0` release notes highlight command suggestions on typo by default and Python 3.14 support. The current Typer command-group pattern remains current, so Story 1.6 should extend `src/codeman/cli/index.py` instead of redesigning CLI wiring. [Source: https://typer.tiangolo.com/release-notes/]
- Pydantic v2.12 was published on October 7, 2025 and added initial Python 3.14 support. The repository's current `BaseModel` plus `ConfigDict(extra="forbid")` style remains the correct v2-era contract pattern for new re-index DTOs. [Source: https://pydantic.dev/articles/pydantic-v2-12-release]
- SQLAlchemy `2.0.44` is the official Core-era baseline already approved by the architecture, and the official release notes reinforce staying on explicit SQLAlchemy Core patterns instead of introducing ORM-heavy persistence just to support re-index metadata. [Source: https://www.sqlalchemy.org/blog/2025/10/10/sqlalchemy-2.0.44-released/]
- The Alembic changelog includes `1.17.2`, released on November 14, 2025. The repository's migration flow is still modern, so schema changes for re-index metadata should continue through Alembic rather than ad hoc SQLite bootstrapping. [Source: https://alembic.sqlalchemy.org/en/latest/changelog.html]
- Git's official docs continue to define `status --porcelain` as stable machine-readable output and `ls-files` as the supported way to enumerate tracked and other candidate files with ignore handling. If Story 1.6 expands Git-aware change detection, it should stay on these machine-readable commands rather than parsing human console text. [Source: https://git-scm.com/docs/git-status; https://git-scm.com/docs/git-ls-files]

### Project Context Reference

- No `project-context.md` file was found in the repository, so the authoritative guidance remains the PRD, architecture, epics, sprint status, and the completed Stories 1.4 and 1.5 artifacts.
- No separate UX design artifact exists for this project, and Story 1.6 remains a CLI/data-flow story with no dedicated UI requirements.

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Epic 1; Story 1.6]
- [Source: _bmad-output/planning-artifacts/prd.md - FR3, FR4, FR5, FR6, FR13-FR17, Project Classification, Reliability & Reproducibility, Journey 2]
- [Source: _bmad-output/planning-artifacts/architecture.md - Core Architectural Decisions, Data Architecture, Caching Strategy, API & Communication Patterns, Format Patterns, Project Structure & Boundaries, Data Boundaries, File Organization Patterns]
- [Source: _bmad-output/planning-artifacts/implementation-readiness-report-2026-03-13.md]
- [Source: _bmad-output/implementation-artifacts/1-4-extract-supported-source-files-into-a-source-inventory.md]
- [Source: _bmad-output/implementation-artifacts/1-5-generate-structure-aware-retrieval-chunks.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: README.md]
- [Source: docs/cli-reference.md]
- [Source: pyproject.toml]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/cli/index.py]
- [Source: src/codeman/config/models.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: src/codeman/contracts/repository.py]
- [Source: src/codeman/contracts/chunking.py]
- [Source: src/codeman/application/repo/create_snapshot.py]
- [Source: src/codeman/application/indexing/extract_source_files.py]
- [Source: src/codeman/application/indexing/build_chunks.py]
- [Source: src/codeman/application/ports/artifact_store_port.py]
- [Source: src/codeman/application/ports/chunk_store_port.py]
- [Source: src/codeman/application/ports/snapshot_port.py]
- [Source: src/codeman/application/ports/source_inventory_port.py]
- [Source: src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/tables.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/snapshot_repository.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/source_file_repository.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/chunk_repository.py]
- [Source: src/codeman/infrastructure/snapshotting/git_revision_resolver.py]
- [Source: src/codeman/infrastructure/snapshotting/local_repository_scanner.py]
- [Source: tests/unit/application/test_create_snapshot.py]
- [Source: tests/unit/application/test_extract_source_files.py]
- [Source: tests/unit/application/test_build_chunks.py]
- [Source: tests/unit/cli/test_index.py]
- [Source: tests/integration/persistence/test_chunk_generation.py]
- [Source: tests/e2e/test_index_build_chunks.py]
- [Source: git log --oneline -5]
- [Source: git show --stat --summary 9f82235]
- [Source: git show --stat --summary d1eebe2]
- [Source: https://www.python.org/downloads/release/python-31312/]
- [Source: https://typer.tiangolo.com/release-notes/]
- [Source: https://pydantic.dev/articles/pydantic-v2-12-release]
- [Source: https://www.sqlalchemy.org/blog/2025/10/10/sqlalchemy-2.0.44-released/]
- [Source: https://alembic.sqlalchemy.org/en/latest/changelog.html]
- [Source: https://git-scm.com/docs/git-status]
- [Source: https://git-scm.com/docs/git-ls-files]

## Story Completion Status

- Status set to `ready-for-dev`.
- Ultimate context engine analysis completed - comprehensive developer guide created.
- The next expected workflow is implementation via the dev-story/dev agent, followed by code review once development is complete.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Implementation Plan

- Add a narrow indexing fingerprint and snapshot-level completion markers so the latest usable baseline can be discovered deterministically.
- Reuse prior chunk payloads through a shared chunk materializer while keeping snapshots immutable and persisting attributable `reindex_runs`.
- Cover `noop`, selective reuse, config-driven rebuilds, and CLI JSON/stderr discipline with unit, integration, and e2e tests.

### Debug Log References

- `python3 -m compileall src/codeman`
- `python3 -m compileall tests`
- `PYTHONPATH=src pytest -q`
- `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run ruff check src tests`

### Completion Notes List

- Implemented `index reindex` orchestration with baseline discovery, narrow indexing fingerprinting, attributed `reindex_runs`, and operator-safe JSON/text CLI output.
- Added shared chunk materialization helpers so unchanged chunk payloads can be cloned into a fresh snapshot namespace while changed/config-invalidated files rebuild cleanly.
- Extended snapshot persistence to remember chunk-generation completion and indexing fingerprints, enabling deterministic `no_change`, `source_changed`, `config_changed`, and `source_and_config_changed` classification.
- Added unit, integration, and e2e coverage for no-op behavior, partial reuse with removed files, config-driven rebuilds, CLI failure handling, and artifact-store payload round-trips.
- Aligned the stale local-repository-scanner fixture expectation with the current supported-source contract where malformed-but-textual `assets/broken.js` remains a supported source file and is handled later by chunk fallback.
- Resolved the review follow-up that empty extract-only snapshots must not qualify as indexed baselines until chunk generation has actually completed.
- Resolved the review follow-up that unsupported-only repository revisions remain true no-op re-index runs without creating duplicate snapshots, while still recording the current revision identity.
- Re-ran the full validation suite after the review fixes: `PYTHONPATH=src pytest -q` and `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run ruff check src tests`.

### File List

- `_bmad-output/implementation-artifacts/1-6-re-index-after-source-or-configuration-changes.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/cli-reference.md`
- `migrations/versions/202603141330_add_reindex_runs_and_snapshot_indexing_fields.py`
- `src/codeman/application/indexing/build_chunks.py`
- `src/codeman/application/indexing/chunk_materializer.py`
- `src/codeman/application/ports/artifact_store_port.py`
- `src/codeman/application/ports/chunk_store_port.py`
- `src/codeman/application/ports/reindex_run_store_port.py`
- `src/codeman/application/ports/snapshot_port.py`
- `src/codeman/application/repo/reindex_repository.py`
- `src/codeman/bootstrap.py`
- `src/codeman/cli/index.py`
- `src/codeman/config/indexing.py`
- `src/codeman/config/models.py`
- `src/codeman/contracts/errors.py`
- `src/codeman/contracts/reindexing.py`
- `src/codeman/contracts/repository.py`
- `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py`
- `src/codeman/infrastructure/persistence/sqlite/repositories/chunk_repository.py`
- `src/codeman/infrastructure/persistence/sqlite/repositories/reindex_run_repository.py`
- `src/codeman/infrastructure/persistence/sqlite/repositories/snapshot_repository.py`
- `src/codeman/infrastructure/persistence/sqlite/tables.py`
- `tests/e2e/test_index_reindex.py`
- `tests/integration/persistence/test_reindex_runs.py`
- `tests/unit/application/test_build_chunks.py`
- `tests/unit/application/test_reindex_repository.py`
- `tests/unit/cli/test_index.py`
- `tests/unit/infrastructure/test_filesystem_artifact_store.py`
- `tests/unit/infrastructure/test_local_repository_scanner.py`

## Change Log

- `2026-03-14`: Implemented repository re-indexing with baseline reuse, snapshot fingerprint tracking, `reindex_runs` persistence, CLI/docs updates, and full automated test coverage.
- `2026-03-14`: Addressed post-review baseline/no-op edge cases, expanded regression coverage, and closed the story after a green full-suite validation.
