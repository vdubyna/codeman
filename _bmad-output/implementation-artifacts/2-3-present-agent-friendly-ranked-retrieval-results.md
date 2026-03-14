# Story 2.3: Present Agent-Friendly Ranked Retrieval Results

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want retrieval results to include useful metadata and explanations,
so that I can understand relevance and use the output directly in reasoning and implementation workflows.

## Acceptance Criteria

1. Given a successful retrieval run, when results are returned in human or JSON mode, then each result includes stable chunk identity, source file reference, language metadata, and rank-related information, and the output format is consistent across retrieval modes.
2. Given a ranked result set, when I inspect the retrieval package, then I can see enough explanation or scoring context to understand why a result appeared near the top, and the package is compact enough to support agent consumption without opening the full repository manually.

## Tasks / Subtasks

- [x] Introduce a shared agent-friendly retrieval package and formatter entrypoint. (AC: 1, 2)
  - [x] Extend `src/codeman/contracts/retrieval.py` with stable result-package DTOs that can carry retrieval mode, query metadata, repository/snapshot/build identity, and enriched per-result fields without breaking the standard top-level success/failure envelope.
  - [x] Add `src/codeman/application/query/format_results.py` as the shared enrichment/formatting layer so lexical output stops hardcoding presentation inside `src/codeman/cli/query.py` and later Stories 2.5-2.7 can reuse the same contract shape.
  - [x] Keep `src/codeman/cli/query.py` limited to argument parsing, progress reporting, envelope emission, and human-readable rendering from already formatted DTOs.

- [x] Enrich lexical hits from persisted chunk metadata and chunk payload artifacts, not live repository reads. (AC: 1, 2)
  - [x] Add a narrow lookup capability to `src/codeman/application/ports/chunk_store_port.py` and the SQLite chunk repository so ranked `chunk_id` values can be resolved back to `ChunkRecord` rows in incoming rank order instead of forcing snapshot-wide scans.
  - [x] Reuse `ArtifactStorePort.read_chunk_payload()` to load matched chunk payloads and include compact source previews plus span metadata (`start_line`, `end_line`, `start_byte`, `end_byte`) in the formatted package; do not reread source files from the registered repository.
  - [x] Preserve lexical ranking context by surfacing at least `rank`, `score`, and a short explanation of what matched, such as highlighted query terms, path-hit context, or a lexical-only explanation string. Keep the explanation truthful to lexical evidence and do not imply semantic or hybrid reasoning.
  - [x] Keep the package compact: include only matched chunks, bounded preview text, and navigation metadata needed for reasoning workflows instead of dumping full chunk payloads or whole files.

- [x] Keep the retrieval output contract consistent across human mode, JSON mode, and future retrieval modes. (AC: 1, 2)
  - [x] Update lexical query orchestration so the same enriched result package can become the shared baseline for semantic and hybrid stories instead of inventing a lexical-only schema.
  - [x] In JSON mode, keep `stdout` limited to the standard success envelope and `snake_case` fields; in text mode, render a readable summary that mirrors the same metadata, span, preview, and explanation fields.
  - [x] Do not add a second bespoke JSON schema, and do not bury explanation assembly inside the CLI module where later MCP or compare flows would have to duplicate it.

- [x] Document the enriched query surface and add mirrored automated coverage. (AC: 1, 2)
  - [x] Update `docs/cli-reference.md` to show the enriched lexical retrieval output expectations in both text and JSON modes.
  - [x] Add unit coverage for formatter logic, preview truncation, explanation assembly, and stable rank-preserving chunk lookup.
  - [x] Add integration coverage proving formatted lexical results use persisted snapshot artifacts even if live repository files change after indexing, and fail safely when chunk metadata or payload artifacts are missing.
  - [x] Add e2e coverage for `uv run codeman query lexical ...` in text and JSON modes, asserting stable chunk identity, source references, spans/previews, explanation context, and clean `stdout`/`stderr` separation.

## Dev Notes

### Previous Story Intelligence

- Story 2.2 already delivers the safe lexical-query baseline for this story: repository-scoped build resolution, parameterized `MATCH` queries, deterministic ordering, clean JSON envelopes, and minimal ranked hits containing `chunk_id`, `relative_path`, `language`, `strategy`, `score`, and `rank`.
- Story 2.2 explicitly deferred snippets, highlighting, explanation text, and metadata-heavy result packaging to Story 2.3. This story should extend that baseline rather than redesigning query execution from scratch.
- The lexical query adapter already reads only the persisted lexical SQLite artifact. Keep that as the retrieval source of truth, then enrich ranked hits using persisted chunk metadata and payload artifacts.
- Upstream indexing stories already persist the data this story needs for richer packaging: `ChunkRecord` stores stable identifiers plus span metadata, and `ChunkPayloadDocument` stores the chunk content under `.codeman/artifacts/snapshots/<snapshot-id>/chunks/`.
- The current delivery pattern is stable and should continue: thin Typer commands, one primary use case per application file, explicit ports/adapters, runtime-managed artifacts under `.codeman/`, and mirrored unit/integration/e2e tests.

### Current Repo State

- `src/codeman/cli/query.py` currently renders a minimal lexical text summary directly in the CLI module. There is no reusable result formatter yet.
- `src/codeman/contracts/retrieval.py` contains raw lexical query DTOs only. It does not yet expose an agent-friendly retrieval package with spans, previews, or explanations.
- `src/codeman/application/query/run_lexical_query.py` returns minimal ranked hits and diagnostics, but there is no post-query enrichment step that joins `chunk_id` values back to chunk metadata and payload artifacts.
- `src/codeman/application/ports/chunk_store_port.py` exposes `list_by_snapshot()` only; there is no narrow lookup for resolving a ranked subset of chunk ids efficiently and deterministically.
- `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py` already supports `read_chunk_payload()`, so Story 2.3 does not need a new artifact format to access chunk content.
- `src/codeman/infrastructure/indexes/lexical/sqlite_fts5_query_engine.py` already computes lexical ranking and can be extended carefully if lexical evidence such as `highlight()` or `snippet()` should be returned from the adapter.
- `docs/cli-reference.md` documents the lexical query command surface but not the richer retrieval package expected by Story 2.3.
- The architecture document already names `src/codeman/application/query/format_results.py` as the intended shared home for result formatting, but that file does not exist in the current repository yet.

### Technical Guardrails

- Keep the public interface CLI-only. This story must not introduce HTTP endpoints, MCP transport, background workers, or daemonized retrieval services. [Source: _bmad-output/planning-artifacts/prd.md - Project Classification; _bmad-output/planning-artifacts/architecture.md - API & Communication Patterns]
- Preserve the modular-monolith boundary already used in the repository: CLI parses and renders, application orchestrates and formats, infrastructure owns SQLite/filesystem behavior, and contracts remain the stable DTO layer. [Source: _bmad-output/planning-artifacts/architecture.md - Architectural Boundaries; Service Boundaries; src/codeman/bootstrap.py]
- `bootstrap.py` remains the single composition root. Wire any new formatter collaborators or lookup adapters there instead of constructing them inside CLI commands or tests. [Source: _bmad-output/planning-artifacts/architecture.md - Project Structure & Boundaries; src/codeman/bootstrap.py]
- Build the enriched retrieval package from persisted artifacts only: lexical hits from the SQLite FTS5 artifact, chunk metadata from SQLite, and chunk payload previews from `.codeman/artifacts/`. Do not reread live repository files or treat the mutable working tree as the source of truth for formatted query output. [Source: _bmad-output/planning-artifacts/prd.md - Technical Success; _bmad-output/planning-artifacts/architecture.md - Data Boundaries; src/codeman/contracts/chunking.py; src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- Keep `stdout` clean in JSON mode. Human progress or diagnostics belong on `stderr`, and the final machine-readable payload must stay inside the standard success/failure envelope only. [Source: _bmad-output/planning-artifacts/epics.md - Additional Requirements; _bmad-output/planning-artifacts/architecture.md - Format Patterns; Process Patterns; src/codeman/cli/common.py]
- Keep JSON fields in `snake_case` and preserve stable identifiers ending in `_id`. Reuse existing DTO and error-code patterns instead of inventing near-duplicate response shapes. [Source: _bmad-output/planning-artifacts/architecture.md - Naming Patterns; Enforcement Guidelines]
- Do not introduce a second lexical-only result contract that semantic and hybrid queries cannot reuse. Story 2.3 should establish the shared retrieval-package baseline for later Stories 2.5-2.7. [Source: _bmad-output/planning-artifacts/epics.md - Epic 2; Story 2.3; Story 2.5; Story 2.6; Story 2.7; _bmad-output/planning-artifacts/architecture.md - Requirements Coverage Validation]
- Explanations must remain truthful. Use lexical evidence such as rank, score, path hits, query-term highlighting, or matched-content previews; do not fabricate semantic reasoning, fusion logic, or confidence claims the system cannot support yet. [Source: _bmad-output/planning-artifacts/prd.md - Executive Summary; Journey 1; Journey Requirements Summary]
- Keep previews compact and operator-safe. The goal is a retrieval package that avoids opening the full repository manually, not one that dumps complete chunk payloads or large repository excerpts by default. [Source: _bmad-output/planning-artifacts/prd.md - Success Criteria; Measurable Outcomes; _bmad-output/planning-artifacts/epics.md - Story 2.3]
- No metadata schema change is expected for the happy path in Story 2.3. Reuse `chunks` rows plus existing chunk payload artifacts unless a very small additive persistence change proves necessary during implementation. [Source: src/codeman/infrastructure/persistence/sqlite/tables.py; src/codeman/infrastructure/persistence/sqlite/repositories/chunk_repository.py]
- Do not pull durable query-run manifests, benchmark comparison output, semantic retrieval, or hybrid fusion into this story. Structured run logs/manifests belong to Story 5.3, and other retrieval modes belong to Stories 2.5-2.7. [Source: _bmad-output/planning-artifacts/epics.md - Story 2.5; Story 2.6; Story 2.7; Story 5.3]
- The architecture reserves `application/query/format_results.py` and a future `domain/retrieval/explanations.py`, but the current repo does not yet contain a `domain/retrieval/` package. Start with a focused application-layer formatter and only extract pure explanation logic into `domain/` if the rules become reusable enough to justify the extra boundary. Inference based on the current repository shape and the architecture target. [Source: _bmad-output/planning-artifacts/architecture.md - Complete Project Directory Structure; Service Boundaries; src/codeman/application/query/]

### File / Structure Guidance

- Preferred new or expanded files for this story:
  - `src/codeman/application/query/format_results.py`
  - `src/codeman/application/query/run_lexical_query.py`
  - `src/codeman/application/ports/chunk_store_port.py`
  - `src/codeman/bootstrap.py`
  - `src/codeman/cli/query.py`
  - `src/codeman/contracts/retrieval.py`
  - `src/codeman/infrastructure/indexes/lexical/sqlite_fts5_query_engine.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/chunk_repository.py`
  - `docs/cli-reference.md`
  - `tests/unit/application/test_format_results.py`
  - `tests/unit/application/test_run_lexical_query.py`
  - `tests/unit/cli/test_query.py`
  - `tests/unit/infrastructure/test_sqlite_fts5_query_engine.py`
  - `tests/integration/query/test_run_lexical_query_integration.py`
  - `tests/e2e/test_query_lexical.py`
- A pragmatic shared retrieval-package result shape is:
  - `retrieval_mode`
  - `query`
  - `repository`
  - `snapshot`
  - `build`
  - `results`
  - `diagnostics`
- A pragmatic enriched result-item shape is:
  - `chunk_id`
  - `relative_path`
  - `language`
  - `strategy`
  - `rank`
  - `score`
  - `start_line`
  - `end_line`
  - `start_byte`
  - `end_byte`
  - `content_preview`
  - `explanation`
- Prefer keeping lexical evidence as part of the adapter-facing or formatter-facing DTOs rather than reconstructing matches from raw text heuristics later.
- If preview generation needs lexical highlighting, the strongest path is to let the SQLite FTS5 adapter return snippet/highlight evidence while the application formatter translates that evidence into the shared result package.
- If preview truncation rules are added, keep them local to result formatting and document them clearly so semantic and hybrid stories can mirror the same compact-output convention later.

### Testing Guidance

- Use pytest across unit, integration, and e2e layers and preserve the temp-workspace isolation pattern already used in Stories 2.1 and 2.2. [Source: _bmad-output/implementation-artifacts/2-1-build-lexical-index-artifacts.md - Testing Guidance; _bmad-output/implementation-artifacts/2-2-run-lexical-retrieval-against-indexed-chunks.md - Testing Requirements]
- Add unit coverage for the new formatter or packager: enriched field mapping, preview truncation, explanation assembly, empty-result behavior, and preservation of incoming rank order.
- Add unit or integration coverage for the narrow chunk lookup path so ranked hit ordering is preserved even when chunk metadata is loaded through SQLite after the lexical query completes.
- Add infrastructure-level tests for any FTS5 `highlight()` or `snippet()` usage, including a safe fallback when punctuation-heavy queries or missing matches do not produce a highlight fragment.
- Add an integration test proving that after indexing completes, mutating the live repository file without reindexing does not change the formatted retrieval package. The package must still reflect the persisted snapshot artifacts, not the new working-tree contents.
- Add a failure-path test where lexical hits resolve to missing chunk metadata or a missing chunk payload artifact, and verify the error remains stable and operator-safe instead of silently omitting inconsistent results.
- Extend e2e coverage to assert that text output includes path, span, preview, and explanation context, while JSON mode exposes the same information in structured form and keeps `stdout` free of progress lines. [Source: _bmad-output/planning-artifacts/architecture.md - Format Patterns; Process Patterns]

### Git Intelligence Summary

- Recent implementation history continues to favor additive changes over refactors: add one focused use case or adapter, wire it in `bootstrap.py`, and back it with mirrored unit/integration/e2e coverage.
- Commit `8de17fc` (`story(2-2-run-lexical-retrieval-against-indexed-chunks): complete code review and mark done`) is the most relevant baseline because it completed the lexical query flow while deliberately keeping Story 2.3 out of scope. Reuse that query path instead of redesigning lexical retrieval.
- Commit `54e4f83` (`story(2-1-build-lexical-index-artifacts): complete code review and mark done`) matters because Story 2.3 depends on the corrected current-build lookup and snapshot-scoped lexical artifacts introduced there.
- Commit `912e308` (`feat: complete story 1.6 reindex flow`) reinforces the team's emphasis on attributable snapshot-local artifacts and fresh/current baseline resolution. Story 2.3 should preserve that same snapshot fidelity when packaging results.

### Latest Technical Information

- The current workspace runtime reports SQLite `3.45.3`, and a local smoke test confirms this runtime supports FTS5 `highlight()` and `snippet()` functions. Story 2.3 can therefore rely on those long-stable FTS5 helpers for compact lexical evidence without adding a third-party search dependency. [Source: local command `python3 -c 'import sqlite3; print(sqlite3.sqlite_version)'`; local command `python3 - <<'PY' ... select highlight(ft, 0, '[', ']'), snippet(ft, 0, '[', ']', '...', 5) ... PY`]
- The official SQLite FTS5 documentation describes `highlight()` and `snippet()` as auxiliary functions for matched rows. Inference: prefer these helpers for compact, truthful lexical explanations instead of dumping entire chunk contents or inventing ad hoc highlighting logic in Python. [Source: https://sqlite.org/fts5.html]
- The Python `sqlite3` documentation continues to recommend DB-API parameter substitution instead of string formatting for SQL values. Story 2.3 should keep that rule intact if the lexical query adapter expands its `SELECT` list to return snippet/highlight evidence. [Source: https://docs.python.org/3/library/sqlite3.html]
- The existing project pin `typer>=0.20.0,<0.21.0` remains appropriate for this story because Story 2.3 extends result rendering, not the CLI framework choice. No framework upgrade is required to satisfy the acceptance criteria. [Source: pyproject.toml]

### Project Context Reference

- No `project-context.md` file was found in the repository, so the authoritative guidance remains the PRD, architecture, epics, sprint status, and completed Stories 2.1 and 2.2.
- No separate UX design artifact exists for this project. Story 2.3 is a CLI and retrieval-packaging story, so UX requirements here are limited to compact, readable, agent-usable output.

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Epic 2; Story 2.1; Story 2.2; Story 2.3; Story 2.5; Story 2.6; Story 2.7; Story 5.3]
- [Source: _bmad-output/planning-artifacts/prd.md - Executive Summary; Success Criteria; Measurable Outcomes; Journey 1; Journey Requirements Summary; Technical Architecture Considerations]
- [Source: _bmad-output/planning-artifacts/architecture.md - Core Architectural Decisions; API & Communication Patterns; Naming Patterns; Format Patterns; Service Boundaries; Complete Project Directory Structure; Data Boundaries; Requirements Coverage Validation]
- [Source: _bmad-output/implementation-artifacts/2-1-build-lexical-index-artifacts.md]
- [Source: _bmad-output/implementation-artifacts/2-2-run-lexical-retrieval-against-indexed-chunks.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: docs/cli-reference.md]
- [Source: pyproject.toml]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/cli/common.py]
- [Source: src/codeman/cli/query.py]
- [Source: src/codeman/contracts/chunking.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: src/codeman/contracts/retrieval.py]
- [Source: src/codeman/application/query/run_lexical_query.py]
- [Source: src/codeman/application/ports/artifact_store_port.py]
- [Source: src/codeman/application/ports/chunk_store_port.py]
- [Source: src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- [Source: src/codeman/infrastructure/indexes/lexical/sqlite_fts5_builder.py]
- [Source: src/codeman/infrastructure/indexes/lexical/sqlite_fts5_query_engine.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/tables.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/chunk_repository.py]
- [Source: tests/unit/cli/test_query.py]
- [Source: tests/unit/infrastructure/test_sqlite_fts5_query_engine.py]
- [Source: tests/integration/query/test_run_lexical_query_integration.py]
- [Source: tests/e2e/test_query_lexical.py]
- [Source: git log --oneline -5]
- [Source: https://sqlite.org/fts5.html]
- [Source: https://docs.python.org/3/library/sqlite3.html]
- [Source: local command `python3 -c 'import sqlite3; print(sqlite3.sqlite_version)'`]
- [Source: local command `python3 - <<'PY' ... select highlight(ft, 0, '[', ']'), snippet(ft, 0, '[', ']', '...', 5) ... PY`]

## Story Completion Status

- Status set to `done`.
- Implemented the shared retrieval package, lexical enrichment flow, truthful explanation handling, bounded top-N packaging, CLI rendering updates, and mirrored automated coverage for the enriched query surface.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Implementation Plan

- Add shared retrieval-package DTOs and a dedicated formatting layer so lexical query results move to a reusable contract for later retrieval modes.
- Extend lexical query orchestration to resolve ranked chunk ids back to persisted chunk metadata and chunk payload artifacts, then assemble compact previews and truthful lexical explanations without reading live repository files.
- Update CLI rendering, docs, and mirrored unit/integration/e2e coverage so text and JSON output expose the same enriched retrieval package cleanly.

### Debug Log References

- 2026-03-14: Story context generated via the `bmad-create-story` workflow for backlog story `2-3-present-agent-friendly-ranked-retrieval-results`.
- 2026-03-14: Story moved to `in-progress` via `dev-story`; implementation started from the first incomplete task.
- 2026-03-14: Red phase: `PYTHONPATH=src pytest -q tests/unit/application/test_format_results.py`
- 2026-03-14: Story suite: `PYTHONPATH=src pytest -q tests/unit/application/test_format_results.py tests/unit/application/test_run_lexical_query.py tests/unit/cli/test_query.py tests/unit/infrastructure/test_sqlite_fts5_query_engine.py tests/integration/query/test_run_lexical_query_integration.py`
- 2026-03-14: E2E validation: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --with pytest pytest -q tests/e2e/test_query_lexical.py`
- 2026-03-14: Full regression: `PYTHONPATH=src pytest -q`
- 2026-03-14: Lint: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run ruff check src tests`
- 2026-03-14: Review-fix validation: `PYTHONPATH=src pytest -q tests/unit/application/test_format_results.py tests/unit/application/test_run_lexical_query.py tests/unit/infrastructure/test_sqlite_fts5_query_engine.py tests/unit/cli/test_query.py`
- 2026-03-14: Final regression after review fixes: `PYTHONPATH=src pytest -q`
- 2026-03-14: Final lint after review fixes: `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run ruff check src tests`

### Completion Notes List

- Added shared retrieval-package DTOs plus a dedicated `format_results` layer so lexical query output now lands in one reusable agent-friendly contract.
- Enriched lexical results from persisted chunk metadata and chunk payload artifacts only, including compact previews, span metadata, FTS5-backed lexical evidence, and stable failures for missing metadata or payload artifacts.
- Kept the CLI thin by moving presentation assembly out of the command path, updating text rendering to mirror JSON fields, and preserving the standard success/failure envelope on `stdout`.
- Added mirrored unit, integration, and e2e coverage for formatter behavior, rank-preserving chunk lookup, persisted-artifact fidelity after live-repo changes, missing metadata/payload failures, and text/JSON output parity.
- Fixed review findings by bounding retrieval packages to the top 20 ranked hits and surfacing `total_match_count` / `truncated` diagnostics for broad queries.
- Replaced bracket-only explanation detection with explicit FTS5 highlight markers so path-only hits no longer fabricate content-match explanations when source code contains literal `[` / `]`.
- Verified the final state with `PYTHONPATH=src pytest -q` (`115 passed`) and `uv run ruff check src tests`.

### File List

- _bmad-output/implementation-artifacts/2-3-present-agent-friendly-ranked-retrieval-results.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- docs/cli-reference.md
- src/codeman/application/ports/chunk_store_port.py
- src/codeman/application/ports/lexical_query_port.py
- src/codeman/application/query/__init__.py
- src/codeman/application/query/format_results.py
- src/codeman/application/query/run_lexical_query.py
- src/codeman/bootstrap.py
- src/codeman/cli/query.py
- src/codeman/contracts/errors.py
- src/codeman/contracts/retrieval.py
- src/codeman/infrastructure/indexes/lexical/sqlite_fts5_query_engine.py
- src/codeman/infrastructure/persistence/sqlite/repositories/chunk_repository.py
- tests/e2e/test_query_lexical.py
- tests/integration/query/test_run_lexical_query_integration.py
- tests/unit/application/test_format_results.py
- tests/unit/application/test_run_lexical_query.py
- tests/unit/cli/test_query.py
- tests/unit/infrastructure/test_sqlite_fts5_query_engine.py

## Senior Developer Review (AI)

### Review Date

2026-03-14

### Outcome

Approve

### Summary

- Verified the Story 2.3 acceptance criteria against the implementation, docs, and automated coverage after the review-fix pass.
- Confirmed the retrieval package now stays compact by returning only the top-ranked result window while reporting total-match diagnostics for broader queries.
- Confirmed lexical explanations now rely on explicit FTS5 highlight markers instead of a raw bracket heuristic, preventing fabricated content evidence.

### Action Items

- [x] [Medium] Bound broad-query result packages so the lexical path does not emit arbitrarily large payloads or artifact reads.
- [x] [High] Keep explanation assembly truthful when repository content includes literal square brackets.

## Change Log

- 2026-03-14: Implemented Story 2.3 shared retrieval packaging, persisted-artifact lexical enrichment, CLI/docs updates, and mirrored automated coverage; story moved to `review`.
- 2026-03-14: Resolved code review findings for bounded result packaging and truthful lexical explanation evidence; story marked `done`.
