# Story 4.5: Compare Benchmark Runs Across Retrieval Strategies

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want to compare benchmark runs side by side,
so that I can understand how one retrieval strategy performs relative to another.

## Acceptance Criteria

1. Given two or more completed benchmark runs, when I run a comparison workflow, then codeman produces a structured comparison of key metrics and configuration identities, and makes it clear which run performed better for each reported measure.
2. Given compared runs were produced under different repository states or benchmark datasets, when I inspect the comparison output, then codeman highlights those comparability differences explicitly, and does not imply a clean apples-to-apples comparison when the context differs.

## Tasks / Subtasks

- [x] Add additive benchmark-comparison DTOs, provenance context, and typed failures. (AC: 1, 2)
  - [x] Extend `src/codeman/contracts/evaluation.py` with request/result DTOs for multi-run benchmark comparison. Reuse existing `BenchmarkRunRecord`, `BenchmarkDatasetSummary`, `BenchmarkMetricsSummary`, retrieval build contexts, and `RunConfigurationProvenanceRecord` instead of duplicating those shapes.
  - [x] Add one explicit comparability surface, such as `comparability` plus `differences`/`notes`, so JSON and text output can state why a comparison is or is not apples-to-apples.
  - [x] Add stable error codes in `src/codeman/contracts/errors.py` and matching typed exceptions in `src/codeman/application/evaluation/compare_runs.py` for unknown run ids, missing `run.json`, missing `metrics.json`, incomplete benchmark runs, corrupt or mismatched persisted evidence, unavailable provenance, and cross-repository comparisons.
  - [x] Extend `src/codeman/contracts/configuration.py` additively for benchmark-comparison provenance if the workflow records a comparison run id. At minimum, support a new workflow type such as `compare.benchmark_runs` and preserve deterministic compared-run ordering in workflow context.

- [x] Implement one benchmark comparison use case over persisted evidence only. (AC: 1, 2)
  - [x] Add `src/codeman/application/evaluation/compare_runs.py` and wire it to load each requested benchmark run row, `run.json`, `metrics.json`, and stored provenance by run id.
  - [x] Validate every compared package internally before comparing it: run row, raw artifact, metrics artifact, and provenance must agree on run id, repository id, snapshot id, dataset identity, retrieval mode, and build context.
  - [x] Reuse the read-and-validate discipline established in `src/codeman/application/evaluation/generate_report.py`; do not rerun retrieval, reload the authored dataset from disk, recalculate metrics, parse `report.md`, or compare loose SQLite summary values when persisted artifacts disagree.
  - [x] Preserve the user-provided run order in the returned comparison package. Use `get_by_run_id(...)` for each requested id rather than deriving order from repository listings.
  - [x] Treat repository mismatch as a hard failure. Treat snapshot, dataset, evaluated cutoff `k`, case-count, provider/model, and configuration differences as explicit comparability notes rather than silent assumptions.
  - [x] Compare the stored metrics truthfully:
    - higher is better for `Recall@K`, `MRR`, and `NDCG@K`
    - lower is better for latency and indexing-duration metrics when values are present
    - `null` values are unavailable data, not hidden wins or losses
    - ties remain ties; do not invent a composite score or weighted overall winner

- [x] Expose benchmark comparison through the existing `compare` CLI surface. (AC: 1, 2)
  - [x] Add a thin command such as `compare benchmark-runs` in `src/codeman/cli/compare.py` instead of inventing a new root command tree or overloading `eval`.
  - [x] Accept at least two run ids, preferably through repeated `--run-id` options so multi-run comparisons stay explicit and deterministic.
  - [x] Keep text output compact and operator-focused: compared run ids, retrieval modes, key metrics, per-metric winners or ties, and explicit comparability notes.
  - [x] In JSON mode, return exactly one standard success envelope on `stdout` with no interleaved commentary; progress and status lines belong on `stderr` only.
  - [x] Wire the use case through `src/codeman/bootstrap.py` and reuse shared CLI helpers instead of creating a special-case output path.

- [x] Update canonical docs and keep benchmark policy honest. (AC: 1, 2)
  - [x] Update `docs/cli-reference.md` with the supported comparison command syntax, minimum run count, text/JSON output fields, and stable failure semantics.
  - [x] Update `docs/benchmarks.md` so benchmark-run comparison moves from future work to implemented behavior once the code exists, while keeping regression detection as future work until Story 4.6 is implemented.
  - [x] If benchmark-comparison provenance becomes user-visible, document only the user-facing behavior in the canonical owner document instead of scattering the same rules elsewhere.

- [x] Add mirrored automated coverage for the new comparison workflow. (AC: 1, 2)
  - [x] Add unit coverage for DTO validation, metric-direction winner logic, deterministic tie handling, and comparability-note generation.
  - [x] Add unit coverage for failure mapping when any compared run is unknown, incomplete, cross-repository, missing persisted evidence, or has corrupt/mismatched evidence.
  - [x] Extend CLI unit coverage in `tests/unit/cli/test_compare.py` for text mode, JSON mode, repeated `--run-id` parsing, clean `stdout`/`stderr` separation, and stable failure envelopes.
  - [x] Add integration coverage for persisted-evidence comparison under `tests/integration/`, including scenarios where runs differ by snapshot or dataset and must compare truthfully with warnings instead of pretending equivalence.
  - [x] Add end-to-end coverage that creates at least two benchmark runs from the mixed-stack fixtures, compares them in text and JSON modes, and proves the output marks contextual mismatches explicitly when the run contexts differ.

## Dev Notes

### Epic Context

- Story 4.5 is the first run-to-run comparison layer for benchmark evidence. Story 4.6 should be able to build on this truth surface for regression detection instead of inventing a parallel comparison path.
- Epic 4 is intentionally cumulative:
  - Story 4.2 established truthful benchmark execution and persisted `run.json`.
  - Story 4.3 established deterministic metrics and persisted `metrics.json`.
  - Story 4.4 established read-only reporting over persisted evidence.
  - Story 4.5 should compare those same persisted artifacts, not introduce a second source of truth.
- The product goal is evidence-driven strategy comparison, not anecdotal winner-picking. Comparison output must stay attributable to the benchmark context that produced each run. [Source: _bmad-output/planning-artifacts/epics.md - Epic 4; Story 4.5; Story 4.6] [Source: _bmad-output/planning-artifacts/prd.md - Technical Success; Measurable Outcomes; Evaluation & Benchmarking]

### Current Repo State

- The benchmark stack already exists under `src/codeman/application/evaluation/` with `run_benchmark.py`, `calculate_benchmark_metrics.py`, and `generate_report.py`. There is no benchmark-run comparison use case yet. [Source: src/codeman/application/evaluation/run_benchmark.py] [Source: src/codeman/application/evaluation/calculate_benchmark_metrics.py] [Source: src/codeman/application/evaluation/generate_report.py]
- `src/codeman/cli/eval.py` already exposes `eval benchmark` and `eval report`. `src/codeman/cli/compare.py` currently exposes only `compare query-modes`. The benchmark-run comparison workflow should extend the existing `compare` group, not create a second comparison surface somewhere else. [Source: src/codeman/cli/eval.py] [Source: src/codeman/cli/compare.py] [Source: docs/cli-reference.md#Compare Commands]
- `ArtifactStorePort` and `FilesystemArtifactStore` already provide structured access to benchmark `run.json`, `metrics.json`, and `report.md`. Story 4.5 should compare the structured JSON artifacts and provenance, not parse the human Markdown report. [Source: src/codeman/application/ports/artifact_store_port.py] [Source: src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- `SqliteBenchmarkRunStore` already supports `get_by_run_id(...)` and `list_by_repository_id(...)`. `get_by_run_id(...)` is the right primitive for comparison because it preserves requested run ids and avoids hidden reorderings. [Source: src/codeman/application/ports/benchmark_run_store_port.py] [Source: src/codeman/infrastructure/persistence/sqlite/repositories/benchmark_run_repository.py]
- Run provenance already exists and is queryable through `ShowRunConfigurationProvenanceUseCase`. Story 4.5 should surface configuration identity from that existing provenance seam rather than reading provenance tables directly in the CLI. [Source: src/codeman/application/provenance/show_run_provenance.py] [Source: src/codeman/contracts/configuration.py]
- `docs/benchmarks.md` still says run comparison remains future work. That statement should stay true until the new command and tests are actually implemented. [Source: docs/benchmarks.md#Current Status]

### Required Implementation Guardrails

- Do not compare benchmark runs by parsing `report.md` or CLI text output. Those are human review surfaces, not machine truth. Compare `BenchmarkRunRecord`, `BenchmarkRunArtifactDocument`, `BenchmarkMetricsArtifactDocument`, and stored provenance directly. [Source: src/codeman/contracts/evaluation.py] [Source: src/codeman/application/evaluation/generate_report.py]
- Do not silently drop requested runs that are incomplete or corrupt. If a requested run cannot participate truthfully, fail with a stable typed error and tell the operator which run id is the problem. [Source: docs/project-context.md - Critical Don't-Miss Rules] [Source: src/codeman/contracts/errors.py]
- Do not invent an overall score that weights metrics without product approval. The acceptance criteria only require clarity about which run performed better for each reported measure. A per-metric winner surface is in scope; a synthetic aggregate ranking is not. [Source: _bmad-output/planning-artifacts/epics.md - Story 4.5]
- Do not treat contextual mismatches as equivalent comparisons. Snapshot identity, dataset identity, evaluated `k`, and case count all affect comparability and must be surfaced explicitly. [Source: _bmad-output/planning-artifacts/architecture.md - Project Context Analysis; Data Architecture] [Source: docs/benchmarks.md#Benchmark Baseline Policy]
- Do not add a new CLI presentation dependency just for tables. Stay within the current Typer/plain-text output pattern unless the codebase already establishes a different rendering dependency before implementation starts. [Source: src/codeman/cli/eval.py] [Source: src/codeman/cli/compare.py]
- Keep repository contents local-first and secret-safe. Comparison output may expose provider/model/config provenance, but it must not leak secret-bearing configuration values or full repository contents. [Source: docs/project-context.md - Critical Don't-Miss Rules] [Source: docs/benchmarks.md#Privacy and Provider Boundaries]

### Previous Story Intelligence

- Story 4.4 already solved the hardest truthfulness problem for read-only benchmark workflows: load the benchmark row, raw artifact, metrics artifact, and provenance; cross-validate them; then render output from persisted evidence only. Story 4.5 should reuse that pattern directly or extract a small shared helper if duplication becomes meaningful. [Source: _bmad-output/implementation-artifacts/4-4-generate-benchmark-reports-for-review.md]
- The review fixes in Story 4.4 matter here too:
  - report generation wraps report-write failures in typed benchmark-report errors;
  - metrics summary fields are cross-checked against `metrics.json`;
  - SQLite datetimes are normalized to UTC-aware values.
  Benchmark comparison should preserve these guarantees rather than weakening them for convenience. [Source: _bmad-output/implementation-artifacts/4-4-generate-benchmark-reports-for-review.md] [Source: src/codeman/infrastructure/persistence/sqlite/repositories/benchmark_run_repository.py]
- Story 4.3 already defines the comparable metrics surface: `Recall@K`, `MRR`, `NDCG@K`, query latency summaries, and truthful indexing-duration summaries. Reuse those stored values instead of recalculating them from raw case results during comparison. [Source: _bmad-output/implementation-artifacts/4-3-calculate-and-store-retrieval-quality-metrics.md] [Source: src/codeman/contracts/evaluation.py]
- Story 4.2 already ensures benchmark runs have repository/snapshot/build/dataset provenance and persisted raw execution evidence. Story 4.5 should compare benchmarked truth, not rerun retrieval. [Source: _bmad-output/implementation-artifacts/4-2-execute-a-benchmark-run-against-an-indexed-repository.md]
- `compare query-modes` is a strong current implementation pattern for this story:
  - one focused use case
  - thin CLI command in `src/codeman/cli/compare.py`
  - stable error codes
  - one success envelope on JSON `stdout`
  - explicit snapshot mismatch handling
  Benchmark-run comparison should reuse those structural patterns without copying retrieval-specific logic. [Source: src/codeman/application/query/compare_retrieval_modes.py] [Source: src/codeman/cli/compare.py]

### Cross-Story Baseline

- Story 4.1 established dataset truth and dataset fingerprinting. Comparison output should surface dataset id/version/fingerprint and treat mismatches as context differences, not cosmetic metadata. [Source: _bmad-output/implementation-artifacts/4-1-define-the-golden-query-benchmark-dataset.md]
- Story 3.4 established shared run-provenance recording. If Story 4.5 records a benchmark-comparison provenance row, it should use the same run-provenance infrastructure and additive workflow-context fields instead of inventing a benchmark-only provenance store. [Source: _bmad-output/implementation-artifacts/3-4-record-configuration-provenance-for-every-run.md] [Source: src/codeman/contracts/configuration.py]
- Story 3.5 established configuration reuse lineage. Benchmark comparison should surface effective configuration identity and reuse lineage so operators can see whether runs came from ad hoc settings, reused profiles, or modified profile reuse. [Source: _bmad-output/implementation-artifacts/3-5-reuse-prior-configurations-in-later-experiments.md]
- Story 3.6 established deterministic content/config identity and runtime artifact discipline. Comparison logic should remain deterministic, runtime-local, and explicit about what was compared. [Source: _bmad-output/implementation-artifacts/3-6-key-caches-to-configuration-and-content-identity.md]

### Architecture Compliance

- Keep the extension path narrow: `cli` -> `application` -> `ports` -> `infrastructure` -> `contracts/config/runtime`. The CLI should not read SQLite tables or artifact files directly. [Source: docs/architecture/patterns.md#Layering Pattern] [Source: docs/architecture/patterns.md#Current Extension Patterns]
- The codebase is CLI-first and local-first. There is no HTTP or MCP comparison surface to wire here. [Source: docs/architecture/decisions.md#Current Decisions]
- Machine-readable output must remain the standard success/failure envelope on `stdout`, with progress lines on `stderr`. [Source: docs/project-context.md - Framework-Specific Rules] [Source: docs/architecture/decisions.md#Current Decisions]
- Generated state belongs under `.codeman/`. Story 4.5 does not require a new artifact by default; if you later discover a concrete need for a comparison artifact, add it only deliberately and document it honestly. [Source: docs/project-context.md - Critical Don't-Miss Rules] [Source: docs/architecture/patterns.md#Add Runtime-Managed Artifacts]

### File Structure Requirements

- Primary code changes should stay near the existing benchmark/report surfaces:
  - `src/codeman/contracts/evaluation.py`
  - `src/codeman/contracts/errors.py`
  - `src/codeman/contracts/configuration.py` if comparison provenance is recorded
  - `src/codeman/application/evaluation/compare_runs.py`
  - `src/codeman/cli/compare.py`
  - `src/codeman/bootstrap.py`
- Expected tests:
  - `tests/unit/application/test_compare_benchmark_runs.py`
  - `tests/unit/cli/test_compare.py`
  - one integration test module under `tests/integration/` for persisted benchmark comparison
  - one e2e module under `tests/e2e/` or an extension of `tests/e2e/test_eval_benchmark.py`
- Docs to update when behavior exists:
  - `docs/cli-reference.md`
  - `docs/benchmarks.md`

### Testing Requirements

- Assert stable user-facing behavior, not just internal values:
  - exit codes
  - error codes
  - success-envelope shape
  - deterministic compared-run ordering
  - explicit comparability warnings
  - clean `stdout`/`stderr` separation
- Cover at least these comparison scenarios:
  - lexical vs semantic benchmark runs on the same dataset and snapshot
  - runs with different dataset version or fingerprint
  - runs with different snapshot ids on the same repository
  - runs with missing metrics artifacts
  - runs that belong to different repositories and must fail
  - ties on one or more metrics
- Keep the e2e workflow local-first. Reuse the existing mixed-stack fixture and benchmark dataset instead of introducing heavy synthetic fixtures without need. [Source: tests/e2e/test_eval_benchmark.py]

### Latest Technical Information

- As of March 15, 2026, Typer's official docs still center nested command composition through `app.add_typer(...)`. Inference: benchmark-run comparison should live under the existing `compare` Typer group instead of creating a second root command tree. [Source: https://typer.tiangolo.com/tutorial/subcommands/add-typer/]
- As of March 15, 2026, Typer's official docs still support repeated option values through list-typed options. Inference: repeated `--run-id` options are a good fit for an explicit multi-run comparison command. [Source: https://typer.tiangolo.com/tutorial/multiple-values/multiple-options/]
- As of March 15, 2026, the official Pydantic docs continue to document `ConfigDict` for strict model configuration and `model_validate_json()` for JSON-bound validation. Inference: new comparison DTOs and persisted-artifact loading should follow the same strict boundary pattern as the current benchmark/report contracts. [Source: https://docs.pydantic.dev/latest/api/config/] [Source: https://docs.pydantic.dev/latest/concepts/json/]

### Project Context Reference

- `docs/project-context.md` remains the canonical agent-facing implementation ruleset: thin CLI commands, typed exceptions with stable error codes, deterministic ordering, workspace-local runtime artifacts, and mirrored automated coverage.
- `docs/README.md` remains the canonical documentation ownership map.
- `docs/architecture/decisions.md` and `docs/architecture/patterns.md` define the stable extension path the implementation should preserve.
- No separate UX artifact exists for this story. The relevant UX requirement is operator clarity: side-by-side comparison must be understandable in text mode without sacrificing truthful JSON mode.

### Project Structure Notes

- The current split metadata/artifact architecture already supports this story:
  - SQLite stores benchmark lifecycle rows and summary fields.
  - `.codeman/artifacts/benchmarks/<run-id>/run.json` stores raw benchmark evidence.
  - `.codeman/artifacts/benchmarks/<run-id>/metrics.json` stores additive metric outputs.
  - stored run provenance provides configuration identity and reuse lineage.
- Story 4.5 should compare those persisted surfaces directly and remain additive. It should not mutate old benchmark runs and should not require rebuilding indexes or rerunning queries to answer a comparison request.
- If you record one benchmark-comparison provenance row, keep it lightweight and attributable. Do not create a second persistence subsystem for comparison history.

### References

- [Source: docs/project-context.md]
- [Source: docs/README.md]
- [Source: docs/architecture/decisions.md]
- [Source: docs/architecture/patterns.md]
- [Source: docs/benchmarks.md]
- [Source: docs/cli-reference.md]
- [Source: src/codeman/cli/eval.py]
- [Source: src/codeman/cli/compare.py]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/application/evaluation/run_benchmark.py]
- [Source: src/codeman/application/evaluation/calculate_benchmark_metrics.py]
- [Source: src/codeman/application/evaluation/generate_report.py]
- [Source: src/codeman/application/provenance/show_run_provenance.py]
- [Source: src/codeman/application/query/compare_retrieval_modes.py]
- [Source: src/codeman/application/ports/artifact_store_port.py]
- [Source: src/codeman/application/ports/benchmark_run_store_port.py]
- [Source: src/codeman/contracts/configuration.py]
- [Source: src/codeman/contracts/evaluation.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/benchmark_run_repository.py]
- [Source: tests/unit/cli/test_compare.py]
- [Source: tests/unit/cli/test_eval.py]
- [Source: tests/integration/persistence/test_benchmark_run_repository.py]
- [Source: tests/e2e/test_eval_benchmark.py]
- [Source: _bmad-output/planning-artifacts/epics.md - Epic 4; Story 4.5; Story 4.6]
- [Source: _bmad-output/planning-artifacts/prd.md - Measurable Outcomes; Evaluation & Benchmarking; Reliability & Reproducibility]
- [Source: _bmad-output/planning-artifacts/architecture.md - Project Context Analysis; Data Architecture; Naming Patterns; Requirements to Structure Mapping]
- [Source: _bmad-output/implementation-artifacts/4-1-define-the-golden-query-benchmark-dataset.md]
- [Source: _bmad-output/implementation-artifacts/4-2-execute-a-benchmark-run-against-an-indexed-repository.md]
- [Source: _bmad-output/implementation-artifacts/4-3-calculate-and-store-retrieval-quality-metrics.md]
- [Source: _bmad-output/implementation-artifacts/4-4-generate-benchmark-reports-for-review.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: https://typer.tiangolo.com/tutorial/subcommands/add-typer/]
- [Source: https://typer.tiangolo.com/tutorial/multiple-values/multiple-options/]
- [Source: https://docs.pydantic.dev/latest/api/config/]
- [Source: https://docs.pydantic.dev/latest/concepts/json/]

## Story Completion Status

- Status set to `done`.
- Completion note: `Implemented persisted benchmark-run comparison via compare benchmark-runs with truthful comparability signaling, review fixes applied, docs updates, and mirrored automated coverage.`
- Recorded assumptions:
  - The first benchmark-run comparison command should live under `compare`, not `eval`.
  - Multi-run selection should be explicit and deterministic; repeated `--run-id` options are the preferred interface unless the repo establishes a stronger pattern before implementation starts.
  - Benchmark comparison should remain read-only over persisted benchmark evidence and provenance.
  - Cross-repository comparison is out of scope for this story and should fail explicitly instead of producing a misleading side-by-side result.

## Dev Agent Record

### Agent Model Used

Codex (GPT-5)

### Debug Log References

- 2026-03-15: Story context generated via the `bmad-create-story` workflow for backlog story `4-5-compare-benchmark-runs-across-retrieval-strategies`.
- 2026-03-15: Loaded sprint tracking, Epic 4 planning artifacts, benchmark/report implementation stories, current benchmark/report/query comparison code, CLI/docs contracts, and recent git history to derive implementation guardrails.
- 2026-03-15: Verified current official guidance for Typer command composition, repeated option values, and Pydantic strict JSON boundary patterns before finalizing the story.
- 2026-03-15: Implemented `CompareBenchmarkRunsUseCase` over persisted benchmark rows, `run.json`, `metrics.json`, and stored provenance with typed comparison-specific failures and deterministic run ordering.
- 2026-03-15: Added `compare benchmark-runs` CLI wiring, canonical docs updates, unit/integration coverage, and an e2e workflow that proves contextual mismatch signaling.
- 2026-03-15: Applied review fixes by rejecting duplicate run ids, failing cross-repository comparisons before artifact/provenance loading, and keeping benchmark-run comparison read-only so it does not record misleading comparison provenance.
- 2026-03-15: Revalidated the story with focused comparison tests, `ruff check`, and a full `pytest` run (`380 passed`).

### Implementation Plan

- Add benchmark comparison DTOs, comparability surfaces, and error contracts without duplicating existing benchmark/evaluation shapes.
- Implement one persisted-evidence comparison use case that reuses the same validation discipline as benchmark reporting and keeps the comparison workflow read-only over persisted evidence.
- Expose the workflow through `compare benchmark-runs`, then mirror the behavior in docs and automated tests before marking the story ready for completion.

### Completion Notes List

- Added comparison DTOs and typed failures for benchmark-run comparison, including explicit comparability notes/differences, duplicate run-id validation, and stable failure envelopes.
- Implemented `compare benchmark-runs` on top of persisted evidence only, with per-metric winner/tie logic, an early cross-repository hard failure, and a read-only comparison workflow that does not create misleading comparison provenance.
- Updated canonical CLI/benchmark docs and added unit, integration, and e2e coverage for winners, ties, mismatch notes, duplicate ids, and cross-repository precedence.

### File List

- `docs/benchmarks.md`
- `docs/cli-reference.md`
- `src/codeman/application/evaluation/compare_runs.py`
- `src/codeman/bootstrap.py`
- `src/codeman/cli/compare.py`
- `src/codeman/contracts/configuration.py`
- `src/codeman/contracts/errors.py`
- `src/codeman/contracts/evaluation.py`
- `tests/e2e/test_eval_benchmark.py`
- `tests/integration/test_compare_benchmark_runs_integration.py`
- `tests/unit/application/test_compare_benchmark_runs.py`
- `tests/unit/cli/test_compare.py`

## Change Log

- 2026-03-15: Implemented benchmark-run comparison over persisted evidence, added `compare benchmark-runs`, updated docs, and added mirrored unit/integration/e2e coverage.
- 2026-03-15: Applied code-review fixes for duplicate run ids, early cross-repository hard failure, and read-only comparison behavior; reran `ruff check` and full `pytest` (`380 passed`).
