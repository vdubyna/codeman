# Story 4.3: Calculate and Store Retrieval Quality Metrics

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want codeman to calculate standard retrieval metrics for benchmark runs,
so that strategy quality can be compared using evidence instead of intuition.

## Acceptance Criteria

1. Given a completed benchmark run, when codeman calculates evaluation results, then it produces at least Recall@K, MRR, and NDCG@K for the run, and stores the metric outputs in a structured, attributable format.
2. Given the same benchmark run, when performance data is recorded, then codeman also captures indexing time where applicable and query latency metrics for comparison, and the metric record is tied to the same benchmark and configuration identity.

## Tasks / Subtasks

- [x] Add strict benchmark-metrics contracts and a pure calculation policy. (AC: 1, 2)
  - [x] Extend `src/codeman/contracts/evaluation.py` additively with DTOs for aggregate benchmark metrics, per-case metric results, performance summaries, and one normalized metrics artifact document.
  - [x] Add typed benchmark-metrics failures in the evaluation/application layer for cases such as missing benchmark artifact, incomplete benchmark run, corrupt benchmark artifact, or unsupported metric input shape.
  - [x] Add a focused pure-Python metrics policy module under `src/codeman/domain/evaluation/` for result-to-judgment matching plus Recall@K, MRR, and NDCG@K calculation. Do not add a heavyweight dependency such as `numpy` or `scikit-learn` just to compute three metrics.
  - [x] Persist the evaluated cutoff explicitly as `k` (or an equivalently clear field) so later comparisons can tell which ranking window produced the metric values.

- [x] Persist benchmark metric outputs in attributable metadata and artifact form. (AC: 1, 2)
  - [x] Extend the searchable benchmark metadata row additively with nullable metric summary fields and a metrics-generated timestamp, or an equivalently queryable summary surface, instead of hiding all comparison inputs only inside raw JSON.
  - [x] Extend `ArtifactStorePort` and `FilesystemArtifactStore` with a dedicated benchmark-metrics artifact seam under `.codeman/artifacts/benchmarks/<run-id>/metrics.json` or an equivalently deterministic path.
  - [x] Keep `run.json` as the raw benchmark execution evidence from Story 4.2. Metrics storage should be additive and should not replace or mutate the meaning of the raw benchmark artifact.
  - [x] Tie the persisted metric record to the same `run_id`, repository identity, snapshot identity, dataset identity/version/fingerprint, retrieval mode, and configuration/build context already established by Story 4.2.

- [x] Capture indexing-time inputs honestly before using them in benchmark metrics. (AC: 2)
  - [x] Extend lexical and semantic build contracts, persistence, and use cases to record explicit end-to-end build duration in milliseconds on the build records themselves.
  - [x] Use monotonic timing (`perf_counter_ns()` or equivalent) around the actual index-build workflows; do not infer indexing duration from `created_at` deltas, snapshot timestamps, or filesystem mtimes.
  - [x] Reuse those persisted build durations when benchmark metrics summarize indexing time for lexical and semantic runs.
  - [x] For hybrid benchmark runs, surface the component build durations separately and only include a combined value if it is clearly marked as a derived sum rather than a real standalone hybrid indexing duration.

- [x] Implement one benchmark-metrics use case and wire it into the successful benchmark lifecycle. (AC: 1, 2)
  - [x] Add a use case such as `src/codeman/application/evaluation/calculate_benchmark_metrics.py` that loads a completed benchmark run, reads the normalized raw benchmark artifact, computes the metric set deterministically, persists the metrics artifact/summary, and returns a compact result DTO.
  - [x] Wire the use case through `src/codeman/bootstrap.py` and invoke it automatically for newly successful benchmark runs so a successful `eval benchmark` execution records metrics without requiring a second manual command.
  - [x] Refuse to calculate metrics for `running`, `failed`, or partial benchmark artifacts. Failed or interrupted runs must stay truthful and must not receive misleading metric summaries.
  - [x] Reuse the stored benchmark artifact as the source of truth. Do not re-run retrieval, do not reread the mutable authored dataset path, and do not resolve new “latest” builds while computing metrics for an existing run.

- [x] Extend the public benchmark output contract additively, without jumping ahead to reports or comparisons. (AC: 1, 2)
  - [x] Extend `RunBenchmarkResult` and `src/codeman/cli/eval.py` with a compact metrics summary and any metrics artifact reference needed for operator inspection.
  - [x] Keep text output compact and JSON output envelope-based; add machine-readable metrics fields without changing the existing success/failure envelope shape.
  - [x] Update `docs/cli-reference.md` and `docs/benchmarks.md` honestly to document what metrics now exist, what `k` means, and where raw evidence versus computed metrics live.
  - [x] Do not add benchmark report generation, side-by-side run comparison, regression judgments, synthetic-query generation, or judge workflows in this story. Those remain Story 4.4-4.6 and beyond.

- [x] Add mirrored automated coverage for formulas, persistence, and CLI behavior. (AC: 1, 2)
  - [x] Add unit tests for the pure metrics policy, including binary and graded judgments, no-hit cases, duplicate result hits, optional line-span matching, and deterministic handling of `k`.
  - [x] Add unit tests for the benchmark-metrics use case, including successful calculation, refusal on incomplete/failed runs, and additive JSON artifact persistence.
  - [x] Add integration coverage for any new migration/table changes plus benchmark metrics artifact round-trips.
  - [x] Extend e2e benchmark coverage so lexical, semantic, and hybrid benchmark runs assert compact metric summaries and persisted metrics artifacts in both text and JSON modes.
  - [x] Add focused regression tests proving indexing duration is recorded explicitly on build records and benchmark metrics do not synthesize fake values when a duration is genuinely unavailable.

## Dev Notes

### Epic Context

- Story 4.3 is the first story that turns raw benchmark evidence into reviewable quality metrics. Story 4.2 intentionally stopped after truthful execution, raw artifacts, and benchmark lifecycle persistence.
- Story 4.4 depends on Story 4.3 producing stable stored metric outputs so report generation can stay a presentation layer instead of recalculating metrics ad hoc.
- Story 4.5 and Story 4.6 depend on Story 4.3 preserving comparable metric summaries, evaluated `k`, dataset identity, and build/config provenance so side-by-side comparison and regression detection stay attributable.

### Current Repo State

- `src/codeman/application/evaluation/` currently contains `load_benchmark_dataset.py` and `run_benchmark.py`; there is no dedicated benchmark-metrics calculation use case yet.
- `src/codeman/domain/` currently exists only as an empty package. If Story 4.3 introduces pure metric formulas, this is the right place for small side-effect-free evaluation policies rather than hiding ranking math inside CLI or persistence adapters.
- `src/codeman/contracts/evaluation.py` currently defines dataset contracts, benchmark run lifecycle DTOs, raw benchmark artifacts, and benchmark success results, but it does not yet define benchmark-metrics DTOs or a metrics artifact schema.
- `src/codeman/infrastructure/persistence/sqlite/tables.py` currently stores benchmark lifecycle information in `benchmark_runs`, but there are no metric summary fields yet.
- `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py` can read and write raw benchmark execution artifacts under `.codeman/artifacts/benchmarks/<run-id>/run.json`; there is no separate `metrics.json` artifact seam yet.
- `src/codeman/cli/eval.py` currently returns a compact benchmark summary with no retrieval-quality metrics.
- `docs/cli-reference.md` and `docs/benchmarks.md` explicitly say metrics calculation starts after Story 4.2.

### Previous Story Intelligence

- Story 4.2 already snapshots the normalized benchmark dataset used at execution time inside the raw benchmark artifact. Story 4.3 must calculate metrics from that stored artifact, not from the mutable dataset path on disk. [Source: _bmad-output/implementation-artifacts/4-2-execute-a-benchmark-run-against-an-indexed-repository.md]
- Story 4.2 already persists the per-case inputs Story 4.3 needs:
  - query identity and query text
  - authored relevance judgments
  - ranked retrieval results with stable locators
  - per-case query diagnostics including `query_latency_ms`
  - pinned lexical/semantic/hybrid build context
- Story 4.2 review fixes matter directly here:
  - benchmark runs are pinned to preflight-resolved build ids;
  - interrupted and failed runs are finalized truthfully;
  - JSON request validation failures still return the standard failure envelope.
  Story 4.3 must preserve those truths rather than “filling in” metrics for invalid or partial runs.
- Story 4.2 intentionally kept metric columns out of the benchmark row until Story 4.3. That is a strong signal that Story 4.3 should add a searchable metric summary surface now instead of leaving all comparison data buried in artifacts. [Source: _bmad-output/implementation-artifacts/4-2-execute-a-benchmark-run-against-an-indexed-repository.md]

### Cross-Story Baseline

- Story 4.1 established the benchmark truth model: repository-relative POSIX paths are canonical, line anchors are optional and 1-based, and `relevance_grade` values are open-ended positive integers specifically so later stories can support graded metrics such as NDCG. [Source: _bmad-output/implementation-artifacts/4-1-define-the-golden-query-benchmark-dataset.md; tests/unit/contracts/test_evaluation.py]
- Story 3.4 established the shared run-provenance pattern. Story 4.3 should attach metric results to the existing benchmark `run_id` and provenance lineage instead of inventing a second evaluation identity. [Source: _bmad-output/implementation-artifacts/3-4-record-configuration-provenance-for-every-run.md]
- Story 3.5 established explicit configuration/profile reuse lineage. Metric records must preserve the same configuration identity so later comparisons remain attributable. [Source: _bmad-output/implementation-artifacts/3-5-reuse-prior-configurations-in-later-experiments.md]
- Story 3.6 established deterministic cache/content identity discipline. Story 4.3 should keep ordering, fingerprinting, and artifact paths deterministic and should not use heuristic “best effort” metric recomputation against mutable live data. [Source: _bmad-output/implementation-artifacts/3-6-key-caches-to-configuration-and-content-identity.md]
- The current retrieval result contracts already expose the minimum matching data Story 4.3 needs: `relative_path`, `language`, `start_line`, `end_line`, rank, score, and per-case `query_latency_ms`. [Source: src/codeman/contracts/retrieval.py]

### Technical Guardrails

- Keep Story 4.3 CLI-first and local-first. Do not add HTTP routes, MCP execution, judge-provider flows, or background workers. [Source: docs/project-context.md; docs/architecture/decisions.md]
- Use the raw benchmark artifact from Story 4.2 as the metric input source of truth. Do not reread the authored dataset file, do not rescan the repository, and do not re-run lexical/semantic/hybrid retrieval to calculate metrics. [Source: docs/benchmarks.md; _bmad-output/implementation-artifacts/4-2-execute-a-benchmark-run-against-an-indexed-repository.md]
- Match benchmark results to judgments through stable locators, not content previews. A practical deterministic policy is:
  - exact `relative_path` match is required;
  - if the judgment specifies `language`, require the same language on the result item;
  - if the judgment specifies line anchors, treat a result as matching when the result span overlaps the authored line span.
  This overlap rule is an inference from the current benchmark truth model plus chunk-span result contracts and should be made explicit in code/tests. [Inference from src/codeman/contracts/evaluation.py and src/codeman/contracts/retrieval.py]
- One authored judgment should contribute at most once per query case. Multiple returned chunks that hit the same judged target must not inflate Recall, MRR, or NDCG.
- Use the benchmark run’s retained ranking window as the explicit evaluated cutoff `k`. Persist that value so later stories can detect when runs are not strictly comparable because they were evaluated at different cutoffs. [Inference from `RunBenchmarkRequest.max_results` and Story 4.2]
- Treat MRR over the persisted benchmark ranking window only. If no relevant result appears in the retained ranked list, the reciprocal-rank contribution should be `0.0`.
- Use graded relevance for NDCG from the authored `relevance_grade` values. Do not collapse NDCG into a binary hit metric. [Source: tests/unit/contracts/test_evaluation.py; _bmad-output/implementation-artifacts/4-1-define-the-golden-query-benchmark-dataset.md]
- Keep metric formulas pure and dependency-light. The repo does not currently depend on numerical libraries, and Story 4.3 does not need them for these metrics. [Source: pyproject.toml]
- Capture indexing time explicitly on build records with monotonic timing. Do not fake index duration by subtracting wall-clock timestamps such as `snapshot.chunk_generation_completed_at` from `build.created_at`; those timestamps measure attribution, not elapsed build work. [Inference from src/codeman/application/indexing/build_lexical_index.py; src/codeman/application/indexing/build_semantic_index.py]
- For hybrid metrics, preserve component durations separately. If a total is surfaced, mark it clearly as derived from lexical + semantic build durations rather than a real hybrid build duration.
- Keep DTOs additive and strict with `ConfigDict(extra="forbid")`. Preserve clean JSON `stdout` and keep progress/status lines on `stderr`. [Source: docs/project-context.md; docs/architecture/patterns.md]
- Do not generate benchmark reports, side-by-side comparisons, regression judgments, or judge-signal outputs in this story. Story 4.3 owns metric calculation and storage only. [Source: _bmad-output/planning-artifacts/epics.md - Stories 4.3-4.6; docs/benchmarks.md]

### Implementation Notes

- A clean Story 4.3 split is:
  - pure metric math and matching in `domain/evaluation/`;
  - orchestration plus persistence in `application/evaluation/`;
  - one compact searchable metric summary in SQLite;
  - one richer metrics artifact for per-case details under `.codeman/artifacts/benchmarks/<run-id>/metrics.json`.
- A practical metrics artifact should include:
  - run / repository / snapshot / build context
  - dataset id / version / fingerprint
  - evaluated `k`
  - aggregate retrieval-quality metrics (`recall_at_k`, `mrr`, `ndcg_at_k`)
  - aggregate performance metrics (query latency summary and indexing duration summary)
  - per-case metric details so Story 4.4 can render reports without reverse-engineering raw rankings again
  - `metrics_computed_at`
- A practical searchable summary on the benchmark row could include:
  - `evaluated_at_k`
  - `recall_at_k`
  - `mrr`
  - `ndcg_at_k`
  - latency summary fields such as mean and p95 (or an equally explicit comparable subset)
  - metrics artifact path or metrics-generated timestamp
  - indexing duration fields that are meaningful for the selected retrieval mode
- Prefer deterministic per-case ordering based on the dataset case order already frozen in the raw benchmark artifact.
- If older benchmark runs predate explicit build-duration capture, surface `null` for unavailable indexing-duration fields instead of synthesizing misleading numbers. AC 2 says “where applicable”; use that escape hatch honestly.
- Keep benchmark metrics calculation side-effect free with respect to retrieval/index state. The only writes should be metric persistence artifacts/rows for the already completed run.
- If the benchmark run already persisted one raw artifact and then metrics calculation fails, the run should remain truthful. Do not convert a succeeded execution run into a fake failed execution run just because the later metric-calculation step failed. Instead, use a benchmark-metrics-specific failure surface and leave raw execution evidence intact. [Inference from Story 4.2 truthfulness rules]

### File Structure Requirements

- Existing files to extend:
  - `src/codeman/application/evaluation/__init__.py`
  - `src/codeman/application/evaluation/run_benchmark.py`
  - `src/codeman/application/indexing/build_lexical_index.py`
  - `src/codeman/application/indexing/build_semantic_index.py`
  - `src/codeman/application/ports/artifact_store_port.py`
  - `src/codeman/application/ports/benchmark_run_store_port.py`
  - `src/codeman/bootstrap.py`
  - `src/codeman/cli/eval.py`
  - `src/codeman/contracts/evaluation.py`
  - `src/codeman/contracts/errors.py`
  - `src/codeman/contracts/retrieval.py`
  - `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/benchmark_run_repository.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/index_build_repository.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/semantic_index_build_repository.py`
  - `src/codeman/infrastructure/persistence/sqlite/tables.py`
  - `docs/benchmarks.md`
  - `docs/cli-reference.md`
- Likely new files for this story:
  - `src/codeman/application/evaluation/calculate_benchmark_metrics.py`
  - `src/codeman/domain/evaluation/__init__.py`
  - `src/codeman/domain/evaluation/metrics.py`
  - `migrations/versions/<timestamp>_add_benchmark_metrics_summary.py`
- Likely tests to add or extend:
  - `tests/unit/domain/test_benchmark_metrics.py`
  - `tests/unit/application/test_calculate_benchmark_metrics.py`
  - `tests/unit/application/test_run_benchmark.py`
  - `tests/unit/cli/test_eval.py`
  - `tests/unit/infrastructure/test_filesystem_artifact_store.py`
  - `tests/unit/application/test_build_lexical_index.py`
  - `tests/unit/application/test_build_semantic_index.py`
  - `tests/integration/persistence/test_benchmark_run_repository.py`
  - `tests/e2e/test_eval_benchmark.py`

### Testing Requirements

- Add unit tests for judgment/result matching policy:
  - exact-path-only match
  - path + overlapping line-span match
  - optional language mismatch rejection
  - duplicate result hits against the same judgment do not inflate gains
  - no-hit cases contribute `0.0` safely
- Add unit tests for aggregate metric formulas:
  - Recall@K across multiple judged targets
  - MRR where the first hit appears at rank 1, later ranks, or not at all
  - graded NDCG with mixed relevance grades and truncated `k`
  - deterministic handling when a case has fewer returned results than `k`
- Add unit tests for performance summaries:
  - query latency aggregation from raw per-case diagnostics
  - explicit `null` indexing durations when unavailable
  - hybrid component duration handling
- Add use-case tests proving:
  - successful benchmark runs automatically persist metrics
  - failed/interrupted benchmark runs do not get metric summaries
  - corrupt or missing raw benchmark artifacts fail with typed benchmark-metrics errors
- Add integration tests covering new migration/schema changes plus read/write round trips for any metrics artifact.
- Extend e2e benchmark coverage so text and JSON output assert compact metric summaries for lexical, semantic, and hybrid benchmark runs without requiring a separate manual metrics command.

### Git Intelligence Summary

- Commit `8b4c797` (`story(4-2): fix final benchmark review findings`) reinforced a repo value that matters directly for Story 4.3: keep benchmark workflows truthful, preserve clean JSON failure envelopes, and fix edge cases with focused additive changes rather than rewrites.
- Commit `f682e66` (`story(4-2): close benchmark execution after review fixes`) established the benchmark implementation pattern to reuse now:
  - one focused use case in `application/evaluation/`
  - additive DTO changes
  - a dedicated artifact seam
  - SQLite-backed searchable metadata
  - mirrored unit/integration/e2e coverage
- Commit `147399b` (`story(4-1-define-the-golden-query-benchmark-dataset): complete code review and mark done`) is the metric-foundation baseline. It established strict dataset validation, normalized repository-relative locators, and open-ended relevance grades that Story 4.3 should convert into metrics rather than redesign.
- Commit `c447863` (`story(3-6-key-caches-to-configuration-and-content-identity): complete code review and mark done`) reinforces deterministic identity, local artifact storage, and stable fingerprinting. Metric artifacts and summary rows should follow the same discipline.
- Commit `4d51962` (`story(3-5-reuse-prior-configurations-in-later-experiments): complete code review and mark done`) matters because benchmark metrics must remain attributable to the same configuration/profile lineage used by the indexed builds and benchmark run.

### Latest Technical Information

- As of March 15, 2026, the official Pydantic docs continue to document `ConfigDict` as the supported model-configuration surface and recommend `model_validate_json()` for JSON-bound validation. Inference: new benchmark-metrics artifacts and DTOs should stay strict and continue using the repo’s current Pydantic JSON boundary style rather than manual `json.loads(...)` plus loose dict validation. [Source: https://docs.pydantic.dev/latest/concepts/config/; https://docs.pydantic.dev/latest/concepts/json/]
- As of March 15, 2026, the official Python docs continue to recommend `perf_counter_ns()` to avoid float precision loss when measuring short durations. Inference: explicit lexical/semantic build-duration capture should use monotonic integer timing and then convert to millisecond contract fields deliberately. [Source: https://docs.python.org/3/library/time.html#time.perf_counter_ns]
- As of March 15, 2026, the official scikit-learn docs still describe NDCG as discounted gain normalized by the ideal ranking and truncated by optional `k`. Inference: Story 4.3 should treat authored `relevance_grade` as graded gain and persist the evaluated cutoff explicitly instead of silently computing an unbounded NDCG. [Source: https://scikit-learn.org/stable/modules/generated/sklearn.metrics.ndcg_score.html]
- TREC’s QA evaluation notes still describe MRR as the reciprocal rank of the first correct response, averaged across questions, with `0` when no correct response is returned. Inference: Story 4.3 should compute per-case reciprocal rank from the first matching relevant result in the persisted ranking window and average those values across benchmark cases. [Source: https://trec.nist.gov/data/qa.html]

### Project Context Reference

- `docs/project-context.md` remains the canonical agent-facing implementation ruleset: use strict Pydantic boundary models, thin CLI handlers, deterministic ordering, runtime-managed artifacts under `.codeman/`, and mirrored automated coverage for touched behavior.
- `docs/architecture/decisions.md` and `docs/architecture/patterns.md` keep the extension path narrow: `cli -> application -> ports -> infrastructure -> contracts/config/runtime`.
- `docs/benchmarks.md` owns the human-facing benchmark/evaluation policy. Update it honestly for implemented metrics instead of spreading benchmark semantics into multiple docs.
- No separate UX artifact exists. The relevant UX requirement here is operator clarity: a benchmark run should stay compact, truthful, and scriptable while still surfacing enough metric summary to support the next comparison/reporting stories.

### Project Structure Notes

- The planning architecture expects evaluation workflows in `application/evaluation/` plus pure metric logic in `domain/evaluation/`. The current code has not used `domain/` yet, so Story 4.3 should introduce only the smallest useful pure evaluation module instead of dumping formulas back into `run_benchmark.py`.
- The current split metadata/artifact architecture is a good fit for metrics too:
  - SQLite for searchable summary values that later comparison/reporting stories need quickly
  - generated JSON artifact for richer per-case metric detail
- The existing `eval benchmark` command is already the canonical benchmark surface. Story 4.3 should extend it additively rather than creating a parallel benchmark command family.
- The raw benchmark artifact currently carries everything needed for deterministic metric calculation. That makes Story 4.3 a good place to add a metrics layer without changing the benchmark truth model itself.

### References

- [Source: docs/project-context.md]
- [Source: docs/README.md]
- [Source: docs/architecture/decisions.md]
- [Source: docs/architecture/patterns.md]
- [Source: docs/benchmarks.md]
- [Source: docs/cli-reference.md]
- [Source: pyproject.toml]
- [Source: _bmad-output/planning-artifacts/epics.md - Epic 4; Story 4.1; Story 4.2; Story 4.3; Story 4.4; Story 4.5; Story 4.6]
- [Source: _bmad-output/planning-artifacts/prd.md - Executive Summary; Measurable Outcomes; FR20; FR23; NFR3; NFR12-NFR19]
- [Source: _bmad-output/planning-artifacts/architecture.md - Evaluation and Benchmarking capability group; Data Architecture; Service Boundaries; Data Flow]
- [Source: _bmad-output/implementation-artifacts/4-1-define-the-golden-query-benchmark-dataset.md]
- [Source: _bmad-output/implementation-artifacts/4-2-execute-a-benchmark-run-against-an-indexed-repository.md]
- [Source: _bmad-output/implementation-artifacts/3-4-record-configuration-provenance-for-every-run.md]
- [Source: _bmad-output/implementation-artifacts/3-5-reuse-prior-configurations-in-later-experiments.md]
- [Source: _bmad-output/implementation-artifacts/3-6-key-caches-to-configuration-and-content-identity.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: src/codeman/application/evaluation/__init__.py]
- [Source: src/codeman/application/evaluation/run_benchmark.py]
- [Source: src/codeman/application/indexing/build_lexical_index.py]
- [Source: src/codeman/application/indexing/build_semantic_index.py]
- [Source: src/codeman/application/ports/artifact_store_port.py]
- [Source: src/codeman/application/ports/benchmark_run_store_port.py]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/cli/eval.py]
- [Source: src/codeman/contracts/evaluation.py]
- [Source: src/codeman/contracts/retrieval.py]
- [Source: src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/benchmark_run_repository.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/tables.py]
- [Source: tests/unit/contracts/test_evaluation.py]
- [Source: tests/unit/application/test_run_benchmark.py]
- [Source: tests/unit/application/test_load_benchmark_dataset.py]
- [Source: tests/unit/application/test_build_lexical_index.py]
- [Source: tests/unit/application/test_build_semantic_index.py]
- [Source: tests/integration/persistence/test_benchmark_run_repository.py]
- [Source: tests/e2e/test_eval_benchmark.py]
- [Source: tests/fixtures/queries/mixed_stack_fixture_golden_queries.json]
- [Source: git log --oneline -5]
- [Source: https://docs.pydantic.dev/latest/concepts/config/]
- [Source: https://docs.pydantic.dev/latest/concepts/json/]
- [Source: https://docs.python.org/3/library/time.html#time.perf_counter_ns]
- [Source: https://scikit-learn.org/stable/modules/generated/sklearn.metrics.ndcg_score.html]
- [Source: https://trec.nist.gov/data/qa.html]

## Story Completion Status

- Status set to `ready-for-dev`.
- Completion note: `Ultimate context engine analysis completed - comprehensive developer guide created.`
- Recorded assumptions:
  - Story 4.3 should extend the existing `eval benchmark` lifecycle so successful benchmark runs receive stored metrics automatically rather than relying on a second manual command.
  - A dedicated metrics artifact plus a searchable metric summary is the best fit for the current split metadata/artifact architecture.
  - Explicit index-build duration capture is required in this story because the current build records do not yet store a truthful indexing-duration field.
  - Result-to-judgment matching should be made explicit and deterministic in Story 4.3, with path equality and optional line-span overlap as the default rule.

## Dev Agent Record

### Agent Model Used

Codex (GPT-5)

### Debug Log References

- 2026-03-15: Story context generated via the `bmad-create-story` workflow for backlog story `4-3-calculate-and-store-retrieval-quality-metrics`.
- 2026-03-15: Loaded Epic 4, PRD, architecture, benchmark policy/docs, completed Story 4.2, current evaluation/indexing contracts, benchmark CLI/tests, and recent git history to derive the metric-calculation guardrails for this story.
- 2026-03-15: Implemented benchmark metrics contracts, pure evaluation policy, additive metrics artifact persistence, build-duration capture, automatic metrics execution for successful benchmark runs, CLI contract updates, and migration support.
- 2026-03-15: Validated with `UV_CACHE_DIR=.local/uv-cache uv run --group dev pytest -q tests/unit/domain/test_benchmark_metrics.py tests/unit/application/test_calculate_benchmark_metrics.py tests/unit/cli/test_eval.py tests/unit/infrastructure/test_filesystem_artifact_store.py tests/integration/persistence/test_benchmark_run_repository.py tests/unit/application/test_run_benchmark.py tests/unit/application/test_build_lexical_index.py tests/unit/application/test_build_semantic_index.py`, `UV_CACHE_DIR=.local/uv-cache uv run --group dev pytest -q tests/e2e/test_eval_benchmark.py`, and `UV_CACHE_DIR=.local/uv-cache uv run --group dev ruff check src/codeman/application/evaluation src/codeman/domain/evaluation src/codeman/contracts src/codeman/infrastructure/artifacts src/codeman/infrastructure/persistence/sqlite tests/unit/domain/test_benchmark_metrics.py tests/unit/application/test_calculate_benchmark_metrics.py tests/unit/cli/test_eval.py tests/unit/infrastructure/test_filesystem_artifact_store.py tests/integration/persistence/test_benchmark_run_repository.py tests/unit/application/test_run_benchmark.py tests/unit/application/test_build_lexical_index.py tests/unit/application/test_build_semantic_index.py tests/e2e/test_eval_benchmark.py`.
- 2026-03-15: Addressed post-review findings by wrapping unexpected metrics persistence failures into the benchmark-metrics error surface, strengthening raw benchmark artifact identity/build-context validation, and widening lexical/semantic duration capture to cover chunk-payload loading before the build stages.
- 2026-03-15: Revalidated after review fixes with `UV_CACHE_DIR=.local/uv-cache uv run --group dev pytest -q tests/unit/application/test_calculate_benchmark_metrics.py tests/unit/application/test_build_lexical_index.py tests/unit/application/test_build_semantic_index.py tests/unit/cli/test_eval.py tests/e2e/test_eval_benchmark.py`, `UV_CACHE_DIR=.local/uv-cache uv run --group dev ruff check src tests`, and `UV_CACHE_DIR=.local/uv-cache uv run --group dev pytest -q`.

### Completion Notes List

- Added strict benchmark-metrics DTOs, additive benchmark-run summary fields, benchmark-metrics-specific errors, and a dedicated `metrics.json` artifact seam.
- Implemented a pure domain metrics policy for deterministic path/language/line-overlap matching plus `Recall@K`, `MRR`, `NDCG@K`, and query-latency summaries.
- Recorded explicit lexical and semantic build durations with monotonic timing and reused them in benchmark metrics, including separate hybrid component durations and a clearly derived combined duration.
- Added `CalculateBenchmarkMetricsUseCase`, wired it through bootstrap, and invoked it automatically after successful `eval benchmark` runs without mutating the meaning of raw `run.json` evidence.
- Extended benchmark CLI text/JSON output and canonical docs to surface `k`, aggregate metrics, performance summaries, and the additive metrics artifact location.
- Added mirrored unit, integration, and e2e coverage for formulas, persistence, CLI output, automatic metrics execution, and duration-capture regression cases.
- Closed the three review findings by making metrics-phase failures return the stable benchmark-metrics CLI envelope, validating dataset/build attribution more defensively against persisted run/build identity, and proving end-to-end build timing includes chunk payload loading.
- Revalidated the full repository regression suite successfully before closing the story.

### File List

- _bmad-output/implementation-artifacts/4-3-calculate-and-store-retrieval-quality-metrics.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- docs/benchmarks.md
- docs/cli-reference.md
- migrations/versions/202603151630_add_benchmark_metrics_summary_fields.py
- src/codeman/application/evaluation/__init__.py
- src/codeman/application/evaluation/calculate_benchmark_metrics.py
- src/codeman/application/evaluation/run_benchmark.py
- src/codeman/application/indexing/build_lexical_index.py
- src/codeman/application/indexing/build_semantic_index.py
- src/codeman/application/ports/artifact_store_port.py
- src/codeman/bootstrap.py
- src/codeman/cli/eval.py
- src/codeman/contracts/errors.py
- src/codeman/contracts/evaluation.py
- src/codeman/contracts/retrieval.py
- src/codeman/domain/evaluation/__init__.py
- src/codeman/domain/evaluation/metrics.py
- src/codeman/infrastructure/artifacts/filesystem_artifact_store.py
- src/codeman/infrastructure/persistence/sqlite/repositories/benchmark_run_repository.py
- src/codeman/infrastructure/persistence/sqlite/repositories/index_build_repository.py
- src/codeman/infrastructure/persistence/sqlite/repositories/semantic_index_build_repository.py
- src/codeman/infrastructure/persistence/sqlite/tables.py
- tests/e2e/test_eval_benchmark.py
- tests/integration/persistence/test_benchmark_run_repository.py
- tests/unit/application/test_build_lexical_index.py
- tests/unit/application/test_build_semantic_index.py
- tests/unit/application/test_calculate_benchmark_metrics.py
- tests/unit/application/test_run_benchmark.py
- tests/unit/cli/test_eval.py
- tests/unit/domain/test_benchmark_metrics.py
- tests/unit/infrastructure/test_filesystem_artifact_store.py

### Change Log

- 2026-03-15: Implemented Story 4.3 benchmark metrics end-to-end, including additive contracts and persistence, explicit build-duration capture, automatic benchmark metrics calculation, CLI/doc updates, migration support, and mirrored automated coverage.
- 2026-03-15: Addressed code review findings, reran the full lint/test suite (`342 passed`), and closed Story 4.3 as done.
