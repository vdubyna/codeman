# Story 2.1: Build Lexical Index Artifacts

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want codeman to build a lexical index from generated retrieval chunks,
so that lexical queries can run quickly and consistently against the indexed repository.

## Acceptance Criteria

1. Given a repository with generated retrieval chunks, when lexical indexing is run, then codeman builds and stores a lexical index from chunk content and relevant metadata, and records enough index metadata to attribute the lexical index to a specific repository state and run context.
2. Given lexical index artifacts already exist for an older chunk set or repository state, when lexical indexing is run again, then codeman refreshes or rebuilds the lexical index as needed for the current state, and does not execute lexical queries against stale index artifacts.

## Tasks / Subtasks

- [x] Introduce the lexical-index build use case, contracts, and CLI surface. (AC: 1, 2)
  - [x] Add focused request/result/diagnostics DTOs plus stable error codes, preferably in `src/codeman/contracts/retrieval.py` and `src/codeman/contracts/errors.py`, without pulling full query-result formatting into this story.
  - [x] Create `src/codeman/application/indexing/build_lexical_index.py` as the orchestration entrypoint and keep `src/codeman/cli/index.py` limited to argument parsing, progress reporting, success/failure envelopes, and exit handling.
  - [x] Wire the use case through `src/codeman/bootstrap.py` and expose `uv run codeman index build-lexical <snapshot-id>` with `--output-format json`.
  - [x] Add stable failures for unknown snapshots, missing chunk baselines, missing/corrupt chunk payload artifacts, and a generic lexical-build failure that stays operator-safe.

- [x] Build snapshot-scoped lexical index artifacts from persisted chunk metadata and payloads. (AC: 1, 2)
  - [x] Add a narrow lexical index port plus a concrete adapter under `src/codeman/infrastructure/indexes/lexical/` that builds a dedicated SQLite FTS5 database under `.codeman/indexes/lexical/<repository-id>/<snapshot-id>/`.
  - [x] Use persisted chunk rows from `ChunkStorePort.list_by_snapshot()` plus payload text from `FilesystemArtifactStore.read_chunk_payload()`; do not re-scan the repository and do not re-run parsers/chunkers.
  - [x] Index chunk `content` and `relative_path` as searchable fields, and carry traceability fields such as `chunk_id`, `snapshot_id`, `repository_id`, `language`, and `strategy` inside the lexical artifact so later query flows can explain hits without inventing a second source of truth.
  - [x] Keep build input ordering deterministic and finalize the artifact atomically, so reruns do not leave behind partially written or half-refreshed index files.

- [x] Persist attributable lexical-build metadata without pulling Epic 3 forward. (AC: 1, 2)
  - [x] Add a dedicated `lexical_index_builds` table, or a narrowly scoped `index_builds` equivalent, plus a SQLite repository adapter that records build id, repository id, snapshot id, revision identity/source, current `indexing_config_fingerprint`, lexical engine id, tokenizer spec, indexed fields, chunk count, index path, and creation timestamp.
  - [x] Add lookup helpers that later stories can use to resolve the correct lexical build for a snapshot or repository and therefore avoid stale artifacts.
  - [x] Keep lexical-build configuration intentionally narrow and local to this story; do not implement the layered retrieval configuration model, reusable strategy profiles, or experiment-management UX from Epic 3.

- [x] Keep Story 2.1 bounded to artifact creation, freshness, docs, and tests. (AC: 1, 2)
  - [x] Do not implement public lexical query execution, ranked result formatting, snippet generation, compare flows, or hybrid retrieval behavior in this story.
  - [x] Update `docs/cli-reference.md` with the lexical build command only.
  - [x] Add mirrored unit, integration, and e2e coverage for happy-path builds, rebuild/freshness behavior, and stable failure modes.

## Dev Notes

### Previous Story Intelligence

- Story 1.5 established the approved upstream input for this story: chunk metadata is persisted in SQLite, and chunk payload JSON artifacts live under `.codeman/artifacts/snapshots/<snapshot-id>/chunks/` with stable chunk ids, spans, strategy labels, and source content hashes.
- Story 1.6 introduced `indexing_config_fingerprint` on snapshots plus the notion of a latest indexed baseline. Story 2.1 should reuse those attribution concepts instead of inventing a parallel provenance model for lexical builds.
- The recent delivery pattern is stable and should continue here: thin Typer commands, one primary use case per application file, SQLAlchemy Core repositories, Alembic-managed schema changes, and runtime-managed artifacts under `.codeman/`.

### Current Repo State

- `src/codeman/cli/query.py` is still a placeholder, so there is no lexical query surface yet.
- `src/codeman/application/indexing/` currently stops at chunk generation; there is no lexical index builder in the codebase.
- `src/codeman/bootstrap.py` wires repository registration, snapshot creation, source extraction, chunk generation, and re-indexing only.
- `src/codeman/runtime.py` already exposes `.codeman/indexes/`, which is the approved home for lexical artifacts.
- `src/codeman/contracts/chunking.py`, `src/codeman/infrastructure/persistence/sqlite/repositories/chunk_repository.py`, and `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py` already provide the metadata-plus-payload inputs required for lexical indexing without touching the live repository.
- There is no retrieval/index-build contract module, no lexical index port, and no lexical build metadata table yet.
- Current tests cover registration, snapshotting, extraction, chunking, and re-indexing; there is no lexical artifact coverage yet.

### Technical Guardrails

- Keep the public interface CLI-only. This story must not introduce HTTP endpoints, MCP transport, background workers, or daemonized retrieval processes. [Source: _bmad-output/planning-artifacts/prd.md - Project Classification; _bmad-output/planning-artifacts/architecture.md - API & Communication Patterns]
- Build lexical artifacts only from persisted chunk rows and chunk payload JSON documents. Do not re-scan the repository tree, do not re-run parsers or chunkers, and do not derive lexical documents from mutable live files. [Source: _bmad-output/implementation-artifacts/1-5-generate-structure-aware-retrieval-chunks.md; src/codeman/contracts/chunking.py; src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- Preserve the modular-monolith boundary already working in the repository: CLI parses and formats, application orchestrates, infrastructure owns SQLite/FTS/filesystem behavior, and contracts remain the stable DTO layer. [Source: _bmad-output/planning-artifacts/architecture.md - Architectural Boundaries; Service Boundaries]
- `bootstrap.py` remains the single composition root. Wire lexical ports, repositories, and adapters there instead of constructing them inside CLI commands or tests. [Source: _bmad-output/planning-artifacts/architecture.md - Project Structure & Boundaries; src/codeman/bootstrap.py]
- Keep all generated index artifacts under `.codeman/indexes/`; never write them under `src/`, checked-in fixture directories, or ad hoc repository-root locations. [Source: _bmad-output/planning-artifacts/architecture.md - Data Boundaries; File Organization Patterns; src/codeman/runtime.py]
- Snapshot identity and the existing `indexing_config_fingerprint` are part of lexical-build attribution. Story 2.1 should record them rather than recomputing provenance from the live repository state at build time. [Source: src/codeman/contracts/repository.py; src/codeman/config/indexing.py; _bmad-output/implementation-artifacts/1-6-re-index-after-source-or-configuration-changes.md]
- Do not pull query orchestration, result formatting, snippets, ranking explanations, semantic retrieval, or hybrid fusion into this story. Those belong to Stories 2.2, 2.3, 2.5, and 2.6. [Source: _bmad-output/planning-artifacts/epics.md - Story 2.2; Story 2.3; Story 2.5; Story 2.6]
- Do not assume a single lexical artifact is globally valid across snapshots. Freshness must be resolved by snapshot/repository metadata so stale builds are never selected for later query runs. [Source: _bmad-output/planning-artifacts/epics.md - Story 2.1; _bmad-output/implementation-artifacts/1-6-re-index-after-source-or-configuration-changes.md]
- Inference: a snapshot-scoped SQLite FTS5 database is the best MVP lexical engine fit because the project is already SQLite-based, the runtime in this workspace supports FTS5 today, and the architecture reserves adapter-owned local index directories under `.codeman/indexes/`. [Source: _bmad-output/planning-artifacts/architecture.md - Data Architecture; https://sqlite.org/fts5.html; local command `python3 - <<'PY' ... create virtual table t using fts5(x) ... PY`]
- Inference: exact symbol/identifier fidelity matters for codeman, so the default tokenizer should favor code-friendly token preservation over stemming-heavy defaults. Add tests around `snake_case`, mixed-case identifiers, and path fragments before locking the default tokenizer behavior. [Source: _bmad-output/planning-artifacts/prd.md - Executive Summary; Success Criteria; https://sqlite.org/fts5.html]

### File / Structure Guidance

- Preferred new or expanded files for this story:
  - `src/codeman/application/indexing/build_lexical_index.py`
  - `src/codeman/application/ports/lexical_index_port.py`
  - `src/codeman/application/ports/index_build_store_port.py`
  - `src/codeman/bootstrap.py`
  - `src/codeman/cli/index.py`
  - `src/codeman/contracts/retrieval.py`
  - `src/codeman/contracts/errors.py`
  - `src/codeman/infrastructure/indexes/lexical/__init__.py`
  - `src/codeman/infrastructure/indexes/lexical/sqlite_fts5_builder.py`
  - `src/codeman/infrastructure/persistence/sqlite/tables.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/index_build_repository.py`
  - `docs/cli-reference.md`
  - `migrations/versions/<timestamp>_create_lexical_index_builds_table.py`
  - `tests/unit/application/test_build_lexical_index.py`
  - `tests/unit/cli/test_index.py`
  - `tests/unit/infrastructure/test_sqlite_fts5_builder.py`
  - `tests/integration/indexing/test_build_lexical_index.py`
  - `tests/e2e/test_index_build_lexical.py`
- A pragmatic first CLI surface is:
  - `uv run codeman index build-lexical <snapshot-id>`
  - `uv run codeman index build-lexical <snapshot-id> --output-format json`
- A pragmatic lexical build result shape is:
  - `build_id`
  - `repository`
  - `snapshot`
  - `lexical_engine`
  - `tokenizer_spec`
  - `indexed_fields`
  - `chunks_indexed`
  - `index_path`
  - `created_at`
- A pragmatic `lexical_index_builds` row shape is:
  - `id`
  - `repository_id`
  - `snapshot_id`
  - `revision_identity`
  - `revision_source`
  - `indexing_config_fingerprint`
  - `lexical_engine`
  - `tokenizer_spec`
  - `indexed_fields_json`
  - `chunks_indexed`
  - `index_path`
  - `created_at`
- A pragmatic on-disk layout is:
  - `.codeman/indexes/lexical/<repository-id>/<snapshot-id>/lexical.sqlite3`
  - optionally a sibling manifest only if the SQLite file itself cannot carry enough build metadata; avoid redundant second sources of truth
- If the adapter needs temporary build files, place them under `.codeman/tmp/` and atomically replace the final lexical index DB only after the build fully succeeds.

### Testing Guidance

- Use pytest across unit, integration, and e2e layers and keep the same temp-workspace isolation pattern already used in Stories 1.5 and 1.6. [Source: _bmad-output/implementation-artifacts/1-5-generate-structure-aware-retrieval-chunks.md - Testing Guidance; _bmad-output/implementation-artifacts/1-6-re-index-after-source-or-configuration-changes.md - Testing Guidance]
- Add unit coverage for deterministic document ordering from chunk inputs, metadata-record creation, and stable error mapping when chunk rows or payload artifacts are missing.
- Add infrastructure-level tests that the SQLite FTS5 builder creates the expected schema, stores traceability metadata, and can satisfy direct adapter-level `MATCH` smoke queries for identifiers and path terms without needing the public query CLI yet.
- Add integration coverage that building twice for the same snapshot refreshes/replaces the artifact cleanly, while building for a new snapshot creates a distinct path and metadata row and does not treat the older build as current for the new snapshot.
- Add a failure-path test proving lexical build aborts safely when chunk payload JSON is missing or corrupt for one of the persisted chunk rows.
- Add e2e coverage that registers a repository, creates a snapshot, extracts sources, builds chunks, builds lexical artifacts, and verifies both human-readable and JSON envelopes.
- Add a second e2e or integration test after `index reindex` proving a new snapshot can build a fresh lexical artifact while the prior build remains attributable but is not selected as current for the new snapshot.
- Add assertions that JSON mode writes only the final envelope to `stdout` and keeps progress text on `stderr`. [Source: _bmad-output/planning-artifacts/architecture.md - Process Patterns; docs/cli-reference.md; src/codeman/cli/index.py]

### Git Intelligence Summary

- Recent implementation history shows a consistent additive style: add one focused use case, a narrow set of ports/repositories, wire it in `bootstrap.py`, and back it with mirrored unit, integration, and e2e tests instead of broad rewrites.
- Commit `912e308` (`feat: complete story 1.6 reindex flow`) confirms the team is already comfortable adding snapshot-scoped provenance and refresh logic without restructuring core layers. Story 2.1 should follow that style for lexical freshness.
- The repository currently favors direct explicit modules over framework-heavy abstractions, so a small dedicated FTS5 adapter is a better fit than introducing a large search framework upfront.

### Latest Technical Information

- Official SQLite chronology shows the SQLite project is already beyond the repository's local runtime version, but the current Python runtime in this workspace reports SQLite `3.45.3` and successfully creates an `fts5` virtual table. Story 2.1 should therefore rely only on long-stable FTS5 capabilities rather than newer release-specific additions. [Source: https://sqlite.org/chronology.html; local command `python3 - <<'PY' ... print(sqlite3.sqlite_version) ... PY`; local command `python3 - <<'PY' ... create virtual table t using fts5(x) ... PY`]
- The official SQLite FTS5 docs describe `UNINDEXED` columns for stored metadata, `tokenchars` options for tokenizer customization, optional `prefix` indexes for faster prefix lookups, and BM25/rank support. Inference: a dedicated snapshot-scoped SQLite FTS5 database with searchable `content` and `relative_path` plus unindexed traceability columns is a strong MVP lexical index design for codeman. [Source: https://sqlite.org/fts5.html]
- FTS5 has shipped as part of SQLite since 3.9.0, which makes it a strong local-first choice without pulling a third-party lexical engine dependency into the project. [Source: https://sqlite.org/fts5.html]
- Inference from the PRD and FTS5 docs: because codeman prioritizes exact symbol and identifier lookup, prefer `unicode61` tokenization with explicit code-friendly `tokenchars` over stemming-oriented defaults such as the Porter tokenizer, and prove the choice with tests on symbol-heavy fixture queries before treating it as stable. [Source: _bmad-output/planning-artifacts/prd.md - Executive Summary; Success Criteria; https://sqlite.org/fts5.html]

### Project Context Reference

- No `project-context.md` file was found in the repository, so the authoritative guidance remains the PRD, architecture, epics, sprint status, and completed Stories 1.5 and 1.6.
- No separate UX design artifact exists for this project, and Story 2.1 remains a CLI/data-flow story with no dedicated UI requirements.

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Epic 2; Story 2.1; Story 2.2; Story 2.3]
- [Source: _bmad-output/planning-artifacts/prd.md - Executive Summary; Success Criteria; Product Scope; Domain-Specific Requirements; Risk Mitigations]
- [Source: _bmad-output/planning-artifacts/architecture.md - Core Architectural Decisions; Data Architecture; API & Communication Patterns; Project Structure & Boundaries; Data Boundaries; Requirements to Structure Mapping; Gap Analysis Results]
- [Source: _bmad-output/planning-artifacts/implementation-readiness-report-2026-03-13.md - Overall Readiness Status; Recommended Next Steps]
- [Source: _bmad-output/implementation-artifacts/1-5-generate-structure-aware-retrieval-chunks.md]
- [Source: _bmad-output/implementation-artifacts/1-6-re-index-after-source-or-configuration-changes.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: README.md]
- [Source: docs/cli-reference.md]
- [Source: pyproject.toml]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/cli/index.py]
- [Source: src/codeman/cli/query.py]
- [Source: src/codeman/runtime.py]
- [Source: src/codeman/config/models.py]
- [Source: src/codeman/config/indexing.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: src/codeman/contracts/repository.py]
- [Source: src/codeman/contracts/chunking.py]
- [Source: src/codeman/application/indexing/build_chunks.py]
- [Source: src/codeman/application/ports/snapshot_port.py]
- [Source: src/codeman/application/ports/chunk_store_port.py]
- [Source: src/codeman/application/ports/artifact_store_port.py]
- [Source: src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/tables.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/snapshot_repository.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/chunk_repository.py]
- [Source: tests/e2e/test_index_build_chunks.py]
- [Source: git log --oneline -5]
- [Source: https://sqlite.org/fts5.html]
- [Source: https://sqlite.org/chronology.html]
- [Source: local command `python3 - <<'PY' ... print(sqlite3.sqlite_version) ... PY`]
- [Source: local command `python3 - <<'PY' ... create virtual table t using fts5(x) ... PY`]

## Story Completion Status

- Status set to `done`.
- Implemented snapshot-scoped lexical index creation with attributable build metadata, current-snapshot freshness lookup, and stable operator-safe failure handling.
- Verified the full repository with `ruff` and `pytest` after resolving review findings (`91 passed`).

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Debug Log References

- 2026-03-14: `PYTHONPATH=src pytest -q tests/unit/application/test_build_chunks.py tests/unit/application/test_build_lexical_index.py tests/unit/cli/test_index.py tests/unit/test_scaffold.py tests/integration/persistence/test_reindex_runs.py tests/integration/indexing/test_build_lexical_index_integration.py tests/e2e/test_index_build_chunks.py tests/e2e/test_index_reindex.py tests/e2e/test_index_build_lexical.py` (`31 passed`).
- 2026-03-14: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run ruff check src tests` (`All checks passed!`).
- 2026-03-14: `PYTHONPATH=src pytest -q` (`91 passed`).

### Completion Notes List

- Added the lexical build DTOs, error codes, use case, CLI command, and bootstrap wiring for `uv run codeman index build-lexical <snapshot-id>`.
- Implemented a snapshot-scoped SQLite FTS5 lexical artifact builder with deterministic input ordering, traceability fields, and atomic refresh behavior under `.codeman/indexes/lexical/`.
- Added `lexical_index_builds` persistence, lookup helpers, CLI docs, and mirrored unit/integration/e2e coverage for success, rebuild freshness, and stable failure modes.
- Resolved code review follow-ups by preventing empty/missing chunk baselines from producing a false-success lexical artifact and by making repository-level lookup return only the build for the current indexed snapshot.

### Change Log

- 2026-03-14: Implemented Story 2.1 lexical artifact creation flow, metadata attribution, CLI surface, and automated coverage.
- 2026-03-14: Fixed code review findings for stale repository-level lexical build lookup and missing-baseline validation, then revalidated the repository quality gates.

### File List

- _bmad-output/implementation-artifacts/2-1-build-lexical-index-artifacts.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- docs/cli-reference.md
- migrations/versions/202603141430_create_lexical_index_builds_table.py
- src/codeman/application/indexing/build_lexical_index.py
- src/codeman/application/ports/index_build_store_port.py
- src/codeman/application/ports/lexical_index_port.py
- src/codeman/bootstrap.py
- src/codeman/cli/index.py
- src/codeman/contracts/errors.py
- src/codeman/contracts/retrieval.py
- src/codeman/infrastructure/indexes/__init__.py
- src/codeman/infrastructure/indexes/lexical/__init__.py
- src/codeman/infrastructure/indexes/lexical/sqlite_fts5_builder.py
- src/codeman/infrastructure/persistence/sqlite/repositories/index_build_repository.py
- src/codeman/infrastructure/persistence/sqlite/tables.py
- tests/e2e/test_index_build_lexical.py
- tests/integration/indexing/test_build_lexical_index_integration.py
- tests/unit/application/test_build_lexical_index.py
- tests/unit/cli/test_index.py
- tests/unit/infrastructure/test_sqlite_fts5_builder.py
