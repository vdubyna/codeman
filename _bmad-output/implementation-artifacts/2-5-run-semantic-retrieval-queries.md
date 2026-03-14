# Story 2.5: Run Semantic Retrieval Queries

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want to run semantic queries against the indexed repository,
so that I can retrieve relevant code context even when my query does not exactly match symbols or file text.

## Acceptance Criteria

1. Given a repository with completed semantic indexing artifacts, when I run a semantic query through the CLI, then codeman returns ranked semantic matches from the vector index, and each result remains traceable to the original chunk and source file.
2. Given a semantic query run completes, when I inspect the recorded run metadata, then I can identify the embedding provider, model version, and query latency associated with that result set, and the output remains consistent with the shared retrieval result contract.

## Tasks / Subtasks

- [x] Introduce the semantic query contracts, use case, and CLI surface. (AC: 1, 2)
  - [x] Extend `src/codeman/contracts/retrieval.py` with semantic-query request/result DTOs, ranked semantic match diagnostics, and additive semantic build metadata on the shared retrieval package without breaking lexical output contracts.
  - [x] Add stable semantic query failure handling in `src/codeman/contracts/errors.py`, `src/codeman/application/query/run_semantic_query.py`, and `src/codeman/cli/query.py`, including missing repository, missing current semantic baseline, missing vector artifact, and missing chunk metadata/payload paths.
  - [x] Wire `uv run codeman query semantic <repository-id> "<query>"` plus the explicit `--query` escape hatch through `src/codeman/bootstrap.py` and the existing Typer query group.

- [x] Resolve the current semantic build for the current repository/config and generate a query embedding with the same provider lineage. (AC: 1, 2)
  - [x] Reuse `build_semantic_indexing_fingerprint(config.semantic_indexing)` and `SemanticIndexBuildStorePort.get_latest_build_for_repository(repository_id, fingerprint)` so semantic queries only run against the current snapshot/config pair and never silently fall back to stale semantic artifacts.
  - [x] Add a dedicated query-embedding path to the embedding-provider boundary instead of faking a `SemanticEmbeddingDocument` or inventing chunk metadata for the query vector; the same provider/model/version and vector dimension used for the resolved semantic build must be used for query execution.
  - [x] Preserve explicit local-provider gating; if the current semantic config does not resolve to an allowed local provider/model path, fail safely with the existing provider-safe behavior instead of silently sending repository-derived data or query text to an external provider.

- [x] Execute deterministic semantic ranking against the persisted vector artifact and enrich results from persisted chunk artifacts only. (AC: 1, 2)
  - [x] Add a narrow semantic-query port plus a concrete adapter under `src/codeman/infrastructure/indexes/vector/` for the current `sqlite-exact` artifact that reads `semantic_vectors`, computes exact similarity over stored embeddings, orders results deterministically, and returns top-k ranked chunk ids with score and latency.
  - [x] Keep query behavior behind a query-specific port/adapter; do not overload `SqliteExactVectorIndexBuilder` with query responsibilities.
  - [x] Resolve ranked chunk ids back through `ChunkStorePort.get_by_chunk_ids()` and `ArtifactStorePort.read_chunk_payload()` so previews, spans, and source references come from persisted snapshot artifacts rather than live repository files.

- [x] Reuse the shared retrieval package and document operator-visible semantic metadata. (AC: 1, 2)
  - [x] Extend `src/codeman/application/query/format_results.py` with a semantic formatting path that keeps the same result item shape established in Story 2.3 and uses truthful semantic explanations.
  - [x] Surface `provider_id`, `model_id`, `model_version`, `vector_engine`, `semantic_config_fingerprint`, `build_id`, `snapshot_id`, and `query_latency_ms` in the semantic result package so operators can inspect the semantic run context directly from text or JSON output.
  - [x] Keep JSON mode limited to the standard success/failure envelope on `stdout`, and mirror the same semantic metadata in the human-readable text rendering.

- [x] Update docs and add mirrored automated coverage. (AC: 1, 2)
  - [x] Update `docs/cli-reference.md` with the `query semantic` command, text output expectations, and JSON contract fields.
  - [x] Add unit coverage for provider query embeddings, semantic-query use-case orchestration, formatter behavior, CLI rendering, and exact-search ranking/tie handling.
  - [x] Add integration coverage proving semantic query output is built from persisted artifacts, fails when the current semantic baseline is missing after reindex/config drift, and switches to the latest snapshot only after a matching semantic rebuild exists.
  - [x] Add e2e coverage for `uv run codeman query semantic ...` in text and JSON modes using the deterministic local provider path already established in Story 2.4.

## Dev Notes

### Previous Story Intelligence

- Story 2.4 already established the semantic-build baseline this story must reuse: fingerprint-scoped semantic build lookup, provider/model attribution, local-first provider gating, persisted embedding documents, and `sqlite-exact` vector artifacts under `.codeman/indexes/vector/<repository-id>/<snapshot-id>/<semantic-config-fingerprint>/semantic.sqlite3`.
- Story 2.3 already established the shared agent-friendly retrieval package and `RetrievalResultFormatter`. Story 2.5 should extend that contract rather than inventing a semantic-only response schema.
- Story 2.2 already established the query-command pattern: thin Typer commands, `--query` for option-like input, current-build resolution at the repository level, clean JSON on `stdout`, and operator messages on `stderr`.
- Story 5.3 is where durable structured run manifests/logs are planned. For Story 2.5, treat the returned retrieval package and diagnostics as the "recorded run metadata" needed by the acceptance criteria instead of pulling the full run-manifest system forward.

### Current Repo State

- `src/codeman/cli/query.py` currently exposes only `query lexical`; there is no semantic query command yet.
- `src/codeman/bootstrap.py` wires `build_semantic_index` and `run_lexical_query`, but there is no `run_semantic_query` use case in the container.
- `src/codeman/contracts/retrieval.py` contains semantic build DTOs and the shared lexical retrieval package, but no semantic query request/result contracts and no semantic build metadata on the retrieval package.
- `src/codeman/application/query/format_results.py` is lexical-only today; it formats `RunLexicalQueryResult` and has no semantic-result path.
- `src/codeman/application/ports/` contains `lexical_query_port.py`, `embedding_provider_port.py`, `semantic_index_build_store_port.py`, and `vector_index_port.py`, but no semantic-query port.
- `src/codeman/infrastructure/indexes/vector/sqlite_exact_builder.py` builds the vector artifact and stores metadata plus `embedding_json` rows in `semantic_vectors`, but there is no query adapter that reads those artifacts.
- `src/codeman/infrastructure/embeddings/local_hash_provider.py` only embeds persisted source documents today. There is no query-specific embedding method, which means Story 2.5 must add one rather than abusing document-embedding DTOs for query text.
- `src/codeman/infrastructure/persistence/sqlite/repositories/semantic_index_build_repository.py` already resolves the latest semantic build by repository and semantic-config fingerprint. That freshness logic should remain the source of truth for semantic query readiness.
- `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py` already supports `read_chunk_payload()` and `read_embedding_documents()`, so semantic query can reuse persisted artifacts rather than creating new preview formats.
- `docs/cli-reference.md` documents `index build-semantic` and `query lexical`, but not the semantic query surface yet.

### Technical Guardrails

- Keep the public interface CLI-only. This story must not introduce HTTP endpoints, MCP transport, background workers, or daemonized retrieval services. [Source: docs/architecture/decisions.md; _bmad-output/planning-artifacts/prd.md - Project Classification; _bmad-output/planning-artifacts/architecture.md - API & Communication Patterns]
- Preserve the modular-monolith layering already used in the repo: CLI parses/renders, application orchestrates, ports describe boundaries, infrastructure owns vector/SQLite/provider behavior, and contracts remain the stable DTO layer. [Source: docs/architecture/patterns.md; docs/project-context.md; src/codeman/bootstrap.py]
- `bootstrap.py` remains the single composition root. Wire new semantic-query collaborators there instead of constructing them inside CLI commands or tests. [Source: docs/architecture/decisions.md; docs/architecture/patterns.md; src/codeman/bootstrap.py]
- Resolve the current semantic build through `SemanticIndexBuildStorePort.get_latest_build_for_repository(repository_id, semantic_config_fingerprint)` and fail clearly if the latest snapshot/config pair does not have a matching semantic build yet. Do not query stale artifacts from an older snapshot, and do not rebuild semantic artifacts implicitly inside the query path. [Source: src/codeman/infrastructure/persistence/sqlite/repositories/semantic_index_build_repository.py; _bmad-output/implementation-artifacts/2-4-build-semantic-retrieval-index-artifacts.md]
- Use the same semantic configuration fingerprinting path as Story 2.4 so the query is bound to the same provider/model/vector-engine context as the resolved build. Changing `CODEMAN_SEMANTIC_MODEL_VERSION`, vector dimension, provider id, or other fingerprint inputs must invalidate the previous baseline until a matching semantic rebuild exists. [Source: src/codeman/config/semantic_indexing.py; tests/integration/indexing/test_build_semantic_index_integration.py]
- Do not fake query embeddings by inventing chunk ids, source-file ids, or payload metadata. Query text is not a repository chunk and needs its own provider boundary path. The query vector must be produced with the same provider lineage as the stored corpus vectors. [Source: src/codeman/application/ports/embedding_provider_port.py; src/codeman/infrastructure/embeddings/local_hash_provider.py; https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html]
- Keep provider usage explicit and local-first. If the current semantic provider is unavailable or points to a non-readable local path, fail with a stable user-safe error instead of silently enabling OpenAI or another external provider. [Source: docs/project-context.md; docs/architecture/decisions.md; src/codeman/application/indexing/build_embeddings.py; _bmad-output/planning-artifacts/prd.md - NFR5, NFR8]
- Keep the semantic query source of truth artifact-only: rank against the persisted vector index artifact, then enrich results from persisted chunk metadata and chunk payload artifacts. Do not reread mutable working-tree files and do not rescan the repository tree during query execution. [Source: docs/project-context.md; src/codeman/infrastructure/indexes/vector/sqlite_exact_builder.py; src/codeman/infrastructure/artifacts/filesystem_artifact_store.py; src/codeman/application/query/run_lexical_query.py]
- Keep the shared retrieval contract stable and additive. Do not create a second semantic-only success payload that Story 2.6 or future MCP reuse would have to special-case. [Source: docs/project-context.md; docs/architecture/patterns.md; _bmad-output/implementation-artifacts/2-3-present-agent-friendly-ranked-retrieval-results.md]
- Preserve compact result packaging. The default package should stay bounded and agent-usable instead of dumping full embedding artifacts or full file contents. Reuse the existing top-k default behavior unless an additive query option is explicitly justified. [Source: docs/cli-reference.md; _bmad-output/implementation-artifacts/2-3-present-agent-friendly-ranked-retrieval-results.md]
- Keep semantic explanations truthful. Describe that the chunk ranked highly due to embedding similarity against the persisted semantic index; do not imply lexical evidence, fusion logic, or model reasoning that the system did not compute. [Source: _bmad-output/planning-artifacts/epics.md - Story 2.3; Story 2.5; src/codeman/application/query/format_results.py]
- Do not pull hybrid fusion, compare-mode orchestration, reusable retrieval profiles, structured run manifests, or benchmark reporting into this story. Those belong to Stories 2.6, 2.7, Epic 3, and Epic 5. [Source: _bmad-output/planning-artifacts/epics.md - Story 2.6; Story 2.7; Story 3.1-3.6; Story 5.3]

### Architecture Compliance

- Query orchestration belongs in `src/codeman/application/query/`, while lexical/vector engines stay behind ports and concrete adapters. [Source: _bmad-output/planning-artifacts/architecture.md - Integration Points; Project Structure & Boundaries]
- Runtime-generated indexes and query inputs stay under `.codeman/`; no generated state belongs in `src/`, `tests/fixtures/`, or the indexed target repository. [Source: docs/project-context.md; docs/architecture/patterns.md; src/codeman/runtime.py]
- Boundary DTOs should stay strict Pydantic models with predictable `snake_case` fields. Prefer additive fields on shared contracts over shape-breaking changes. [Source: docs/project-context.md; docs/architecture/decisions.md]
- Query failures must cross the application boundary as typed project errors with stable error codes and exit codes. Do not leak raw SQLite/provider exceptions to the CLI. [Source: docs/project-context.md; _bmad-output/planning-artifacts/architecture.md - Error Handling Patterns]

### Library / Framework Requirements

- Keep Typer usage consistent with the existing query command group: thin commands, `get_container(ctx)`, one use case call, and shared envelope helpers for JSON mode. [Source: docs/project-context.md; src/codeman/cli/query.py]
- Reuse Pydantic contract style with `ConfigDict(extra="forbid")` for new semantic query DTOs and diagnostics. [Source: docs/project-context.md; src/codeman/contracts/retrieval.py]
- Use `pathlib.Path` and runtime path helpers for artifact access; do not thread raw strings through new ports when a path is the real type. [Source: docs/project-context.md; src/codeman/runtime.py]
- The Sentence Transformers semantic-search guidance explicitly separates corpus/document embeddings from query embeddings (`encode_document` vs `encode_query`) and describes exact semantic search over small corpora with top-k ranking. Inference: the cleanest local-first fit for Story 2.5 is a dedicated query-embedding path plus an exact-search adapter over the existing corpus embeddings, not a shortcut that reuses document-only APIs with fake chunk metadata. [Source: https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html]
- The same Sentence Transformers documentation notes that exact semantic search is viable for corpora up to about 1 million entries, defaults to cosine similarity, and can optimize to dot-product only when embeddings are normalized. Inference: start with an exact similarity implementation for the existing `sqlite-exact` artifact and treat normalization-based optimizations as optional follow-up work, not as an unstated invariant. [Source: https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html]
- If the vector adapter issues SQL statements against the semantic artifact, use `sqlite3` placeholders for bound values instead of string interpolation, and keep row handling simple and deterministic. [Source: https://docs.python.org/3/library/sqlite3.html]

### File / Structure Requirements

- Expected application files:
  - `src/codeman/application/query/run_semantic_query.py`
  - `src/codeman/application/query/format_results.py`
- Expected port files:
  - `src/codeman/application/ports/semantic_query_port.py`
  - `src/codeman/application/ports/embedding_provider_port.py` (extend with query embedding support)
- Expected infrastructure files:
  - `src/codeman/infrastructure/indexes/vector/sqlite_exact_query_engine.py`
  - `src/codeman/infrastructure/embeddings/local_hash_provider.py`
- Expected wiring/docs files:
  - `src/codeman/bootstrap.py`
  - `src/codeman/cli/query.py`
  - `src/codeman/contracts/retrieval.py`
  - `src/codeman/contracts/errors.py`
  - `docs/cli-reference.md`
- Expected tests:
  - `tests/unit/application/test_run_semantic_query.py`
  - `tests/unit/infrastructure/test_sqlite_exact_vector_query_engine.py`
  - `tests/unit/cli/test_query.py`
  - `tests/integration/query/test_run_semantic_query_integration.py`
  - `tests/e2e/test_query_semantic.py`

### Testing Requirements

- Add unit coverage for semantic build resolution, query embedding generation, additive retrieval-contract formatting, empty-result handling, deterministic ranking, and stable error mapping.
- Add unit coverage for the vector query adapter that exercises exact similarity scoring, descending score order, deterministic tie-breaking, top-k truncation, and malformed/missing artifact behavior.
- Add integration coverage proving semantic query output uses persisted chunk payload artifacts even if the live repository changes after semantic indexing.
- Add an integration test showing that after reindex creates a newer snapshot but before `build-semantic` runs for that snapshot/config, semantic query fails with the expected missing-baseline error instead of silently using the older semantic build.
- Add an integration test showing that after the matching semantic rebuild exists, semantic query resolves the new snapshot/build successfully.
- Add a configuration-drift test: if semantic fingerprint inputs change (for example model version or vector dimension), querying should require a matching rebuild instead of using the old build.
- Add failure-path tests for missing semantic artifact files, missing chunk metadata, missing chunk payloads, and unavailable local providers.
- Add e2e coverage for `uv run codeman query semantic ...` in both text and JSON modes, asserting provider/model attribution, retrieval-mode labeling, latency reporting, clean `stdout`/`stderr` separation, and stable structured output.

### Git Intelligence Summary

- Recent implementation history favors additive, narrowly scoped changes: one focused use case, one or two narrow ports/adapters, `bootstrap.py` wiring, and mirrored unit/integration/e2e coverage instead of broad refactors.
- Commit `c05aeea` (`story(2-4-build-semantic-retrieval-index-artifacts): complete code review and mark done`) is the immediate baseline. Story 2.5 should consume the semantic artifact/build metadata it introduced instead of redefining semantic storage or freshness rules.
- Commit `0f0f4c1` (`story(2-3-present-agent-friendly-ranked-retrieval-results): complete code review and mark done`) matters because Story 2.5 should plug semantic results into the same retrieval package rather than inventing a second presentation layer.
- Commit `8de17fc` (`story(2-2-run-lexical-retrieval-against-indexed-chunks): complete code review and mark done`) remains the best query-command baseline for CLI behavior, error mapping, and repository-scoped build resolution.

### Latest Technical Information

- The official Sentence Transformers semantic-search documentation says manual/exact semantic search is appropriate for small corpora "up to about 1 million entries" by embedding the corpus and the query, then computing semantic similarity. Inference: the current `sqlite-exact` artifact is an acceptable MVP baseline for Story 2.5, and this story does not need to introduce ANN infrastructure just to satisfy semantic querying. [Source: https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html]
- The same documentation states that `semantic_search()` defaults to cosine similarity and returns top-k ranked results, with `query_chunk_size`, `corpus_chunk_size`, and `top_k` controlling the search shape. Inference: Story 2.5 should keep an explicit top-k contract and deterministic semantic ranking rather than returning an unbounded result set. [Source: https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html]
- Sentence Transformers also documents that normalized query/corpus embeddings can switch scoring to dot product for speed. Inference: if Story 2.5 takes advantage of the current normalized local-hash vectors, it should do so only through an explicit, test-proven invariant; otherwise, exact cosine similarity is the safer default. [Source: https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html]
- The Python `sqlite3` documentation explicitly recommends parameter substitution with placeholders instead of string formatting and recommends setting `Connection.row_factory` if row objects are needed. Inference: keep any SQL interaction in the semantic query adapter parameterized and straightforward rather than building ad hoc SQL strings or custom parsing layers. [Source: https://docs.python.org/3/library/sqlite3.html]

### Project Context Reference

- `docs/project-context.md` is present and is the canonical agent-facing implementation guide for this repository. It explicitly says to treat current code and tests as the source of truth, keep runtime artifacts inside `.codeman/`, preserve deterministic ordering, and avoid assuming planned surfaces are already implemented.
- `docs/README.md` is the documentation ownership map, and `docs/architecture/decisions.md` plus `docs/architecture/patterns.md` define the stable layering and extension rules this story must preserve.
- No separate UX design artifact exists for this project. Story 2.5 is a CLI/data-flow story, so UX requirements are limited to clear operator messaging, safe failures, and machine-stable JSON/text output.

### References

- [Source: docs/project-context.md]
- [Source: docs/README.md]
- [Source: docs/cli-reference.md]
- [Source: docs/architecture/decisions.md]
- [Source: docs/architecture/patterns.md]
- [Source: _bmad-output/planning-artifacts/epics.md - Epic 2; Story 2.3; Story 2.4; Story 2.5; Story 2.6; Story 2.7; Story 5.3]
- [Source: _bmad-output/planning-artifacts/prd.md - Executive Summary; Functional Requirements FR8/FR10; NFR2; NFR3; NFR5; NFR8; NFR20]
- [Source: _bmad-output/planning-artifacts/architecture.md - Data Architecture; API & Communication Patterns; Integration Points; Process Patterns; Requirements Coverage Validation]
- [Source: _bmad-output/implementation-artifacts/2-2-run-lexical-retrieval-against-indexed-chunks.md]
- [Source: _bmad-output/implementation-artifacts/2-3-present-agent-friendly-ranked-retrieval-results.md]
- [Source: _bmad-output/implementation-artifacts/2-4-build-semantic-retrieval-index-artifacts.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/runtime.py]
- [Source: src/codeman/cli/query.py]
- [Source: src/codeman/contracts/retrieval.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: src/codeman/config/semantic_indexing.py]
- [Source: src/codeman/application/query/format_results.py]
- [Source: src/codeman/application/query/run_lexical_query.py]
- [Source: src/codeman/application/indexing/build_embeddings.py]
- [Source: src/codeman/application/indexing/build_semantic_index.py]
- [Source: src/codeman/application/indexing/build_vector_index.py]
- [Source: src/codeman/application/ports/artifact_store_port.py]
- [Source: src/codeman/application/ports/embedding_provider_port.py]
- [Source: src/codeman/application/ports/vector_index_port.py]
- [Source: src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- [Source: src/codeman/infrastructure/embeddings/local_hash_provider.py]
- [Source: src/codeman/infrastructure/indexes/vector/sqlite_exact_builder.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/semantic_index_build_repository.py]
- [Source: tests/integration/indexing/test_build_semantic_index_integration.py]
- [Source: tests/unit/application/test_build_semantic_index.py]
- [Source: tests/e2e/test_index_build_semantic.py]
- [Source: git log --oneline -5]
- [Source: https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html]
- [Source: https://docs.python.org/3/library/sqlite3.html]

## Story Completion Status

- Status set to `done`.
- Semantic query implementation completed, review findings resolved, and full story validation completed.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Implementation Plan

- Extend the shared retrieval contracts with semantic query DTOs and semantic build metadata while preserving the lexical result item shape.
- Add a dedicated semantic query use case, query-specific port, and `sqlite-exact` adapter that rank persisted vectors and resolve previews only from chunk artifacts.
- Wire `query semantic` through `bootstrap.py`, then mirror the change in CLI docs plus unit, integration, and e2e coverage.

### Debug Log References

- 2026-03-14: Story context generated via the `bmad-create-story` workflow for backlog story `2-5-run-semantic-retrieval-queries`.
- 2026-03-14: Updated sprint tracking to `in-progress`, implemented semantic query contracts/use case/CLI wiring, and added a query-specific `sqlite-exact` adapter.
- 2026-03-14: Validated the story with `uv run --group dev pytest -q` (`154 passed`), targeted semantic e2e coverage, and `uv run --group dev ruff check`.
- 2026-03-14: Resolved review findings by validating query embedding lineage against the resolved build, detecting corrupt/truncated semantic vector artifacts, and rerunning full regression validation.

### Completion Notes List

- Comprehensive semantic-query implementation guidance assembled from sprint status, epics, PRD, architecture, existing code, previous stories, tests, git history, and current official technical references.
- Added `query semantic` with `--query` support, stable failure mapping, additive semantic retrieval metadata, and truthful semantic result explanations.
- Added a dedicated provider query-embedding path and artifact-only semantic ranking flow that respects the current repository snapshot and semantic configuration fingerprint.
- Added mirrored unit, integration, and e2e coverage for semantic query orchestration, provider embeddings, exact ranking, CLI rendering, baseline drift failures, and rebuild recovery.
- Resolved the review finding that allowed mismatched query embedding lineage to reach scoring by rejecting provider/model/version/vector-dimension drift before query execution.
- Resolved the review finding that let damaged vector artifacts look like empty result sets by validating persisted metadata and row counts before ranking.
- Revalidated the story with `uv run --group dev pytest -q` (`158 passed`) and `uv run --group dev ruff check`; `ruff format --check` is clean for the changed Python files, while the full repo-wide format check still reports older unrelated drift outside this story.

### File List

- _bmad-output/implementation-artifacts/2-5-run-semantic-retrieval-queries.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- docs/cli-reference.md
- src/codeman/application/indexing/build_embeddings.py
- src/codeman/application/ports/embedding_provider_port.py
- src/codeman/application/ports/semantic_query_port.py
- src/codeman/application/query/format_results.py
- src/codeman/application/query/run_semantic_query.py
- src/codeman/bootstrap.py
- src/codeman/cli/query.py
- src/codeman/contracts/errors.py
- src/codeman/contracts/retrieval.py
- src/codeman/infrastructure/embeddings/local_hash_provider.py
- src/codeman/infrastructure/indexes/vector/sqlite_exact_query_engine.py
- tests/e2e/test_query_semantic.py
- tests/integration/query/test_run_semantic_query_integration.py
- tests/unit/application/test_format_results.py
- tests/unit/application/test_run_semantic_query.py
- tests/unit/cli/test_query.py
- tests/unit/infrastructure/test_local_hash_provider.py
- tests/unit/infrastructure/test_sqlite_exact_vector_query_engine.py

## Change Log

- 2026-03-14: Implemented semantic retrieval queries end-to-end, updated CLI documentation, added semantic query metadata to the shared retrieval contract, and added unit/integration/e2e coverage.
- 2026-03-14: Addressed code review findings for query embedding lineage validation and corrupt semantic artifact detection, reran full validation, and marked the story done.
