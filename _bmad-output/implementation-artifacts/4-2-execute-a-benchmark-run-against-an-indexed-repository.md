# Story 4.2: Execute a Benchmark Run Against an Indexed Repository

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want to execute a benchmark run from the CLI,
so that I can evaluate retrieval behavior for a specific repository state and configuration.

## Acceptance Criteria

1. Given an indexed repository and a valid benchmark dataset, when I run the benchmark command, then codeman executes the benchmark cases against the selected retrieval mode or strategy, and records a benchmark run with repository, configuration, and timestamp metadata.
2. Given a benchmark run is in progress, when progress is reported, then codeman uses consistent run phases and preserves clean JSON `stdout` in machine mode, and records a clear success or failure outcome at completion.

## Tasks / Subtasks

- [x] Add benchmark-run contracts, typed errors, and persistence seams. (AC: 1, 2)
  - [x] Extend `src/codeman/contracts/evaluation.py` with additive DTOs for a benchmark run request/result, benchmark run status, raw run artifact documents, and per-case execution output.
  - [x] Add stable benchmark-execution error codes in `src/codeman/contracts/errors.py` plus benchmark-specific typed application errors instead of leaking raw lexical/semantic/hybrid failures as the top-level `eval` contract.
  - [x] Add a `benchmark_runs` persistence seam and SQLite-backed repository under `src/codeman/infrastructure/persistence/sqlite/repositories/`, backed by an Alembic migration and matching table entries in `src/codeman/infrastructure/persistence/sqlite/tables.py`.
  - [x] Reuse one shared run identifier across the benchmark row, benchmark artifact namespace, and provenance row whenever practical; do not generate multiple unrelated ids for the same execution.

- [x] Implement a benchmark orchestration use case in `src/codeman/application/evaluation/` that reuses existing query flows. (AC: 1, 2)
  - [x] Add `src/codeman/application/evaluation/run_benchmark.py` as the primary orchestration entrypoint for this story.
  - [x] Reuse `LoadBenchmarkDatasetUseCase` from Story 4.1 and dispatch each benchmark case through exactly one selected retrieval use case (`RunLexicalQueryUseCase`, `RunSemanticQueryUseCase`, or `RunHybridQueryUseCase`) instead of inventing a parallel retrieval implementation.
  - [x] Call inner query use cases with `record_provenance=False` so one benchmark invocation produces one benchmark-level provenance record rather than one nested provenance row per query case.
  - [x] Resolve the repository and selected baseline up front, fail clearly when the chosen mode has no usable build for the current effective configuration, and persist only truthful run status transitions.
  - [x] Keep one retrieval mode per benchmark invocation. Side-by-side mode comparison belongs to Story 4.5, not this story.

- [x] Persist raw benchmark execution artifacts without jumping ahead to metrics or reports. (AC: 1)
  - [x] Extend `ArtifactStorePort` and `FilesystemArtifactStore` with a benchmark artifact write/read seam instead of writing ad hoc JSON from the use case.
  - [x] Persist generated benchmark artifacts under `.codeman/artifacts/benchmarks/<run-id>/` (or one equivalently deterministic runtime path), not under `src/`, `tests/fixtures/`, or the indexed target repository.
  - [x] Snapshot the normalized benchmark inputs actually used for the run inside the generated artifact, including dataset identity/version/fingerprint and per-case judgments, so later metrics/reporting remain reproducible even if the authored dataset file changes on disk.
  - [x] Persist raw per-case outputs needed by later stories: query identity/text, source kind, expected judgments, ranked retrieval results, relevant build/snapshot context, and query latency data, but do not calculate Recall@K, MRR, NDCG, or reports yet.
  - [x] Keep artifacts compact and operator-safe: persist the current retrieval-result package or a strict additive subset of it, not full chunk payload contents or arbitrary repository dumps.

- [x] Record benchmark lifecycle truthfully, including explicit failure outcomes after a run starts. (AC: 2)
  - [x] Create the benchmark run record only after preflight validation succeeds (dataset load plus baseline resolution), then move it through explicit states such as `running` -> `succeeded` or `failed`.
  - [x] If the benchmark fails after execution starts, finalize the benchmark row with `failed`, capture stable error metadata, and make any partial artifact unmistakably failed rather than looking like a successful complete run.
  - [x] If dataset validation fails before execution begins, reuse Story 4.1's typed dataset failures and do not emit misleading success artifacts or completed benchmark rows.
  - [x] Keep benchmark datasets as authored input files outside `.codeman/`; only generated benchmark outputs belong in runtime-managed storage.

- [x] Add the public benchmark CLI surface under the existing `eval` Typer group. (AC: 1, 2)
  - [x] Implement a narrow command such as `uv run codeman eval benchmark <repository-id> <dataset-path>` in `src/codeman/cli/eval.py`.
  - [x] Support `--retrieval-mode` (`lexical`, `semantic`, `hybrid`) and `--max-results`, while reusing the existing root `--profile` option for retrieval strategy selection instead of inventing a benchmark-only profile selector.
  - [x] Keep `src/codeman/cli/eval.py` thin: parse input, resolve the container, call one use case, and render either text output or the standard JSON envelope.
  - [x] Report progress only on `stderr` using stable present-tense phase lines and optional case counters; keep JSON `stdout` as one final machine-readable envelope with no interleaved commentary.
  - [x] Return a compact benchmark summary in both text and JSON modes: run id, repository id, snapshot id, retrieval mode, dataset identity/version, case counts, status, timestamps, and artifact path.

- [x] Extend provenance and docs additively, without pulling later Epic 4 stories forward. (AC: 1, 2)
  - [x] Extend `RunProvenanceWorkflowType` and `RunProvenanceWorkflowContext` to support benchmark execution with dataset, mode, and build references, reusing the existing secret-safe effective-config lineage instead of inventing a second configuration attribution scheme.
  - [x] Wire the benchmark use case through `src/codeman/bootstrap.py` and keep the CLI root registration under the existing `eval` group in `src/codeman/cli/app.py`.
  - [x] Update `docs/cli-reference.md` with the new `eval benchmark` command, stable text/JSON behavior, failure semantics, and stdout/stderr discipline.
  - [x] Update `docs/benchmarks.md` with the implemented benchmark-execution status and the honest boundary that metrics, reports, run comparison, and regressions still belong to Stories 4.3-4.6.
  - [x] Do not add metrics calculation, benchmark report generation, run comparison, regression detection, synthetic-query generation, or judge workflows in this story.

- [x] Add mirrored automated coverage for orchestration, persistence, and CLI behavior. (AC: 1, 2)
  - [x] Add unit tests for benchmark orchestration happy paths and failure mapping: invalid dataset, missing selected baseline, query-path failure during execution, and truthful status finalization.
  - [x] Add unit tests for the new `eval benchmark` CLI in text and JSON modes, including stderr progress behavior and stable failure envelopes.
  - [x] Add integration coverage for the benchmark run repository and benchmark artifact storage seam, including migration/bootstrap behavior and deterministic path handling.
  - [x] Add e2e coverage for `uv run codeman eval benchmark ...` using the mixed-stack repository fixture and seeded golden-query dataset in both text and JSON modes.

## Dev Notes

### Epic Context

- Story 4.2 is the first true benchmark-execution workflow in the codebase. Story 4.1 only established benchmark dataset truth and validation; Story 4.2 turns that dataset into an executable CLI workflow.
- Story 4.3 depends on Story 4.2 persisting raw per-case benchmark outputs and attributable run metadata so metrics can be calculated later without re-running retrieval blindly.
- Story 4.4 depends on Story 4.2 persisting artifact paths and compact summary data so benchmark review can be built as a report layer instead of embedding reporting logic into the execution command.
- Story 4.5 and Story 4.6 depend on Story 4.2 preserving dataset identity, repository/snapshot identity, configuration provenance, and stable run ids so later comparisons and regressions stay attributable.

### Current Repo State

- `src/codeman/cli/eval.py` is still only a placeholder Typer group with no implemented benchmark command.
- `src/codeman/application/evaluation/` exists today only for Story 4.1's dataset loader (`load_benchmark_dataset.py`); there is no benchmark runner yet.
- `src/codeman/contracts/evaluation.py` currently defines dataset contracts and summary metadata, but it does not yet define benchmark-run request/result DTOs, benchmark-run artifacts, or benchmark persistence models.
- `docs/benchmarks.md` now documents the implemented dataset schema and explicitly says benchmark execution, metrics, reports, comparisons, and regressions begin in Story 4.2 and later.
- `docs/cli-reference.md` currently documents repository, index, query, compare, and config surfaces, but it still lacks an `eval benchmark` command contract.
- `src/codeman/application/query/run_lexical_query.py`, `run_semantic_query.py`, and `run_hybrid_query.py` already provide the truthful retrieval execution paths that this story should reuse.
- `src/codeman/application/query/compare_retrieval_modes.py` is a useful composition example, but it is not a benchmark runner and should not become the execution engine for Story 4.2.
- `src/codeman/contracts/configuration.py` and `src/codeman/application/provenance/record_run_provenance.py` already provide a secret-safe configuration provenance foundation, but the current `RunProvenanceWorkflowType` literal does not yet include benchmark execution.
- `src/codeman/infrastructure/persistence/sqlite/tables.py` has no benchmark-run table yet, and `FilesystemArtifactStore` has no benchmark artifact method yet.

### Previous Story Intelligence

- Story 4.1 already established the canonical benchmark dataset truth model: JSON-only authored input, strict Pydantic validation, normalized repository-relative POSIX paths, optional 1-based line spans, and additive dataset fingerprinting.
- Story 4.1 also established the benchmark-dataset failure taxonomy in `LoadBenchmarkDatasetUseCase`; Story 4.2 should surface those typed failures cleanly from the benchmark CLI instead of duplicating path, JSON, or schema validation logic.
- Story 4.1's post-review fixes matter here:
  - Windows absolute benchmark locators are invalid and must stay rejected.
  - Positive relevance grades intentionally remain open-ended for future NDCG work.
  - Dataset truth is anchored to stable repository-relative locators, not to chunk ids or snapshot-scoped identifiers.
- The seeded mixed-stack benchmark dataset and repository fixtures already exist:
  - `tests/fixtures/queries/mixed_stack_fixture_golden_queries.json`
  - `tests/fixtures/repositories/mixed_stack_fixture/`
  Story 4.2 should use those existing assets for tests instead of inventing a second benchmark corpus.

### Cross-Story Baseline

- The existing retrieval result contracts already expose the stable locators later metric work needs: `relative_path`, `language`, `start_line`, `end_line`, `chunk_id`, and truthful query diagnostics. Benchmark execution should preserve those results rather than inventing a second relevance-output vocabulary.
- Story 3.4 established the repo's current provenance pattern: one stable `run_id`, secret-safe effective configuration, workflow-type tagging, and structured workflow context. Story 4.2 should extend that pattern for benchmark runs instead of creating an evaluation-only provenance mechanism.
- Story 3.5 established explicit profile-reuse lineage. Story 4.2 should rely on the existing root `--profile` resolution and persisted provenance rather than inventing benchmark-specific profile selection or config capture.
- Story 3.6 established deterministic identity and cache behavior as first-class values. Benchmark execution should preserve the same discipline for dataset fingerprints, artifact paths, ordering, and run attribution.
- The current root CLI already exposes `--profile`, `--workspace-root`, and output-format handling. Benchmark execution should fit inside that existing operational model, not bypass it.

### Technical Guardrails

- Keep the workflow CLI-first and local-first. Do not add HTTP routes, MCP runtime behavior, background workers, provider-backed judge workflows, or synthetic-query generation in this story. [Source: docs/project-context.md; docs/architecture/decisions.md]
- Put orchestration in `src/codeman/application/evaluation/` and keep `src/codeman/cli/eval.py` thin. Do not rebuild query logic in the CLI layer. [Source: docs/project-context.md; docs/architecture/patterns.md]
- Reuse `LoadBenchmarkDatasetUseCase` and the existing query use cases instead of duplicating dataset validation, index lookup, artifact loading, provider setup, or retrieval-result enrichment. [Source: src/codeman/application/evaluation/load_benchmark_dataset.py; src/codeman/application/query/run_lexical_query.py; src/codeman/application/query/run_semantic_query.py; src/codeman/application/query/run_hybrid_query.py]
- Call inner query use cases with `record_provenance=False`. Benchmark execution should produce one benchmark-level provenance row, not one extra provenance row per benchmark case. [Source: src/codeman/contracts/retrieval.py; src/codeman/application/provenance/record_run_provenance.py]
- Execute one retrieval mode per benchmark run. Do not compare lexical/semantic/hybrid side by side in the same benchmark command, and do not reuse `compare query-modes` as the benchmark engine. [Source: _bmad-output/planning-artifacts/epics.md - Story 4.2; _bmad-output/implementation-artifacts/2-7-compare-retrieval-modes-for-the-same-question.md]
- Snapshot the normalized benchmark inputs used at execution time into the generated run artifact. Do not rely on rereading a mutable dataset path later when Story 4.3 calculates metrics or Story 4.4 renders reports. [Source: docs/benchmarks.md; _bmad-output/implementation-artifacts/4-1-define-the-golden-query-benchmark-dataset.md]
- Keep authored benchmark datasets outside `.codeman/` and generated benchmark outputs inside `.codeman/artifacts/`. Do not copy authored datasets into source control locations as a side effect of execution. [Source: docs/project-context.md; docs/architecture/patterns.md; docs/benchmarks.md]
- Preserve JSON `stdout` discipline: progress belongs on `stderr`, and machine-readable output should be one final envelope only. [Source: docs/architecture/decisions.md; docs/project-context.md; src/codeman/cli/common.py]
- Reuse the existing secret-safe configuration provenance flow. Benchmark rows and artifacts may reference provider/model metadata when relevant, but they must not persist raw provider secrets. [Source: docs/project-context.md; src/codeman/contracts/configuration.py; src/codeman/application/provenance/record_run_provenance.py]
- Use the current query package's `diagnostics.query_latency_ms` as the canonical per-case latency metric for benchmark execution. If additional harness timing is captured, keep it additive and clearly named instead of silently replacing the query-layer latency number. [Inference from current query contracts and NFR3/NFR4]
- Do not calculate Recall@K, MRR, NDCG, benchmark reports, run comparison deltas, or regression judgments in this story. Story 4.2 owns execution and attributable raw evidence only. [Source: _bmad-output/planning-artifacts/epics.md - Stories 4.3-4.6; docs/benchmarks.md]
- Keep DTOs strict with `ConfigDict(extra="forbid")`, keep use cases as typed `@dataclass(slots=True)` classes, and keep ordering deterministic across cases, stored results, and output summaries. [Source: docs/project-context.md; src/codeman/contracts/evaluation.py; src/codeman/bootstrap.py]

### Implementation Notes

- Prefer a split benchmark persistence shape:
  - a compact SQLite `benchmark_runs` row for searchable run status and attribution;
  - one normalized JSON artifact for raw per-case benchmark evidence.
  This matches the repo's current split metadata/artifact architecture.
- A practical run-summary row for this story is:
  - `run_id`
  - `repository_id`
  - `snapshot_id`
  - `retrieval_mode`
  - `dataset_id`
  - `dataset_version`
  - `dataset_fingerprint`
  - `case_count`
  - `completed_case_count`
  - `status`
  - `artifact_path`
  - `error_code` / `error_message` (nullable)
  - `started_at`
  - `completed_at`
  Keep metrics columns out of this table until Story 4.3 actually implements them.
- Because one benchmark run executes exactly one retrieval mode, keep the raw artifact schema run-level-mode-specific or normalized at the run level. Avoid a per-case mixed-mode union format that makes contracts and tests harder to reason about.
- A practical raw artifact should snapshot:
  - benchmark run id and status
  - repository and snapshot identity
  - retrieval mode and build/provider summary
  - dataset id/version/fingerprint plus the normalized case definitions used
  - one list of case execution outputs, each with query identity/text, expected judgments, retrieval results, and latency/diagnostics
  - started/completed timestamps
- Prefer a small dispatch helper inside `run_benchmark.py` that selects the correct retrieval use case once and keeps mode-specific branching out of the CLI and persistence layers.
- The preflight sequence should stay explicit:
  1. load and validate the dataset
  2. resolve the repository and selected retrieval baseline
  3. allocate the run id and create the `running` record
  4. execute benchmark cases in deterministic dataset order
  5. write the benchmark artifact
  6. persist the final `succeeded` or `failed` row and the benchmark provenance context
- If a case fails after the benchmark has started, keep the outcome truthful. A partial artifact is acceptable only if it is explicitly marked failed and cannot be mistaken for a complete successful benchmark run.
- Reuse the existing retrieval result package or a strict additive subset of it. Do not reread chunk payload artifacts just to persist more repository text than the current retrieval contract already exposes.
- Keep benchmark execution in `application/evaluation/`. Do not create `domain/evaluation/` metrics policies yet unless a very small pure policy becomes genuinely necessary for status bookkeeping in this story.

### File Structure Requirements

- Existing files to extend:
  - `src/codeman/application/evaluation/__init__.py`
  - `src/codeman/bootstrap.py`
  - `src/codeman/cli/eval.py`
  - `src/codeman/contracts/evaluation.py`
  - `src/codeman/contracts/errors.py`
  - `src/codeman/contracts/configuration.py`
  - `src/codeman/application/ports/artifact_store_port.py`
  - `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py`
  - `src/codeman/infrastructure/persistence/sqlite/tables.py`
  - `docs/cli-reference.md`
  - `docs/benchmarks.md`
- Likely new files for this story:
  - `src/codeman/application/evaluation/run_benchmark.py`
  - `src/codeman/application/ports/benchmark_run_store_port.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/benchmark_run_repository.py`
  - `migrations/versions/<timestamp>_create_benchmark_runs_table.py`
  - optionally `tests/unit/cli/test_eval.py` if it does not exist yet
- Likely tests to add or extend:
  - `tests/unit/application/test_run_benchmark.py`
  - `tests/unit/cli/test_eval.py`
  - `tests/unit/infrastructure/test_filesystem_artifact_store.py`
  - `tests/integration/persistence/test_benchmark_run_repository.py`
  - `tests/e2e/test_eval_benchmark.py`
  - targeted extensions to existing query/provenance tests if benchmark execution reuses shared helpers or workflow-type literals

### Testing Requirements

- Add unit tests that prove benchmark execution succeeds for the seeded mixed-stack golden dataset when the required retrieval baseline already exists for the selected mode.
- Add unit tests that prove Story 4.1 dataset failures surface unchanged through the benchmark command and do not leave misleading completed run rows or success artifacts.
- Add unit tests that prove lexical/semantic/hybrid baseline problems are mapped to benchmark-specific top-level failures with actionable mode/component details.
- Add unit tests for run finalization behavior:
  - preflight failure before execution starts
  - failure after some cases have executed
  - successful completion with deterministic case ordering
- Add CLI tests for text and JSON modes, including:
  - stable summary content
  - `stderr` progress messages
  - clean JSON `stdout`
  - stable failure envelopes and exit codes
- Add persistence tests for the benchmark run repository and artifact store seam, including deterministic artifact paths and truthful row round-trips.
- Add e2e tests that:
  - prepare the mixed-stack repository fixture
  - register, snapshot, extract, build chunks, and build the selected retrieval baseline
  - run `uv run codeman eval benchmark ...` in text mode and JSON mode
  - assert output contracts, progress behavior, and persisted benchmark artifacts
- Keep using workspace-local `.local/uv-cache` and temporary `CODEMAN_WORKSPACE_ROOT` for e2e isolation, following the current repo's established benchmark/test pattern. [Source: docs/project-context.md; tests/e2e/test_query_lexical.py; tests/e2e/test_compare_query_modes.py]

### Git Intelligence Summary

- Commit `147399b` (`story(4-1-define-the-golden-query-benchmark-dataset): complete code review and mark done`) is the immediate baseline. It added the dataset contracts, typed loader, seeded golden-query fixture, and benchmark policy docs that Story 4.2 must reuse rather than replace.
- Commit `c63fb6e` (`story(3-4): finalize run configuration provenance`) matters because benchmark execution should reuse the existing run-provenance pattern, migration style, and secret-safe configuration identity instead of inventing a second benchmark-only provenance mechanism.
- Commit `4d51962` (`story(3-5-reuse-prior-configurations-in-later-experiments): complete code review and mark done`) matters because Story 4.2 should lean on the existing root `--profile` workflow and stored profile lineage instead of creating benchmark-specific configuration reuse rules.
- Commit `8c0fb68` (`feat: add retrieval strategy profiles`) reinforces the repo's preference for deterministic canonical JSON payloads, additive DTO changes, SQLite persistence, and thin CLI wiring through `bootstrap.py`.
- Recent stories show a strong repo pattern: add one focused use case, wire it through `bootstrap.py`, update the matching CLI/docs, extend the nearest existing persistence/artifact seam, and mirror the change with unit, integration, and e2e coverage instead of broad rewrites.

### Latest Technical Information

- As of March 15, 2026, Typer's official docs still center nested command groups through separate `Typer()` apps wired with `app.add_typer(...)`. Inference: the benchmark command should live under the existing `eval` group in `src/codeman/cli/eval.py` and stay registered through `src/codeman/cli/app.py`, not through a new root CLI tree. [Source: https://typer.tiangolo.com/tutorial/subcommands/]
- As of March 15, 2026, Pydantic's official docs still document `ConfigDict` for strict boundary models and `model_validate_json()` for JSON payload validation. Inference: benchmark run DTOs and any JSON-backed artifact documents should stay strict and reuse JSON-mode validation instead of hand-rolled dictionary checks. [Source: https://docs.pydantic.dev/latest/api/config/#pydantic.config.ConfigDict; https://docs.pydantic.dev/latest/concepts/json/]
- As of March 15, 2026, Python's official `time` docs still recommend `perf_counter_ns()` when high-resolution monotonic timing is needed without float precision loss. Inference: if the benchmark harness records additional wall-clock timings beyond the query diagnostics returned by the retrieval use cases, it should use integer nanosecond timing and convert explicitly to contract-safe integers. [Source: https://docs.python.org/3/library/time.html#time.perf_counter_ns]
- SQLAlchemy 2.0 Core and Alembic official docs still center explicit table metadata plus migration operations for schema evolution. Inference: benchmark-run persistence should follow the existing SQLAlchemy Core table + Alembic migration path rather than ad hoc `sqlite3` DDL inside the new repository or use case. [Source: https://docs.sqlalchemy.org/en/20/core/metadata.html; https://alembic.sqlalchemy.org/en/latest/ops.html]

### Project Context Reference

- `docs/project-context.md` remains the canonical implementation ruleset: strict Pydantic models, thin CLI handlers, deterministic ordering, runtime-managed artifacts under `.codeman/`, and mirrored automated coverage for touched behavior.
- `docs/architecture/decisions.md` and `docs/architecture/patterns.md` require the CLI-first layered flow to remain intact: `cli -> application -> ports -> infrastructure -> contracts/config/runtime`.
- `docs/benchmarks.md` owns the human-facing benchmark and evaluation policy. Story 4.2 should update that doc honestly instead of copying evaluation policy into multiple places.
- No separate UX artifact exists for this project. For Story 4.2, the relevant UX requirement is operational clarity in the CLI: truthful progress on `stderr`, compact summary output, and machine-stable JSON contracts.

### Project Structure Notes

- The planning architecture mentions broader evaluation/reporting packages and later benchmark workflows, but the current implemented codebase only has `application/evaluation/` for dataset loading. Story 4.2 should add the smallest useful benchmark-execution subset there.
- The architecture and current code agree on the split metadata/artifact model. Story 4.2 should therefore store searchable run status in SQLite and raw benchmark evidence in generated artifacts, rather than putting everything in one store.
- Benchmark execution should reuse the existing query services and persistence seams. It should not bypass `bootstrap.py`, instantiate infrastructure directly in the CLI, or create a second parallel retrieval stack for evaluation.
- The current `eval` group is intentionally mounted but empty. Story 4.2 is the right place to turn it into a real execution surface, while keeping metrics, reports, comparisons, and regressions in later Epic 4 stories.

### References

- [Source: docs/project-context.md]
- [Source: docs/README.md]
- [Source: docs/benchmarks.md]
- [Source: docs/cli-reference.md]
- [Source: docs/architecture/decisions.md]
- [Source: docs/architecture/patterns.md]
- [Source: _bmad-output/planning-artifacts/epics.md - Epic 4; Story 4.1; Story 4.2; Story 4.3; Story 4.4; Story 4.5; Story 4.6]
- [Source: _bmad-output/planning-artifacts/prd.md - Executive Summary; Measurable Outcomes; MVP Scope; Journey Requirements Summary; FR19-FR23; NFR3-NFR4; NFR12-NFR23]
- [Source: _bmad-output/planning-artifacts/architecture.md - Evaluation and Benchmarking capability group; Data Architecture; Internal Communication Pattern; Output Contract; Requirements to Structure Mapping; Data Flow; Test Organization]
- [Source: _bmad-output/implementation-artifacts/4-1-define-the-golden-query-benchmark-dataset.md]
- [Source: _bmad-output/implementation-artifacts/3-4-record-configuration-provenance-for-every-run.md]
- [Source: _bmad-output/implementation-artifacts/3-5-reuse-prior-configurations-in-later-experiments.md]
- [Source: _bmad-output/implementation-artifacts/2-7-compare-retrieval-modes-for-the-same-question.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: src/codeman/cli/app.py]
- [Source: src/codeman/cli/eval.py]
- [Source: src/codeman/cli/common.py]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/contracts/evaluation.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: src/codeman/contracts/configuration.py]
- [Source: src/codeman/contracts/retrieval.py]
- [Source: src/codeman/application/evaluation/load_benchmark_dataset.py]
- [Source: src/codeman/application/query/run_lexical_query.py]
- [Source: src/codeman/application/query/run_semantic_query.py]
- [Source: src/codeman/application/query/run_hybrid_query.py]
- [Source: src/codeman/application/query/compare_retrieval_modes.py]
- [Source: src/codeman/application/provenance/record_run_provenance.py]
- [Source: src/codeman/application/ports/artifact_store_port.py]
- [Source: src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/tables.py]
- [Source: tests/unit/application/test_load_benchmark_dataset.py]
- [Source: tests/fixtures/queries/mixed_stack_fixture_golden_queries.json]
- [Source: tests/e2e/test_query_lexical.py]
- [Source: tests/e2e/test_compare_query_modes.py]
- [Source: git log --oneline -5]
- [Source: https://typer.tiangolo.com/tutorial/subcommands/]
- [Source: https://docs.pydantic.dev/latest/api/config/#pydantic.config.ConfigDict]
- [Source: https://docs.pydantic.dev/latest/concepts/json/]
- [Source: https://docs.python.org/3/library/time.html#time.perf_counter_ns]
- [Source: https://docs.sqlalchemy.org/en/20/core/metadata.html]
- [Source: https://alembic.sqlalchemy.org/en/latest/ops.html]

## Story Completion Status

- Status set to `done`.
- Completion note: `Story 4.2 is implemented, revalidated after code review fixes, and closed.`
- Recorded assumptions:
  - The first benchmark execution surface should be `eval benchmark` under the existing `eval` group, with one retrieval mode per invocation.
  - Raw benchmark artifacts should snapshot the normalized benchmark cases used at execution time so later metrics and reports remain reproducible even if the authored dataset changes afterward.
  - Benchmark command output should remain compact and artifact-oriented; detailed metrics, reports, run comparison, and regression analysis remain later Epic 4 stories.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Debug Log References

- 2026-03-15: Story context generated via the `bmad-create-story` workflow for backlog story `4-2-execute-a-benchmark-run-against-an-indexed-repository`.
- 2026-03-15: Loaded Epic 4, PRD, architecture, current benchmark policy/docs, Story 4.1 learnings, current eval/query/provenance code, and recent git history to derive benchmark-execution guardrails.
- 2026-03-15: Implemented benchmark execution orchestration, lifecycle persistence, CLI wiring, benchmark artifacts, provenance updates, and mirrored automated coverage for Story 4.2.
- 2026-03-15: Addressed post-review benchmark truthfulness gaps (pinned builds, interruption finalization, semantic/hybrid coverage) and revalidated the full regression suite (`320 passed`).

### Implementation Plan

- Add strict benchmark run DTOs, benchmark-specific error mapping, a SQLite-backed benchmark run store, and a filesystem-backed benchmark artifact seam that reuse the repo's current provenance and artifact patterns.
- Implement `run_benchmark.py` by composing the Story 4.1 dataset loader with exactly one selected retrieval use case per benchmark case, recording one outer provenance row and one benchmark run lifecycle.
- Expose `eval benchmark` under the existing `eval` group, update docs honestly, and mirror the workflow with unit, integration, and e2e coverage.

### Completion Notes List

- Added `eval benchmark` with truthful preflight validation, one-mode-per-run execution, benchmark lifecycle persistence, benchmark artifacts, and shared run-id provenance reuse.
- Extended benchmark/evaluation contracts, runtime artifact seams, SQLite metadata, and query build-selection controls so benchmark cases stay pinned to the preflight-resolved lexical/semantic baselines across long-running executions.
- Finalized interrupted benchmark runs truthfully by persisting `failed` status and failed artifacts for started runs instead of leaving orphaned `running` rows after `KeyboardInterrupt`/signal-driven interruption paths.
- Expanded unit and e2e coverage for semantic and hybrid benchmark execution, explicit build pinning, and hybrid no-nested-provenance dispatch behavior.
- Validated the change set with `ruff check .`, `ruff format --check` on all story-touched Python files, focused post-format benchmark regression coverage (`19 passed`), and the full repository test suite (`320 passed`).

### File List

- _bmad-output/implementation-artifacts/4-2-execute-a-benchmark-run-against-an-indexed-repository.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- docs/benchmarks.md
- docs/cli-reference.md
- migrations/versions/202603151500_create_benchmark_runs_table.py
- src/codeman/application/evaluation/__init__.py
- src/codeman/application/evaluation/run_benchmark.py
- src/codeman/application/ports/artifact_store_port.py
- src/codeman/application/ports/benchmark_run_store_port.py
- src/codeman/application/ports/index_build_store_port.py
- src/codeman/application/ports/semantic_index_build_store_port.py
- src/codeman/application/query/run_hybrid_query.py
- src/codeman/application/query/run_lexical_query.py
- src/codeman/application/query/run_semantic_query.py
- src/codeman/bootstrap.py
- src/codeman/cli/eval.py
- src/codeman/contracts/configuration.py
- src/codeman/contracts/errors.py
- src/codeman/contracts/evaluation.py
- src/codeman/contracts/retrieval.py
- src/codeman/infrastructure/artifacts/filesystem_artifact_store.py
- src/codeman/infrastructure/persistence/sqlite/repositories/benchmark_run_repository.py
- src/codeman/infrastructure/persistence/sqlite/repositories/index_build_repository.py
- src/codeman/infrastructure/persistence/sqlite/repositories/semantic_index_build_repository.py
- src/codeman/infrastructure/persistence/sqlite/tables.py
- tests/e2e/test_eval_benchmark.py
- tests/integration/persistence/test_benchmark_run_repository.py
- tests/unit/application/test_run_benchmark.py
- tests/unit/application/test_run_hybrid_query.py
- tests/unit/application/test_run_lexical_query.py
- tests/unit/application/test_run_semantic_query.py
- tests/unit/cli/test_eval.py
- tests/unit/infrastructure/test_filesystem_artifact_store.py

## Change Log

- `2026-03-15`: Created comprehensive ready-for-dev story context for benchmark execution against indexed repositories.
- `2026-03-15`: Implemented Story 4.2 with benchmark lifecycle persistence, raw benchmark artifacts, `eval benchmark` CLI execution, benchmark provenance wiring, doc updates, and mirrored automated coverage; status set to `review`.
- `2026-03-15`: Addressed code review follow-ups by pinning benchmark execution to preflight-resolved build ids, finalizing interrupted runs truthfully, expanding semantic/hybrid benchmark coverage, revalidating the full suite, and closing the story as `done`.
