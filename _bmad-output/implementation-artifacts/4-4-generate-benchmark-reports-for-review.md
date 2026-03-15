# Story 4.4: Generate Benchmark Reports for Review

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want benchmark results to be presented in a reviewable report format,
so that I can inspect strategy quality without manually assembling the evidence.

## Acceptance Criteria

1. Given a completed benchmark run with computed metrics, when I request a report, then codeman generates a local benchmark report artifact and a CLI-readable summary, and the report includes benchmark identity, retrieval mode, key metrics, and configuration provenance.
2. Given benchmark results are viewed in machine-readable mode, when the report summary is returned, then it follows the standard JSON envelope contract, and does not mix human commentary into `stdout`.

## Tasks / Subtasks

- [x] Add a narrow report DTO surface and typed report failures. (AC: 1, 2)
  - [x] Extend `src/codeman/contracts/evaluation.py` additively with a compact report result DTO that reuses existing `BenchmarkRunRecord`, `BenchmarkDatasetSummary`, `BenchmarkMetricsSummary`, and provenance DTOs instead of duplicating those shapes.
  - [x] Add report-generation-specific failures in `src/codeman/application/evaluation/` and matching stable error codes in `src/codeman/contracts/errors.py` for missing benchmark run, missing raw artifact, missing metrics artifact, incomplete benchmark state, and missing/corrupt provenance when truthful report generation is impossible.
  - [x] Keep the machine-readable surface small and attributable: it should include the report artifact path plus the benchmark, metrics, and provenance information needed by operators and later automation.

- [x] Implement one report-generation use case that only reads persisted evidence. (AC: 1, 2)
  - [x] Add `src/codeman/application/evaluation/generate_report.py` and wire it to load the benchmark run row, raw `run.json`, additive `metrics.json`, and persisted provenance by the same `run_id`.
  - [x] Validate that run row, raw artifact, metrics artifact, and provenance all refer to the same run/repository/snapshot/dataset/build context before generating the report.
  - [x] Refuse to generate reports for `running`, `failed`, partial, or mismatched benchmark evidence. Report generation is a presentation step, not a recovery path.
  - [x] Do not rerun retrieval queries, recalculate metrics, or mutate the meaning of `run.json` or `metrics.json`. Reuse the persisted truth from Stories 4.2 and 4.3.

- [x] Persist one deterministic local benchmark report artifact. (AC: 1)
  - [x] Extend `ArtifactStorePort` and `FilesystemArtifactStore` with one dedicated benchmark-report seam under `.codeman/artifacts/benchmarks/<run-id>/report.md` or an equivalently deterministic path next to `run.json` and `metrics.json`.
  - [x] Build a human-reviewable report that includes benchmark identity, retrieval mode, build/config provenance, key aggregate metrics, truthful performance summaries, and a compact per-case review appendix derived from persisted metrics.
  - [x] Keep the report concise and review-oriented. Raw benchmark execution evidence already lives in `run.json`, and full metric detail already lives in `metrics.json`; do not dump the entire raw payload into the report artifact.
  - [x] Reuse the existing secret-safe provenance model. Secret-bearing configuration values must not appear in the report artifact.

- [x] Expose benchmark report generation through the existing `eval` CLI surface. (AC: 1, 2)
  - [x] Add a thin command such as `eval report <run-id>` in `src/codeman/cli/eval.py` instead of inventing a new root CLI tree.
  - [x] Return a compact text summary that points to the generated report artifact and surfaces benchmark identity, retrieval mode, key metrics, and configuration provenance.
  - [x] In JSON mode, return exactly one standard success envelope on `stdout` with no interleaved commentary; write progress/status lines to `stderr` only.
  - [x] Wire the new use case through `src/codeman/bootstrap.py` and reuse the shared CLI helpers (`SuccessEnvelope`, `emit_json_response`, `emit_failure_response`) instead of creating a special-case output path.

- [x] Update canonical docs and add mirrored automated coverage. (AC: 1, 2)
  - [x] Update `docs/cli-reference.md` with the supported report command syntax, text/JSON output fields, artifact location, and stable failure semantics.
  - [x] Update `docs/benchmarks.md` so benchmark reports move from future work to implemented behavior once the code exists.
  - [x] Add unit coverage for report DTO validation, report-generation identity checks, secret-safe provenance rendering, and CLI text/JSON output formatting.
  - [x] Add integration coverage for the new artifact-store seam and any persistence adapter changes that are genuinely needed.
  - [x] Add end-to-end coverage that creates a benchmark run from the mixed-stack fixtures, requests a report in text and JSON modes, asserts the local report artifact exists, and proves `stdout`/`stderr` separation remains intact.

## Dev Notes

### Epic Context

- Story 4.4 is the presentation layer for benchmark evidence. Story 4.2 already captures truthful raw benchmark execution, and Story 4.3 already captures deterministic metric outputs.
- Story 4.5 and Story 4.6 depend on Story 4.4 preserving attributable benchmark identity, metrics, and provenance in a reviewable form instead of rebuilding evidence ad hoc.
- The acceptance criteria are intentionally narrow: generate a local report artifact plus a CLI-readable summary for an already completed benchmark run.

### Current Repo State

- `src/codeman/application/evaluation/` currently contains `load_benchmark_dataset.py`, `run_benchmark.py`, and `calculate_benchmark_metrics.py`. There is no report-generation use case yet.
- `src/codeman/cli/eval.py` currently exposes only `eval benchmark`; there is no `eval report` command or equivalent benchmark-report workflow.
- `src/codeman/contracts/evaluation.py` already defines strict DTOs for benchmark runs, metrics summaries, raw benchmark artifacts, and additive metrics artifacts, but it does not define a report result contract.
- `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py` currently knows how to read/write `run.json` and `metrics.json` for benchmark runs; there is no report artifact seam yet.
- `src/codeman/infrastructure/persistence/sqlite/tables.py` and `src/codeman/infrastructure/persistence/sqlite/repositories/benchmark_run_repository.py` track benchmark lifecycle and metrics summary fields, but there is no persisted report-generation metadata today.
- `src/codeman/application/provenance/show_run_provenance.py` already provides a narrow way to load stored configuration provenance by `run_id`; Story 4.4 should reuse that existing seam rather than reading provenance tables directly in the CLI.
- `docs/benchmarks.md` still says benchmark reports remain future work for Stories 4.4-4.6.
- The planning architecture mentions `application/evaluation/generate_report.py` and a future `tests/fixtures/benchmark_reports/` area, but the current implemented codebase does not have either yet. Use current code as the source of truth.

### Previous Story Intelligence

- Story 4.3 intentionally made metrics durable and attributable under `.codeman/artifacts/benchmarks/<run-id>/metrics.json`. Story 4.4 should consume that persisted metrics artifact rather than recalculating metrics from raw case outputs. [Source: _bmad-output/implementation-artifacts/4-3-calculate-and-store-retrieval-quality-metrics.md]
- Story 4.2 already persists the raw benchmark artifact, benchmark run row, and shared run-id provenance lineage. Story 4.4 should treat those persisted artifacts as the truth surface for reporting, not rerun benchmark execution. [Source: _bmad-output/implementation-artifacts/4-2-execute-a-benchmark-run-against-an-indexed-repository.md]
- The final review fixes for Stories 4.2 and 4.3 matter directly here:
  - benchmark rows and artifacts are pinned to the preflight-resolved build context;
  - failed or interrupted runs are finalized truthfully;
  - JSON CLI behavior must keep one stable envelope on `stdout`.
  Report generation should preserve those guarantees instead of smoothing over missing or inconsistent evidence.
- Story 4.3 already surfaces the exact benchmark fields Story 4.4 needs for operator review: evaluated `k`, Recall@K, MRR, NDCG@K, query latency summaries, indexing-duration summaries, and metrics artifact path. [Source: src/codeman/contracts/evaluation.py; src/codeman/application/evaluation/calculate_benchmark_metrics.py]

### Cross-Story Baseline

- Story 4.1 established benchmark dataset truth: repository-relative POSIX paths, optional 1-based line spans, stable dataset id/version/fingerprint, and positive `relevance_grade` values. Story 4.4 should report those dataset identities, not invent a second benchmark identity model. [Source: _bmad-output/implementation-artifacts/4-1-define-the-golden-query-benchmark-dataset.md]
- Story 3.4 established the shared run-provenance pattern. Story 4.4 should load provenance by the existing `run_id` and reuse its secret-safe configuration shape rather than building a benchmark-only provenance surface. [Source: _bmad-output/implementation-artifacts/3-4-record-configuration-provenance-for-every-run.md; src/codeman/application/provenance/show_run_provenance.py]
- Story 3.5 established configuration/profile reuse lineage. Report output should include enough provenance to show which effective configuration produced the benchmark, including reuse lineage where present. [Source: _bmad-output/implementation-artifacts/3-5-reuse-prior-configurations-in-later-experiments.md]
- Story 3.6 established deterministic content/config identity and runtime artifact discipline. Story 4.4 should keep report generation deterministic, local-first, and keyed to persisted artifacts rather than mutable live repository state. [Source: _bmad-output/implementation-artifacts/3-6-key-caches-to-configuration-and-content-identity.md]
- `compare query-modes` is a useful implementation pattern for compact text summaries, clean JSON envelopes, and thin CLI wiring. Story 4.4 can reuse those presentation patterns without reusing comparison-specific logic. [Source: src/codeman/cli/compare.py]

### Technical Guardrails

- Keep the workflow CLI-first and local-first. Do not add HTTP routes, MCP execution, background workers, external report exporters, or provider-backed judge flows in this story. [Source: docs/project-context.md; docs/architecture/decisions.md]
- Generate reports strictly from persisted benchmark evidence (`benchmark_runs`, `run.json`, `metrics.json`, and stored provenance). Do not rerun retrieval, reload the authored dataset from disk, or recompute metrics. [Source: docs/project-context.md; src/codeman/application/evaluation/run_benchmark.py; src/codeman/application/evaluation/calculate_benchmark_metrics.py]
- Keep boundary models strict with `ConfigDict(extra="forbid")` and predictable field names. Prefer additive DTOs over loose dicts. [Source: docs/project-context.md; src/codeman/contracts/evaluation.py]
- Preserve the `stdout`/`stderr` split: text or JSON summary on `stdout`, progress and operator commentary on `stderr`, and JSON mode must remain a single final envelope. [Source: docs/architecture/decisions.md; docs/cli-reference.md; src/codeman/cli/eval.py]
- Do not introduce a heavyweight templating or reporting dependency just to write one local report artifact. The current repo favors narrow Python stdlib-based rendering and strict DTOs over extra libraries for simple formatting. Inference from repo state: a deterministic Markdown report plus the existing JSON envelope is the smallest credible implementation.
- Reuse the secret-safe provenance surface exactly as stored. Never print API keys, local secret values, or raw protected config payloads into the report. [Source: docs/benchmarks.md; docs/cli-reference.md; src/codeman/contracts/configuration.py]
- Prefer a deterministic report path derived from `run_id`. Avoid adding new SQLite columns or migrations for report metadata unless the implementation truly needs queryable persisted report state beyond an artifact path that is already derivable from the run id. Inference from current code: Story 4.4 can likely stay simpler than Story 4.3 if the artifact path is fixed and returned directly.
- Keep ordering deterministic. If the report includes case-level sections, either preserve benchmark dataset order or use an explicitly documented stable sort with deterministic tie-breakers.

### Implementation Notes

- `GenerateBenchmarkReportUseCase` should likely depend on:
  - `BenchmarkRunStorePort`
  - `ArtifactStorePort`
  - `ShowRunConfigurationProvenanceUseCase` or the underlying provenance port
  This keeps the use case inside the current layered boundary instead of letting the CLI orchestrate multiple stores directly.
- Reuse the existing benchmark DTOs instead of copying fields into a second parallel model. A small result wrapper that carries `run`, `dataset`, `metrics`, `provenance`, and `report_artifact_path` should be enough for the CLI contract.
- The report artifact should be reviewable first. A Markdown file under the run directory is the simplest fit with the acceptance criteria and the planning architecture’s “generated reports live under `.codeman/artifacts/`” rule. [Source: _bmad-output/planning-artifacts/architecture.md]
- A practical report structure for this story is:
  - benchmark identity and timestamps
  - retrieval/build/config provenance summary
  - aggregate metrics and performance summary
  - concise per-case appendix for review
  This is enough to make quality review possible without copying the full raw retrieval payload.
- The per-case appendix should come from `BenchmarkCaseMetricResult` values in `metrics.json`, not from a second live evaluation pass. Useful columns are `query_id`, `source_kind`, matched vs total judgments, `first_relevant_rank`, `recall_at_k`, `reciprocal_rank`, `ndcg_at_k`, and `query_latency_ms`.
- If the report highlights weak cases, define the ranking explicitly and deterministically (for example, lowest `recall_at_k`, then lowest `ndcg_at_k`, then `query_id`) so repeated runs over the same persisted evidence produce the same report ordering.
- Keep the benchmark report additive. Generating a report should not create a new benchmark run id or a second provenance lineage. It is a read-and-render workflow over an existing completed run.

### File Structure Requirements

- Likely new source file: `src/codeman/application/evaluation/generate_report.py`
- Expected touched source files:
  - `src/codeman/application/ports/artifact_store_port.py`
  - `src/codeman/bootstrap.py`
  - `src/codeman/cli/eval.py`
  - `src/codeman/contracts/errors.py`
  - `src/codeman/contracts/evaluation.py`
  - `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py`
- Reuse existing provenance seams instead of bypassing them:
  - `src/codeman/application/provenance/show_run_provenance.py`
  - `src/codeman/contracts/configuration.py`
- Documentation updates belong in:
  - `docs/cli-reference.md`
  - `docs/benchmarks.md`
- Likely new or extended tests:
  - `tests/unit/application/test_generate_report.py`
  - `tests/unit/cli/test_eval.py`
  - `tests/unit/infrastructure/test_filesystem_artifact_store.py`
  - `tests/e2e/test_eval_report.py` or an additive extension to `tests/e2e/test_eval_benchmark.py`
- Only add a migration if report metadata truly must be queryable from SQLite. A deterministic artifact path may let this story avoid unnecessary schema churn.

### Testing Requirements

- Add focused unit tests for the report use case covering:
  - successful report generation from matching persisted run, raw artifact, metrics artifact, and provenance;
  - refusal when the benchmark run is unknown;
  - refusal when the benchmark run is still `running` or `failed`;
  - refusal when `run.json`, `metrics.json`, or provenance is missing, corrupt, or mismatched;
  - deterministic report content/order and secret-safe provenance rendering.
- Extend CLI unit coverage in `tests/unit/cli/test_eval.py` for:
  - text summary rendering;
  - JSON success envelope shape for the new report command;
  - stable failure envelopes with the new report-specific error codes;
  - clean `stdout` with progress lines on `stderr`.
- Extend artifact-store tests to prove the new benchmark report seam writes to the deterministic benchmark-run directory and can be re-read if the implementation exposes a read helper.
- Add end-to-end coverage using the existing mixed-stack fixtures and benchmark workflow:
  - register repo;
  - snapshot repo;
  - extract sources;
  - build chunks/indexes;
  - run `eval benchmark`;
  - run the new report command against the resulting `run_id`.
- Include at least one scenario that proves provenance details are surfaced truthfully from stored config metadata. If provider/model fields are conditional, cover both the lexical-only and semantic/hybrid shapes through a mix of unit and e2e tests instead of making e2e unnecessarily heavy.
- Run the story-touched regression suite plus `ruff check` on the touched source/test files before closing the implementation.

### Git Intelligence Summary

- Commit `de9054a` (`story(4-3): complete benchmark metrics workflow`) is the immediate baseline. Story 4.4 should build directly on the persisted metrics artifact and summary fields added there, not recreate metric logic.
- Commit `8b4c797` (`story(4-2): fix final benchmark review findings`) reinforces a repo value that matters for report generation too: keep benchmark workflows truthful and preserve clean machine-readable failure envelopes.
- Commit `f682e66` (`story(4-2): close benchmark execution after review fixes`) established the benchmark implementation pattern to reuse now:
  - one focused use case in `application/evaluation/`
  - additive DTO changes
  - a dedicated artifact seam
  - thin CLI wiring through `bootstrap.py`
  - mirrored unit/integration/e2e coverage
- Commit `147399b` (`story(4-1-define-the-golden-query-benchmark-dataset): complete code review and mark done`) remains the benchmark truth-model baseline. Reports should present that dataset identity clearly instead of introducing a second naming scheme.
- Commit `c447863` (`story(3-6-key-caches-to-configuration-and-content-identity): complete code review and mark done`) reinforces deterministic identity, runtime-local artifacts, and stable fingerprinting. Report generation should follow that same discipline.

### Latest Technical Information

- As of March 15, 2026, Typer’s official docs still center nested CLI composition through `app.add_typer(...)`. Inference: the benchmark report surface should live under the existing `eval` group in `src/codeman/cli/eval.py`, not through a new root command tree. [Source: https://typer.tiangolo.com/tutorial/subcommands/add-typer/]
- As of March 15, 2026, the official Pydantic docs continue to document `ConfigDict` for model configuration and `model_validate_json()` for strict JSON-bound validation. Inference: any new report DTOs should stay strict and JSON-friendly in the same style as the current benchmark contracts. [Source: https://docs.pydantic.dev/latest/api/config/; https://docs.pydantic.dev/latest/concepts/json/]
- As of March 15, 2026, Python’s official `json` docs still document deterministic serialization controls such as `sort_keys=True` and explicit `separators`. Inference: if Story 4.4 needs any compact machine-readable sidecar or canonical JSON rendering, it should reuse the repo’s current deterministic JSON approach instead of inventing a custom serializer. [Source: https://docs.python.org/3/library/json.html]

### Project Context Reference

- `docs/project-context.md` remains the canonical agent-facing implementation ruleset: strict Pydantic boundary models, thin CLI handlers, deterministic ordering, runtime-managed artifacts under `.codeman/`, and mirrored automated coverage for touched behavior.
- `docs/architecture/decisions.md` and `docs/architecture/patterns.md` keep the extension path narrow: `cli -> application -> ports -> infrastructure -> contracts/config/runtime`.
- `docs/benchmarks.md` owns the human-facing benchmark/evaluation policy. Update it honestly instead of copying benchmark policy into multiple documents.
- No separate UX artifact exists. The relevant UX requirement here is operator clarity: a benchmark report should make review possible without sacrificing truthful machine-readable behavior.

### Project Structure Notes

- The current split metadata/artifact architecture already fits this story:
  - SQLite remains the source of truth for benchmark lifecycle and searchable summary values.
  - `.codeman/artifacts/benchmarks/<run-id>/` remains the home for generated benchmark artifacts.
- Unlike Story 4.3, Story 4.4 may not need new benchmark-run summary columns if the report artifact path is fully deterministic from `run_id`. Prefer the smaller implementation unless a real query need appears during development.
- The existing `eval benchmark` command remains the canonical producer of benchmark evidence. Story 4.4 should consume that evidence additively rather than extending `eval benchmark` into a mixed execution-plus-reporting command.
- `tests/fixtures/benchmark_reports/` appears in the planning architecture, but the current repo does not yet contain that fixture directory. Only add it if the final implementation genuinely needs fixture artifacts that cannot be produced inline in tests.

### References

- [Source: docs/project-context.md]
- [Source: docs/README.md]
- [Source: docs/architecture/decisions.md]
- [Source: docs/architecture/patterns.md]
- [Source: docs/benchmarks.md]
- [Source: docs/cli-reference.md]
- [Source: src/codeman/cli/app.py]
- [Source: src/codeman/cli/eval.py]
- [Source: src/codeman/cli/compare.py]
- [Source: src/codeman/application/evaluation/run_benchmark.py]
- [Source: src/codeman/application/evaluation/calculate_benchmark_metrics.py]
- [Source: src/codeman/application/provenance/show_run_provenance.py]
- [Source: src/codeman/application/ports/artifact_store_port.py]
- [Source: src/codeman/contracts/configuration.py]
- [Source: src/codeman/contracts/evaluation.py]
- [Source: src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/tables.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/benchmark_run_repository.py]
- [Source: tests/unit/cli/test_eval.py]
- [Source: tests/e2e/test_eval_benchmark.py]
- [Source: tests/fixtures/queries/mixed_stack_fixture_golden_queries.json]
- [Source: _bmad-output/planning-artifacts/epics.md - Epic 4; Story 4.1; Story 4.2; Story 4.3; Story 4.4; Story 4.5; Story 4.6]
- [Source: _bmad-output/planning-artifacts/prd.md - FR20; FR23; NFR3; NFR12-NFR19]
- [Source: _bmad-output/planning-artifacts/architecture.md - evaluation/reporting; application/evaluation/generate_report.py; filesystem artifacts; data flow]
- [Source: _bmad-output/implementation-artifacts/4-1-define-the-golden-query-benchmark-dataset.md]
- [Source: _bmad-output/implementation-artifacts/4-2-execute-a-benchmark-run-against-an-indexed-repository.md]
- [Source: _bmad-output/implementation-artifacts/4-3-calculate-and-store-retrieval-quality-metrics.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: https://typer.tiangolo.com/tutorial/subcommands/add-typer/]
- [Source: https://docs.pydantic.dev/latest/api/config/]
- [Source: https://docs.pydantic.dev/latest/concepts/json/]
- [Source: https://docs.python.org/3/library/json.html]

## Story Completion Status

- Status set to `ready-for-dev`.
- Completion note: `Ultimate context engine analysis completed - comprehensive developer guide created.`
- Recorded assumptions:
  - The first benchmark report request surface should be a focused `eval report <run-id>` command under the existing `eval` group.
  - A deterministic local Markdown artifact under the benchmark run directory is sufficient for the first reviewable report implementation; JSON machine-readability should come from the standard CLI envelope, not a second reporting workflow.
  - Report generation should remain a read-and-render workflow over existing benchmark evidence, not a second benchmark execution or metrics calculation path.
  - Persisting report metadata in SQLite is optional for this story and should be avoided unless implementation work reveals a concrete query/use-case need.

## Dev Agent Record

### Agent Model Used

Codex (GPT-5)

### Debug Log References

- 2026-03-15: Story context generated via the `bmad-create-story` workflow for backlog story `4-4-generate-benchmark-reports-for-review`.
- 2026-03-15: Loaded Epic 4, PRD, architecture, current benchmark policy/docs, completed Stories 4.1-4.3, current evaluation/provenance code, benchmark CLI/tests, and recent git history to derive the report-generation guardrails for this story.
- 2026-03-15: Verified current official guardrails for Typer nested command composition, Pydantic strict JSON DTOs, and deterministic Python JSON serialization before finalizing the implementation-ready story.
- 2026-03-15: Implemented `GenerateBenchmarkReportUseCase`, report DTOs, report-specific failures, deterministic `report.md` artifact persistence, and `eval report <run-id>` wiring through the shared bootstrap and CLI helpers.
- 2026-03-15: Added report-focused unit coverage for DTO validation, use-case evidence identity checks, CLI text/JSON behavior, artifact-store round trips, and hybrid provenance rendering.
- 2026-03-15: Ran `ruff check`, `ruff format --check`, targeted benchmark/report test suites, and the full `pytest` suite (`359 passed`) before moving the story to review.
- 2026-03-15: Fixed code-review findings by wrapping report artifact write failures in typed benchmark-report errors, validating duplicated run/metrics summary fields against `metrics.json`, normalizing benchmark-run SQLite datetimes to UTC-aware values, and rerunning the touched suites plus full regression (`361 passed`).

### Implementation Plan

- Add one focused benchmark report use case that reads the persisted benchmark run, metrics artifact, raw artifact, and stored provenance, then writes one deterministic local report artifact.
- Expose the workflow as a thin `eval` subcommand with compact text output and the standard JSON envelope, keeping progress on `stderr`.
- Update canonical docs and mirror the change with unit, integration, and e2e coverage centered on truthful persisted-evidence reporting.

### Completion Notes List

- Story context created and validated against the current codebase, planning artifacts, benchmark policy docs, and recent benchmark implementation history.
- Added a new benchmark report workflow that reads persisted benchmark runs, raw artifacts, metrics artifacts, and stored provenance without rerunning retrieval or recalculating metrics.
- Persisted deterministic Markdown reports at `.codeman/artifacts/benchmarks/<run-id>/report.md` and exposed the same evidence through the standard JSON success envelope returned by `eval report`.
- Updated canonical benchmark/CLI docs and mirrored the change with unit, integration-style artifact seam coverage, end-to-end CLI coverage, and a full repository regression run.
- Closed the story after review fixes restored `eval report` success on real benchmark flows, preserved the stable failure envelope for report-write errors, and verified story-touched formatting plus full `pytest` regression coverage.

### File List

- _bmad-output/implementation-artifacts/4-4-generate-benchmark-reports-for-review.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- docs/benchmarks.md
- docs/cli-reference.md
- src/codeman/application/evaluation/__init__.py
- src/codeman/application/evaluation/generate_report.py
- src/codeman/application/ports/artifact_store_port.py
- src/codeman/bootstrap.py
- src/codeman/cli/eval.py
- src/codeman/contracts/errors.py
- src/codeman/contracts/evaluation.py
- src/codeman/infrastructure/artifacts/filesystem_artifact_store.py
- src/codeman/infrastructure/persistence/sqlite/repositories/benchmark_run_repository.py
- tests/e2e/test_eval_benchmark.py
- tests/integration/persistence/test_benchmark_run_repository.py
- tests/unit/application/test_generate_benchmark_report.py
- tests/unit/cli/test_eval.py
- tests/unit/contracts/test_evaluation.py
- tests/unit/infrastructure/test_filesystem_artifact_store.py

## Change Log

- 2026-03-15: Implemented benchmark report generation from persisted evidence, added deterministic report artifact persistence, exposed `eval report`, updated canonical docs, and added mirrored automated coverage.
- 2026-03-15: Addressed final code-review findings for report write-failure typing and persisted-summary consistency, normalized benchmark-run SQLite datetime round trips, and closed the story after full regression validation (`361 passed`).
