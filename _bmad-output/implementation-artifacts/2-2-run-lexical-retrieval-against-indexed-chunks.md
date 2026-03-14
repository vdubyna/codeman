# Story 2.2: Run Lexical Retrieval Against Indexed Chunks

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want to run lexical queries against indexed repository chunks,
so that I can find exact symbols, identifiers, and text matches in the repository quickly.

## Acceptance Criteria

1. Given a repository with generated retrieval chunks, when I run a lexical query through the CLI, then codeman searches a lexical index built from chunk content and metadata, and returns ranked matches for the query.
2. Given the same lexical query in machine-readable mode, when the command completes successfully, then `stdout` contains only the standard JSON success envelope, and progress or diagnostics are written to `stderr`.

## Tasks / Subtasks

- [x] Introduce the lexical query use case, contracts, and CLI surface. (AC: 1, 2)
  - [x] Add focused lexical-query request/result/diagnostics DTOs plus stable query failure types in `src/codeman/contracts/retrieval.py` and `src/codeman/contracts/errors.py`, keeping the result shape intentionally narrow and reusable by later retrieval stories.
  - [x] Create `src/codeman/application/query/run_lexical_query.py` as the orchestration entrypoint and keep `src/codeman/cli/query.py` limited to argument parsing, progress reporting, success/failure envelopes, and exit handling.
  - [x] Wire the use case through `src/codeman/bootstrap.py` and expose `uv run codeman query lexical <repository-id> "<query>"` plus `--output-format json`.
  - [x] Return stable failures for unknown repositories, missing current lexical build baselines, missing lexical artifact files, and generic lexical-query execution failures without auto-rebuilding indexes inside the query command.

- [x] Execute deterministic lexical queries against the current repository-scoped FTS5 artifact. (AC: 1)
  - [x] Add a narrow lexical-query port and a concrete adapter under `src/codeman/infrastructure/indexes/lexical/` that opens the current lexical SQLite artifact resolved via `IndexBuildStorePort.get_latest_build_for_repository()`.
  - [x] Query only the persisted lexical artifact and its stored traceability fields; do not re-read chunk payload JSON, do not rescan the repository tree, and do not rebuild lexical artifacts in the query path.
  - [x] Normalize raw CLI query text into a safe literal-oriented FTS5 expression, execute parameterized `MATCH` queries, and order results deterministically with FTS5 ranking plus a stable tiebreaker such as `chunk_id`.
  - [x] Reuse the metadata already stored in `lexical_chunks` (`chunk_id`, `relative_path`, `snapshot_id`, `repository_id`, `language`, `strategy`) so later stories can enrich formatting without inventing a second lookup flow.

- [x] Return ranked matches through the shared CLI contract without pulling Story 2.3 forward. (AC: 1, 2)
  - [x] Emit the standard success envelope in JSON mode with ranked matches and minimal run diagnostics such as query text, resolved snapshot/build identity, match count, and query latency.
  - [x] Keep the human-readable output compact and operator-friendly; send progress or diagnostics to `stderr` and final results to `stdout`.
  - [x] Defer snippets, highlighting, explanation text, semantic retrieval, hybrid fusion, comparison workflows, and metadata-heavy result packaging to Stories 2.3, 2.5, 2.6, and 2.7.

- [x] Update docs and add mirrored automated coverage. (AC: 1, 2)
  - [x] Update `docs/cli-reference.md` with the lexical query command only.
  - [x] Add unit, integration, and e2e coverage for happy-path lexical queries, missing-baseline failures, and text-vs-JSON envelopes.
  - [x] Add tests for symbol-heavy queries, path-fragment queries, deterministic ranking on tie conditions, and punctuation-containing input that must be handled safely instead of being treated as raw FTS syntax.

## Dev Notes

### Previous Story Intelligence

- Story 2.1 already established the lexical artifact contract for this story: a snapshot-scoped SQLite FTS5 database lives under `.codeman/indexes/lexical/<repository-id>/<snapshot-id>/lexical.sqlite3`, and `lexical_index_builds` records the current attributable build for a repository snapshot.
- `IndexBuildStorePort.get_latest_build_for_repository()` already resolves the lexical build for the latest indexed snapshot. Story 2.2 should reuse that lookup path instead of guessing paths or choosing stale builds manually.
- The lexical FTS table already stores the traceability fields this story needs for minimal ranked hits: `chunk_id`, `snapshot_id`, `repository_id`, `relative_path`, `language`, and `strategy`. Query execution should read directly from the lexical artifact rather than rehydrating hits from chunk payload files.
- The recent delivery pattern remains stable and should continue: thin Typer command handlers, one primary use case per application file, SQLite/Core-backed repositories, runtime-managed artifacts under `.codeman/`, and mirrored unit/integration/e2e tests.

### Current Repo State

- `src/codeman/cli/query.py` is still only a Typer group placeholder with no lexical command implementation.
- There is no `src/codeman/application/query/` orchestration yet, so Story 2.2 must introduce the first retrieval use case without disturbing the existing indexing flows.
- `src/codeman/contracts/retrieval.py` currently contains lexical-build DTOs only; no query request/result contracts exist yet.
- `src/codeman/bootstrap.py` wires repository registration, snapshot creation, source extraction, chunk generation, lexical index building, and re-indexing, but not query execution.
- `src/codeman/infrastructure/indexes/lexical/sqlite_fts5_builder.py` proves the artifact can satisfy direct `MATCH` lookups, yet there is no reusable lexical query adapter in the production code.
- `docs/cli-reference.md` lists repository and index commands only; there is no query command surface documented.
- Existing CLI tests in `tests/unit/cli/test_index.py` and adapter tests in `tests/unit/infrastructure/test_sqlite_fts5_builder.py` provide the style to mirror for the new query command and FTS adapter behavior.

### Technical Guardrails

- Keep the public interface CLI-only. This story must not introduce HTTP endpoints, MCP transport, background workers, or daemonized retrieval services. [Source: _bmad-output/planning-artifacts/prd.md - Project Classification; _bmad-output/planning-artifacts/architecture.md - API & Communication Patterns]
- Preserve the modular-monolith boundary already used in the repository: CLI parses and formats, application orchestrates, infrastructure owns SQLite/FTS behavior, and contracts remain the stable DTO layer. [Source: _bmad-output/planning-artifacts/architecture.md - Architectural Boundaries; Service Boundaries]
- `bootstrap.py` remains the single composition root. Wire lexical-query ports and adapters there instead of constructing them inside CLI commands or tests. [Source: _bmad-output/planning-artifacts/architecture.md - Project Structure & Boundaries; src/codeman/bootstrap.py]
- Resolve the current lexical artifact through `IndexBuildStorePort.get_latest_build_for_repository()` and fail clearly if no current indexed baseline exists. Do not silently rebuild indexes, query stale snapshot artifacts, or fall back to scanning live repository files. [Source: src/codeman/application/ports/index_build_store_port.py; src/codeman/infrastructure/persistence/sqlite/repositories/index_build_repository.py; _bmad-output/planning-artifacts/epics.md - Story 2.1; Story 2.2]
- Query against the lexical SQLite artifact only. Do not re-read chunk payload JSON, do not rescan source files, and do not treat the live repository as the source of truth for retrieval results. [Source: _bmad-output/implementation-artifacts/2-1-build-lexical-index-artifacts.md; src/codeman/infrastructure/indexes/lexical/sqlite_fts5_builder.py]
- JSON mode must keep `stdout` clean and final-output only. Human progress or diagnostics belong on `stderr`, and all structured success/failure payloads must follow the existing shared envelope contracts. [Source: _bmad-output/planning-artifacts/architecture.md - Format Patterns; Process Patterns; src/codeman/cli/common.py]
- Use parameterized SQL placeholders for lexical queries; do not interpolate raw query text into SQL strings. [Source: https://docs.python.org/3/library/sqlite3.html]
- Do not require operators to know raw FTS5 syntax for basic identifier/path queries. Inference: a safe literal-oriented query normalizer is preferable for this story because FTS5 bareword grammar is restrictive around punctuation, while codeman queries are likely to include code symbols and path fragments. [Source: https://sqlite.org/fts5.html; tests/unit/infrastructure/test_sqlite_fts5_builder.py]
- Use FTS5 ranking with deterministic secondary ordering so repeated runs on the same artifact and query return a stable order. Inference: `ORDER BY rank, chunk_id` is the strongest default fit because FTS5 exposes the hidden `rank` column for efficient ordering and the project already relies on deterministic artifact ordering elsewhere. [Source: https://sqlite.org/fts5.html; _bmad-output/planning-artifacts/architecture.md - Reliability & Reproducibility]
- Do not pull snippets/highlighting, explanation text, semantic retrieval, hybrid fusion, comparison workflows, or durable query-run manifests into this story. Those belong to Stories 2.3, 2.5, 2.6, 2.7, and 5.3. [Source: _bmad-output/planning-artifacts/epics.md - Story 2.3; Story 2.5; Story 2.6; Story 2.7; Story 5.3]
- No metadata schema change is expected for the core happy path in Story 2.2. Reuse existing lexical build metadata unless a tiny additive change is proven necessary during implementation. [Source: src/codeman/infrastructure/persistence/sqlite/tables.py; src/codeman/infrastructure/persistence/sqlite/repositories/index_build_repository.py]

### File / Structure Guidance

- Preferred new or expanded files for this story:
  - `src/codeman/application/query/__init__.py`
  - `src/codeman/application/query/run_lexical_query.py`
  - `src/codeman/application/ports/lexical_query_port.py`
  - `src/codeman/bootstrap.py`
  - `src/codeman/cli/query.py`
  - `src/codeman/contracts/retrieval.py`
  - `src/codeman/contracts/errors.py`
  - `src/codeman/infrastructure/indexes/lexical/__init__.py`
  - `src/codeman/infrastructure/indexes/lexical/sqlite_fts5_query_engine.py`
  - `docs/cli-reference.md`
  - `tests/unit/application/test_run_lexical_query.py`
  - `tests/unit/cli/test_query.py`
  - `tests/unit/infrastructure/test_sqlite_fts5_query_engine.py`
  - `tests/integration/query/test_run_lexical_query.py`
  - `tests/e2e/test_query_lexical.py`
- A pragmatic first CLI surface is:
  - `uv run codeman query lexical <repository-id> "bootValue"`
  - `uv run codeman query lexical <repository-id> "bootValue" --output-format json`
- A pragmatic lexical query result shape is:
  - `repository`
  - `snapshot`
  - `build`
  - `query`
  - `matches`
  - `diagnostics`
- A pragmatic lexical hit shape is:
  - `chunk_id`
  - `relative_path`
  - `language`
  - `strategy`
  - `score`
  - `rank`
- A pragmatic diagnostics shape is:
  - `match_count`
  - `query_latency_ms`
- Keep the adapter-owned query implementation beside the existing builder in `src/codeman/infrastructure/indexes/lexical/`. Do not place SQL/FTS details into `application/` or `cli/`.

### Testing Guidance

- Use pytest across unit, integration, and e2e layers and keep the same temp-workspace isolation pattern already used by Stories 1.5, 1.6, and 2.1. [Source: _bmad-output/implementation-artifacts/1-5-generate-structure-aware-retrieval-chunks.md; _bmad-output/implementation-artifacts/1-6-re-index-after-source-or-configuration-changes.md; _bmad-output/implementation-artifacts/2-1-build-lexical-index-artifacts.md]
- Add unit coverage for repository/build resolution, safe query normalization, deterministic ordering/tie handling, and stable error mapping for missing repositories, missing builds, and missing lexical artifact files.
- Add infrastructure-level tests that the lexical query adapter can search identifiers (`snake_case`, `HomeController`, `bootValue`) and path fragments, returns stable ordering, and handles punctuation-heavy user input without leaking raw SQL/FTS string interpolation into the implementation.
- Add an integration test proving that after a repository receives a newer snapshot and lexical build, the lexical query use case resolves the current snapshot build instead of returning hits from an older repository build.
- Add an integration or unit test covering the failure path where lexical build metadata exists but the underlying `.sqlite3` artifact has been removed or is unreadable.
- Add e2e coverage that registers a repository, creates a snapshot, extracts sources, builds chunks, builds lexical artifacts, and then executes `query lexical` in both human and JSON modes.
- Add assertions that JSON mode writes only the final success/failure envelope to `stdout` while progress messages remain on `stderr`. [Source: _bmad-output/planning-artifacts/architecture.md - Format Patterns; Process Patterns]

### Git Intelligence Summary

- Recent implementation history shows a consistent additive style: introduce one focused use case, one or two narrow ports/adapters, wire them in `bootstrap.py`, and back the change with mirrored unit, integration, and e2e coverage instead of large refactors.
- Commit `54e4f83` (`story(2-1-build-lexical-index-artifacts): complete code review and mark done`) is especially relevant because Story 2.2 depends on the corrected repository-level lexical build lookup. Reuse that freshness logic rather than recreating repository/snapshot selection inside the query path.
- Commit `912e308` (`feat: complete story 1.6 reindex flow`) confirms the team already prefers attributable, snapshot-aware freshness resolution. Story 2.2 should keep that same repository-current-snapshot posture for query execution.

### Latest Technical Information

- The current workspace runtime reports SQLite `3.45.3`, and local smoke tests confirm this runtime can create and query FTS5 tables successfully. Story 2.2 can therefore rely on long-stable FTS5 behavior already present in the local Python runtime without adding a third-party lexical engine dependency. [Source: local command `python3 - <<'PY' ... print(sqlite3.sqlite_version) ... PY`; local command `python3 - <<'PY' ... create virtual table ft using fts5(...) ... select ... where ft match ? ... PY`]
- The official SQLite FTS5 documentation states that the hidden `rank` column can be used to order matches and is usually faster than sorting by `bm25(ft)` directly. Inference: prefer `ORDER BY rank, chunk_id` for the default lexical query path so the ranking stays efficient and deterministic. [Source: https://sqlite.org/fts5.html]
- The same FTS5 docs describe `highlight()` and `snippet()` helpers, but those capabilities are not required to satisfy Story 2.2. Defer them until Story 2.3, where result explanation and agent-friendly packaging are explicitly in scope. [Source: https://sqlite.org/fts5.html]
- FTS5 barewords intentionally allow only a restricted character set, while codeman users are likely to search for symbols and path fragments containing punctuation. Inference: normalize user input into a safe literal-oriented query before handing it to `MATCH`, and keep raw advanced FTS syntax out of the default CLI contract for now. [Source: https://sqlite.org/fts5.html]
- The Python `sqlite3` documentation recommends DB-API parameter substitution rather than string formatting for SQL values. Story 2.2 should follow that guidance for all lexical query inputs. [Source: https://docs.python.org/3/library/sqlite3.html]

### Project Context Reference

- No `project-context.md` file was found in the repository, so the authoritative guidance remains the PRD, architecture, epics, sprint status, and completed Stories 1.5, 1.6, and 2.1.
- No separate UX design artifact exists for this project, and Story 2.2 remains a CLI/data-flow story with no dedicated UI design requirements.

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Epic 2; Story 2.1; Story 2.2; Story 2.3; Story 2.5; Story 2.6; Story 2.7; Story 5.3]
- [Source: _bmad-output/planning-artifacts/prd.md - Success Criteria; MVP - Minimum Viable Product; Functional Requirements; Non-Functional Requirements]
- [Source: _bmad-output/planning-artifacts/architecture.md - Data Architecture; API & Communication Patterns; Implementation Patterns & Consistency Rules; Project Structure & Boundaries]
- [Source: _bmad-output/implementation-artifacts/2-1-build-lexical-index-artifacts.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: docs/cli-reference.md]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/cli/query.py]
- [Source: src/codeman/cli/common.py]
- [Source: src/codeman/contracts/common.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: src/codeman/contracts/retrieval.py]
- [Source: src/codeman/runtime.py]
- [Source: src/codeman/application/indexing/build_lexical_index.py]
- [Source: src/codeman/application/ports/index_build_store_port.py]
- [Source: src/codeman/infrastructure/indexes/lexical/sqlite_fts5_builder.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/tables.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/index_build_repository.py]
- [Source: tests/unit/cli/test_index.py]
- [Source: tests/unit/infrastructure/test_sqlite_fts5_builder.py]
- [Source: git log --oneline -5]
- [Source: https://sqlite.org/fts5.html]
- [Source: https://docs.python.org/3/library/sqlite3.html]
- [Source: local command `python3 - <<'PY' ... print(sqlite3.sqlite_version) ... PY`]
- [Source: local command `python3 - <<'PY' ... create virtual table ft using fts5(...) ... select ... where ft match ? ... PY`]

## Story Completion Status

- Status set to `review`.
- Implemented repository-scoped lexical query execution, CLI output contracts, and mirrored unit/integration/e2e coverage.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Implementation Plan

- Add lexical-query DTOs, error contracts, use-case orchestration, and bootstrap wiring so `query lexical` resolves the current repository-scoped lexical build without rebuilding indexes.
- Implement a narrow SQLite FTS5 query adapter that normalizes literal-oriented queries safely, reads only persisted lexical artifacts, and returns deterministically ordered hits.
- Expose compact text/JSON CLI output, update the CLI reference, and add mirrored unit, integration, and e2e coverage for success, ranking, and stable failure paths.

### Debug Log References

- 2026-03-14: Story context generated via the `bmad-create-story` workflow for backlog story `2-2-run-lexical-retrieval-against-indexed-chunks`.
- 2026-03-14: Red phase: `PYTHONPATH=src pytest -q tests/unit/application/test_run_lexical_query.py tests/unit/cli/test_query.py`
- 2026-03-14: Task 2 red phase: `PYTHONPATH=src pytest -q tests/unit/infrastructure/test_sqlite_fts5_query_engine.py tests/integration/query/test_run_lexical_query_integration.py`
- 2026-03-14: Story suite: `PYTHONPATH=src pytest -q tests/unit/application/test_run_lexical_query.py tests/unit/cli/test_query.py tests/unit/infrastructure/test_sqlite_fts5_query_engine.py tests/integration/query/test_run_lexical_query_integration.py tests/e2e/test_query_lexical.py`
- 2026-03-14: Review-fix validation: `PYTHONPATH=src pytest -q tests/unit/cli/test_query.py tests/e2e/test_query_lexical.py`
- 2026-03-14: Lint: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run ruff check src tests`
- 2026-03-14: Full regression: `PYTHONPATH=src pytest -q`

### Completion Notes List

- Added lexical-query DTOs, stable error codes, a repository-scoped query use case, and bootstrap wiring for `uv run codeman query lexical <repository-id> "<query>"`.
- Implemented a SQLite FTS5 query adapter that uses parameterized `MATCH` queries, safe literal-oriented normalization, deterministic `ORDER BY rank, chunk_id`, and artifact-only reads from the current repository build.
- Added compact text output, JSON success/failure envelopes, CLI docs, and mirrored unit, integration, and e2e coverage for happy paths, missing lexical baselines, missing artifacts, punctuation-heavy input, path fragments, and deterministic ranking.
- Resolved the code review finding by supporting flag-like query values through an explicit `--query` path without breaking the original positional CLI surface.
- Verified the final state with `ruff check` and a full repository regression run (`106 passed`).

### File List

- _bmad-output/implementation-artifacts/2-2-run-lexical-retrieval-against-indexed-chunks.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- docs/cli-reference.md
- src/codeman/application/ports/lexical_query_port.py
- src/codeman/application/query/__init__.py
- src/codeman/application/query/run_lexical_query.py
- src/codeman/bootstrap.py
- src/codeman/cli/query.py
- src/codeman/contracts/errors.py
- src/codeman/contracts/retrieval.py
- src/codeman/infrastructure/indexes/lexical/__init__.py
- src/codeman/infrastructure/indexes/lexical/sqlite_fts5_query_engine.py
- tests/e2e/test_query_lexical.py
- tests/integration/query/test_run_lexical_query_integration.py
- tests/unit/application/test_run_lexical_query.py
- tests/unit/cli/test_query.py
- tests/unit/infrastructure/test_sqlite_fts5_query_engine.py

## Change Log

- 2026-03-14: Implemented Story 2.2 lexical query contracts, use case, SQLite FTS5 adapter, CLI surface, docs, and mirrored automated coverage; story moved to `review`.
- 2026-03-14: Fixed code review finding for flag-like lexical queries, revalidated the repository, and moved the story to `done`.
