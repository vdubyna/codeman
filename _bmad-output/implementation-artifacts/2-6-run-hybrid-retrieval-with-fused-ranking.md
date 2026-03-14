# Story 2.6: Run Hybrid Retrieval with Fused Ranking

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want to run hybrid retrieval that combines lexical and semantic signals,
so that I can get stronger results than either method alone for mixed repository questions.

## Acceptance Criteria

1. Given both lexical and semantic retrieval capabilities are available, when I run a hybrid query, then codeman combines results from both retrieval strategies into one ranked output, and the fusion process produces a stable final ordering for the same query and configuration context.
2. Given one retrieval path is unavailable or degraded, when a hybrid query is attempted, then codeman returns a clear failure or degradation message according to the configured behavior, and does not pretend the result came from full hybrid fusion if it did not.

## Tasks / Subtasks

- [x] Add hybrid retrieval contracts, typed errors, and a deterministic fusion policy. (AC: 1, 2)
  - [x] Extend `src/codeman/contracts/retrieval.py` with `RunHybridQueryRequest`, `RunHybridQueryResult`, `HybridRetrievalBuildContext`, and `HybridQueryDiagnostics`, keeping lexical and semantic response shapes unchanged.
  - [x] Add stable hybrid-query failure handling in `src/codeman/contracts/errors.py` and `src/codeman/application/query/run_hybrid_query.py` for missing component baselines, mixed-snapshot builds, unavailable providers/artifacts, and truthfully labeled degraded behavior.
  - [x] Implement a narrow, pure fusion helper that uses rank-based fusion rather than raw score blending, applies explicit deterministic tie-breakers, and uses a bounded internal candidate window larger than the final output size.

- [x] Compose lexical and semantic retrieval into one attributable hybrid flow. (AC: 1, 2)
  - [x] Reuse the current lexical and semantic query orchestration paths, or extract the smallest shared helper needed from them, instead of duplicating repository/build/artifact resolution logic in the CLI.
  - [x] Request a larger internal per-mode candidate window for fusion (for example 50) and then truncate the final hybrid package to the user-visible top-k contract (default 20).
  - [x] Require the lexical and semantic paths to resolve the same repository and snapshot before fusion; if either path points to a different snapshot or stale build, fail clearly instead of fusing mixed-state evidence.
  - [x] Treat a successful zero-match path as valid input to fusion, but treat missing baseline, missing artifact, corrupt artifact, or unavailable provider failures as unavailable/degraded paths and surface them explicitly.

- [x] Add the hybrid CLI surface and truthful operator output. (AC: 1, 2)
  - [x] Wire `uv run codeman query hybrid <repository-id> "<query>"` plus the explicit `--query` escape hatch through `src/codeman/bootstrap.py` and `src/codeman/cli/query.py`.
  - [x] Keep JSON mode on the standard success/failure envelopes, with `stdout` reserved for the final JSON payload and progress/diagnostics on `stderr`.
  - [x] Surface hybrid provenance in text and JSON output: fusion strategy, deterministic fusion parameters, lexical/semantic build provenance, component latencies/counts, and explanations that say whether a result came from lexical only, semantic only, or both.

- [x] Update docs and add mirrored automated coverage. (AC: 1, 2)
  - [x] Update `docs/cli-reference.md` with the `query hybrid` command, text output expectations, JSON contract fields, and strict failure/degraded-output behavior.
  - [x] Add unit coverage for fusion scoring, duplicate chunk merging, one-path-empty behavior, mixed-snapshot failure, deterministic tie-breaking, and truthful result explanations.
  - [x] Add integration coverage proving hybrid results are built from persisted artifacts only, fail when lexical and semantic baselines do not refer to the same snapshot, and succeed again once both paths are rebuilt for the same snapshot.
  - [x] Add e2e coverage for `uv run codeman query hybrid ...` in text and JSON modes using the deterministic local semantic provider path already established in Story 2.4 and Story 2.5.

## Dev Notes

### Previous Story Intelligence

- Story 2.5 already established the semantic-query baseline: fingerprint-scoped semantic build lookup, local-only provider gating, provider/model/version attribution, persisted-artifact-only result enrichment, and stable failure handling for missing/corrupt semantic artifacts.
- Story 2.2 already established the lexical-query baseline: thin Typer command flow, repository-scoped lexical build resolution, clear JSON `stdout` versus operational `stderr`, and stable lexical error mapping.
- Story 2.3 already established the shared retrieval package and compact result-item shape. Story 2.6 should extend that package with a hybrid mode rather than inventing a second output schema.
- Story 2.7 owns the dedicated comparison workflow. Story 2.6 should return one fused result set, not side-by-side lexical/semantic/hybrid comparisons.
- Epic 3 owns user-facing retrieval profile/configuration work. Story 2.6 should not invent a new `config` surface just to toggle hybrid fallback policies.

### Current Repo State

- `src/codeman/cli/query.py` currently exposes only `query lexical` and `query semantic`; there is no `query hybrid` command yet.
- `src/codeman/bootstrap.py` wires `run_lexical_query` and `run_semantic_query`, but there is no `run_hybrid_query` use case in the container.
- `src/codeman/contracts/retrieval.py` already reserves `RetrievalMode = Literal["lexical", "semantic", "hybrid"]`, but it has no hybrid request/result DTOs, no hybrid diagnostics, and no hybrid build context.
- `src/codeman/application/query/` contains `run_lexical_query.py`, `run_semantic_query.py`, and `format_results.py`; there is no hybrid orchestration or fusion helper yet.
- `src/codeman/contracts/errors.py` has lexical and semantic query codes only; there are no hybrid-specific error codes today.
- `docs/cli-reference.md` documents `query lexical` and `query semantic`, but not `query hybrid`.
- `src/codeman/cli/compare.py` is still a placeholder. Do not move Story 2.7 compare behavior into Story 2.6.
- `src/codeman/domain/` exists only as a placeholder package right now; there is no established retrieval-domain module to extend yet. Prefer the smallest extension that fits the current code layout.

### Technical Guardrails

- Keep the interface CLI-only. This story must not introduce HTTP endpoints, MCP transport, background workers, or daemonized retrieval services. [Source: docs/architecture/decisions.md; _bmad-output/planning-artifacts/prd.md]
- Reuse the existing lexical and semantic query paths instead of duplicating index access, repository resolution, or artifact loading. Hybrid should compose proven behavior, not re-implement it. [Source: src/codeman/application/query/run_lexical_query.py; src/codeman/application/query/run_semantic_query.py; src/codeman/bootstrap.py]
- Fuse by rank, not by raw score. Lexical BM25-style scores and semantic cosine similarity scores are not directly comparable, so do not add or average them as if they lived on the same scale. [Source: https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking; https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion]
- Use a deterministic fusion strategy, with Reciprocal Rank Fusion as the default baseline unless implementation discovery proves a better already-existing project abstraction. The fusion helper must produce stable output for the same ranked inputs and candidate window. [Source: https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/; https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion]
- Require both retrieval paths to refer to the same repository snapshot before fusion. If lexical and semantic builds point to different snapshots or revision identities, fail clearly instead of returning a misleading "hybrid" result set. This is especially important because lexical and semantic baseline freshness rules are currently resolved independently. [Source: src/codeman/application/query/run_lexical_query.py; src/codeman/application/query/run_semantic_query.py; _bmad-output/planning-artifacts/prd.md - NFR10, NFR11]
- A path that returns zero matches successfully is not degraded; it is a valid result. Degradation/unavailability means missing baseline, missing or corrupt artifact, provider failure, or an attribution mismatch that prevents truthful fusion.
- Because Epic 3 has not delivered retrieval profiles yet, assume the current configured behavior is strict failure by default. If you leave room for future fallback modes, keep that design internal/additive and off by default rather than exposing a premature config surface.
- Keep hybrid provenance explicit. Since there is no persisted hybrid build store yet, do not invent one in this story. Instead, expose a deterministic synthetic hybrid context id derived from the lexical and semantic build ids, and surface both component build ids explicitly in the hybrid build metadata.
- Keep hybrid output truthful. If only one path contributes to a specific fused result, say so in the explanation. If a permissive degraded-success mode is ever added later, it must mark the result package as degraded and identify the failed path instead of pretending full hybrid fusion occurred.
- Keep hybrid result enrichment artifact-only. Rank/fuse against persisted query outputs and persisted chunk artifacts; do not reread mutable working-tree files or rescan the repository during hybrid query execution. [Source: docs/project-context.md; src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- Do not pull compare-mode orchestration, benchmark/reporting work, structured run manifests, or configurable retrieval profiles into this story. Those belong to Story 2.7, Epic 4, Story 5.3, and Epic 3 respectively. [Source: _bmad-output/planning-artifacts/epics.md]

### Architecture Compliance

- Query orchestration belongs in `src/codeman/application/query/`, while lexical and semantic engines remain behind the existing query ports and concrete adapters. [Source: docs/architecture/patterns.md; _bmad-output/planning-artifacts/architecture.md - Service Boundaries]
- `bootstrap.py` remains the single composition root. Wire the hybrid use case there instead of constructing dependencies inside CLI commands or tests. [Source: docs/architecture/decisions.md; src/codeman/bootstrap.py]
- Keep boundary DTOs strict and additive with `ConfigDict(extra="forbid")`. Do not break lexical or semantic JSON output shapes while adding hybrid contracts. [Source: docs/project-context.md; src/codeman/contracts/retrieval.py]
- The current implemented extension pattern does not yet use retrieval-specific domain modules. Prefer a focused pure helper adjacent to query orchestration such as `src/codeman/application/query/hybrid_fusion.py`; only introduce `src/codeman/domain/retrieval/fusion.py` if the change stays minimal, clearly improves reuse, and does not create a large parallel structure ahead of need. [Source: docs/architecture/patterns.md; docs/project-context.md; _bmad-output/planning-artifacts/architecture.md]
- Runtime-generated artifacts and indexes stay under `.codeman/`; no hybrid output state belongs in `src/`, `tests/fixtures/`, or the indexed target repository. [Source: docs/project-context.md; src/codeman/runtime.py]
- Hybrid query failures must cross the application boundary as typed project errors with stable error codes and exit codes. Do not leak raw lexical, semantic, SQLite, or provider exceptions to the CLI. [Source: docs/project-context.md; src/codeman/contracts/errors.py]

### Library / Framework Requirements

- Keep Typer usage consistent with the existing query command group: thin commands, `get_container(ctx)`, one use case call, shared envelope helpers, and the existing positional query plus `--query` escape hatch pattern. [Source: docs/project-context.md; src/codeman/cli/query.py]
- Reuse Pydantic contract style with strict models and additive fields for new hybrid DTOs and diagnostics. [Source: docs/project-context.md; src/codeman/contracts/retrieval.py]
- Use `pathlib.Path` and runtime path helpers when touching artifacts; do not thread raw path strings through new code paths when a path is the real type. [Source: docs/project-context.md; src/codeman/runtime.py]
- Use `time.perf_counter()` for hybrid end-to-end latency so component and overall timing semantics stay aligned with the existing lexical and semantic query adapters. [Source: src/codeman/infrastructure/indexes/lexical/sqlite_fts5_query_engine.py; src/codeman/infrastructure/indexes/vector/sqlite_exact_query_engine.py]
- The original RRF paper introduced reciprocal-rank-based fusion as a strong, simple baseline for combining independently ranked result lists. Inference: Story 2.6 should start with RRF rather than inventing a score-normalization heuristic for BM25 and semantic similarity. [Source: https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/]
- Azure AI Search documents that hybrid search uses Reciprocal Rank Fusion because full-text and vector results produce different ranking-score ranges. Inference: raw lexical and semantic scores should stay diagnostic only; hybrid ranking should be driven by rank positions. [Source: https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking]
- Elasticsearch documents `rank_window_size` and `rank_constant` for RRF and notes that only the top documents from each child retriever contribute to the final ranking. Inference: use an internal fusion candidate window larger than the final user-visible top-k so fusion has enough evidence without exploding output size. [Source: https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion]

### File / Structure Requirements

- Expected application files:
  - `src/codeman/application/query/run_hybrid_query.py`
  - `src/codeman/application/query/format_results.py`
  - `src/codeman/application/query/hybrid_fusion.py` (preferred current-layout helper)
- Expected wiring/docs files:
  - `src/codeman/bootstrap.py`
  - `src/codeman/cli/query.py`
  - `src/codeman/contracts/retrieval.py`
  - `src/codeman/contracts/errors.py`
  - `docs/cli-reference.md`
- Expected tests:
  - `tests/unit/application/test_run_hybrid_query.py`
  - `tests/unit/application/test_hybrid_fusion.py`
  - `tests/unit/cli/test_query.py`
  - `tests/integration/query/test_run_hybrid_query_integration.py`
  - `tests/e2e/test_query_hybrid.py`

### Testing Requirements

- Add unit coverage for the pure fusion helper: rank-based score calculation, duplicate chunk merging across lexical and semantic lists, deterministic tie-breaking, candidate-window truncation, and the one-path-empty case.
- Add unit coverage for hybrid orchestration: component query invocation, same-snapshot enforcement, strict failure behavior for missing lexical/semantic baselines, and truthful propagation of component diagnostics into the hybrid package.
- Add unit coverage for hybrid explanations so a result can state whether it came from lexical only, semantic only, or both, without implying evidence that was never computed.
- Add an integration test proving hybrid results are built from persisted artifacts even if the live repository changes after indexing, reusing the artifact-only assumptions already exercised by lexical and semantic query tests.
- Add an integration test showing that if lexical and semantic builds resolve different snapshots after reindex/rebuild drift, hybrid query fails with the expected typed error instead of fusing mixed-state results.
- Add an integration test showing that once both lexical and semantic baselines are rebuilt for the same latest snapshot, hybrid query succeeds and reports the aligned snapshot/build provenance.
- Add an integration test for the valid zero-match edge case where one path returns no matches but the other path succeeds, and confirm the hybrid package remains truthful rather than being marked degraded.
- Add e2e coverage for `uv run codeman query hybrid ...` in text and JSON modes, asserting `stdout`/`stderr` separation, fused ranking metadata, stable explanations, and JSON envelope shape.

### Git Intelligence Summary

- Recent retrieval work favors additive, narrowly scoped changes: one use case, one focused helper or adapter when needed, `bootstrap.py` wiring, and mirrored unit/integration/e2e coverage rather than broad architectural rewrites.
- Commit `5966a34` (`story(2-5-run-semantic-retrieval-queries): resolve review findings`) matters because Story 2.6 must preserve the semantic-query guardrails around provider/model lineage and corrupt-artifact detection instead of bypassing them during fusion.
- Commit `c05aeea` (`story(2-4-build-semantic-retrieval-index-artifacts): complete code review and mark done`) matters because Story 2.6 should reuse the existing semantic build artifact and fingerprint provenance rather than inventing a separate hybrid semantic path.
- Commit `0f0f4c1` (`story(2-3-present-agent-friendly-ranked-retrieval-results): complete code review and mark done`) matters because Story 2.6 should keep the shared retrieval package shape and compact agent-friendly output.
- Commit `8de17fc` (`story(2-2-run-lexical-retrieval-against-indexed-chunks): complete code review and mark done`) remains the baseline for CLI query behavior, repository-scoped build resolution, and stable exit/error mapping.

### Latest Technical Information

- Reciprocal Rank Fusion is the canonical lightweight baseline for combining independently ranked retrieval lists and is the hybrid-fusion method documented across modern search systems. Inference: it is the safest first implementation for Story 2.6 and a much better fit than ad hoc score normalization. [Source: https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/]
- Azure AI Search documents that hybrid search uses RRF to merge full-text and vector queries because their raw scoring systems differ in range and meaning. Inference: codeman should keep lexical and semantic raw scores as per-mode diagnostics, but fused ordering should depend on ranked positions. [Source: https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking]
- Elasticsearch documents `rank_window_size` as the number of top-ranked documents from each child retriever that enter the RRF calculation and `rank_constant` as the parameter that shapes how strongly high ranks dominate. Inference: Story 2.6 should keep both as localized constants or internal parameters so future benchmark work can tune them without redesigning the query flow. [Source: https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion]
- Elasticsearch also documents that only documents in the selected rank window contribute to the final fused results. Inference: hybrid fusion should request a larger internal candidate window than the final result count; otherwise fusion quality will be constrained by early truncation in the component retrieval paths. [Source: https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion]

### Project Context Reference

- `docs/project-context.md` is present and remains the canonical agent-facing implementation guide. It explicitly says to trust current code and tests first, keep runtime data under `.codeman/`, preserve deterministic ordering, and avoid treating planned surfaces as already implemented.
- `docs/README.md` remains the documentation ownership map, while `docs/architecture/decisions.md` and `docs/architecture/patterns.md` define the stable layering and extension rules this story must preserve.
- No separate UX design artifact exists for this project. Story 2.6 is a CLI/data-flow story, so UX requirements are limited to clear operator messaging, truthful degraded/failure behavior, and machine-stable JSON/text output.

### References

- [Source: docs/project-context.md]
- [Source: docs/README.md]
- [Source: docs/cli-reference.md]
- [Source: docs/architecture/decisions.md]
- [Source: docs/architecture/patterns.md]
- [Source: _bmad-output/planning-artifacts/epics.md - Epic 2; Story 2.2; Story 2.3; Story 2.4; Story 2.5; Story 2.6; Story 2.7]
- [Source: _bmad-output/planning-artifacts/prd.md - Executive Summary; FR9; FR10; FR11; FR12; NFR2; NFR10; NFR11; NFR20; NFR21]
- [Source: _bmad-output/planning-artifacts/architecture.md - Project Structure; Service Boundaries; Data Boundaries]
- [Source: _bmad-output/implementation-artifacts/2-5-run-semantic-retrieval-queries.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/cli/app.py]
- [Source: src/codeman/cli/query.py]
- [Source: src/codeman/cli/compare.py]
- [Source: src/codeman/contracts/retrieval.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: src/codeman/application/query/run_lexical_query.py]
- [Source: src/codeman/application/query/run_semantic_query.py]
- [Source: src/codeman/application/query/format_results.py]
- [Source: src/codeman/infrastructure/indexes/lexical/sqlite_fts5_query_engine.py]
- [Source: src/codeman/infrastructure/indexes/vector/sqlite_exact_query_engine.py]
- [Source: tests/unit/cli/test_query.py]
- [Source: tests/unit/application/test_run_semantic_query.py]
- [Source: tests/integration/query/test_run_semantic_query_integration.py]
- [Source: git log --oneline -5]
- [Source: https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/]
- [Source: https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking]
- [Source: https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion]

## Story Completion Status

- Status set to `ready-for-dev`.
- Completion note: `Ultimate context engine analysis completed - comprehensive developer guide created.`
- Recorded assumption: until Epic 3 introduces retrieval profiles/config layering, the default hybrid availability policy should remain strict failure rather than silent fallback.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Debug Log References

- 2026-03-14: Story context generated via the `bmad-create-story` workflow for backlog story `2-6-run-hybrid-retrieval-with-fused-ranking`.
- 2026-03-14: Implemented hybrid retrieval fusion, CLI wiring, documentation updates, and mirrored unit/integration/e2e coverage.
- 2026-03-14: Resolved code review findings for truthful hybrid truncation metadata and preserved component diagnostics in wrapped hybrid failures.

### Completion Notes List

- Comprehensive hybrid-query implementation guidance assembled from sprint status, epics, PRD, architecture, current code, previous story learnings, tests, git history, and current primary-source fusion references.
- The story intentionally keeps compare-mode, benchmark reporting, and user-facing retrieval profile configuration out of scope so the implementation stays aligned with current code and epic boundaries.
- Implemented strict hybrid-query contracts, typed failures, deterministic reciprocal-rank fusion, and same-snapshot enforcement by composing the existing lexical and semantic query flows.
- Added `query hybrid` CLI output for text and JSON modes with fusion provenance, nested component build metadata, per-component diagnostics, and truthful explanations for lexical-only, semantic-only, and dual-evidence results.
- Added mirrored automated coverage for fusion helper behavior, hybrid orchestration, CLI rendering/failures, artifact-only execution, mixed-snapshot drift detection, zero-match component handling, and end-to-end hybrid query execution.
- Validation completed with `uv run --group dev pytest -q` (173 passed) plus `ruff check` and `ruff format --check` on the touched Python files.
- Resolved code review findings by preserving nested component failure details in hybrid error payloads and marking hybrid `total_match_count` as a lower bound whenever component truncation prevents an exact union size.
- Final validation completed with `uv run --group dev pytest -q` (176 passed) and `ruff format --check` on the touched Python files after the review fixes.

### File List

- docs/cli-reference.md
- src/codeman/application/query/__init__.py
- src/codeman/application/query/format_results.py
- src/codeman/application/query/hybrid_fusion.py
- src/codeman/application/query/run_hybrid_query.py
- src/codeman/bootstrap.py
- src/codeman/cli/query.py
- src/codeman/contracts/errors.py
- src/codeman/contracts/retrieval.py
- tests/e2e/test_query_hybrid.py
- tests/integration/query/test_run_hybrid_query_integration.py
- tests/unit/application/test_hybrid_fusion.py
- tests/unit/application/test_run_hybrid_query.py
- tests/unit/cli/test_query.py
- _bmad-output/implementation-artifacts/2-6-run-hybrid-retrieval-with-fused-ranking.md
- _bmad-output/implementation-artifacts/sprint-status.yaml

## Change Log

- 2026-03-14: Created comprehensive ready-for-dev story context for hybrid retrieval with fused ranking.
- 2026-03-14: Implemented hybrid retrieval fusion, CLI wiring, docs, and mirrored automated coverage; story moved to review.
- 2026-03-14: Fixed review findings for hybrid diagnostics/error details and marked story done after full validation.
