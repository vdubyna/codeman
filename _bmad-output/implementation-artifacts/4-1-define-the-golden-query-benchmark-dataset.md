# Story 4.1: Define the Golden-Query Benchmark Dataset

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want codeman to use a structured golden-query benchmark dataset,
so that retrieval quality can be evaluated against repeatable expected scenarios.

## Acceptance Criteria

1. Given a benchmark dataset definition, when codeman loads it for evaluation, then each test case includes a stable query identity, query text, and expected relevance targets or judgments and the dataset format is validated before benchmark execution begins.
2. Given an invalid or incomplete benchmark dataset, when I start a benchmark run, then codeman fails with a clear validation error and does not produce misleading partial benchmark results.

## Tasks / Subtasks

- [x] Establish the canonical benchmark dataset contracts and validation rules. (AC: 1, 2)
  - [x] Add strict Pydantic DTOs under `src/codeman/contracts/evaluation.py` for a benchmark dataset document, benchmark query case, and benchmark relevance judgment/target locator.
  - [x] Require dataset-level identity metadata such as `dataset_id`, `dataset_version`, and `schema_version`, plus case-level `query_id` and `query_text`.
  - [x] Model query provenance with a narrow additive enum such as `human_authored` and `synthetic_reviewed` so the first baseline can be human-authored while future reviewed synthetic cases fit without breaking the schema.
  - [x] Normalize expected relevance to one canonical machine-readable shape with explicit integer relevance grades, so Story 4.3 can calculate Recall@K, MRR, and NDCG@K without another dataset migration.
  - [x] Anchor expected targets to stable repository-relative locators such as normalized `relative_path` plus optional 1-based line spans; do not use `chunk_id`, `source_file_id`, `snapshot_id`, or byte offsets as benchmark truth.

- [x] Add a reusable dataset load/validate seam for future benchmark execution. (AC: 1, 2)
  - [x] Add `src/codeman/application/evaluation/load_benchmark_dataset.py` with a focused use case or helper that loads an explicit dataset file path and returns a validated DTO plus a small summary.
  - [x] Support JSON input only for the MVP dataset artifact unless a concrete need appears during implementation; do not add a YAML dependency just for this story.
  - [x] Validate the filesystem path, JSON syntax, duplicate `query_id` values, blank query text, empty judgments, invalid path anchors, invalid line spans, and invalid relevance grades before any benchmark query execution can start.
  - [x] Produce deterministic dataset metadata useful for later stories, such as case counts and a canonical dataset fingerprint/content hash, without treating that fingerprint as a replacement for the explicit human-managed dataset version.
  - [x] Add typed dataset load/validation exceptions and stable error codes in `src/codeman/contracts/errors.py` so Story 4.2 can surface failures cleanly from the benchmark CLI.

- [x] Seed the first golden-query fixture and benchmark policy documentation. (AC: 1)
  - [x] Add `tests/fixtures/queries/` as the home for reusable benchmark input files.
  - [x] Create a minimal JSON dataset fixture for `tests/fixtures/repositories/mixed_stack_fixture` that covers at least the current PHP controller, JavaScript boot function, Twig template body block, and optionally the HTML fixture text.
  - [x] Keep the initial fixture intentionally small and human-authored; do not fabricate provider-generated synthetic cases in this story.
  - [x] Update `docs/benchmarks.md` with the implemented dataset schema concepts, versioning expectations, and an honest status note that benchmark orchestration itself still lands in Story 4.2.

- [x] Keep Story 4.1 scoped to dataset definition, not benchmark orchestration. (AC: 1, 2)
  - [x] Do not implement benchmark execution, metrics calculation, reports, run comparison, regression detection, judge workflows, or provider-backed synthetic-query generation in this story.
  - [x] Do not add a `benchmark_runs`/`evaluation_runs` persistence table or extend run-provenance workflow types yet; benchmark execution metadata belongs to Story 4.2 and later once a successful run actually exists.
  - [x] Keep benchmark datasets as authored input files outside `.codeman/`; runtime artifacts and reports remain future evaluation outputs under `.codeman/artifacts/`.
  - [x] Do not add a public `eval` benchmark command surface unless a tiny validation-only command becomes absolutely necessary; if a helper CLI is added, keep it under the existing `eval` Typer group and document it explicitly.

- [x] Add mirrored automated coverage for dataset correctness and failure behavior. (AC: 1, 2)
  - [x] Add unit tests for dataset DTO validation, canonical normalization, duplicate query detection, invalid path/line anchors, and source-kind validation.
  - [x] Add application-level tests for successful dataset loading, missing files, unsupported formats, invalid JSON, and incomplete benchmark cases.
  - [x] Add a fixture regression test proving the seeded dataset references real files/line spans in `tests/fixtures/repositories/mixed_stack_fixture`.
  - [x] Only add CLI unit/e2e coverage if a user-facing validation command is actually introduced; otherwise keep this story's tests focused on contracts and the application seam.

## Dev Notes

### Epic Context

- Epic 4 introduces evaluation and benchmarking as first-class product capabilities. Story 4.1 is the foundation layer that defines what "ground truth" looks like before any benchmark run, metrics record, or report can be trusted.
- Story 4.2 depends on this story's dataset loader and validation errors to fail fast before executing retrieval queries against an invalid benchmark input.
- Story 4.3 depends on this story choosing a judgment shape that can support Recall@K, MRR, and NDCG@K without reworking the dataset format later.
- Story 4.5 and Story 4.6 will depend on stable dataset identity/version semantics so benchmark comparisons and regression detection stay attributable across runs.

### Current Repo State

- `src/codeman/cli/eval.py` is still only a placeholder Typer group with no implemented commands.
- There is no `src/codeman/application/evaluation/` package, no benchmark dataset loader, and no `src/codeman/contracts/evaluation.py` contract module in the current codebase.
- `docs/benchmarks.md` explicitly says full benchmark orchestration is planned but not yet implemented, and it currently owns only policy-level guidance.
- `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py` persists snapshot manifests, chunk payloads, and embedding documents, but nothing yet for authored benchmark inputs.
- `src/codeman/contracts/errors.py` has no benchmark-dataset-specific error codes yet.
- `src/codeman/contracts/configuration.py` and the run-provenance store already capture secret-safe configuration identity, but the current `RunProvenanceWorkflowType` list does not include evaluation workflows yet.
- `tests/fixtures/` currently contains only the mixed-stack repository fixture; there is no `tests/fixtures/queries/` home for golden-query datasets yet.
- `compare query-modes` already compares retrieval behavior for a single query, but benchmark runs, metrics, reports, and regression workflows are not implemented yet.

### Cross-Story Baseline

- Current retrieval result packages already expose `relative_path`, `language`, `start_line`, and `end_line` on `RetrievalResultItem`. Benchmark judgments should align with those stable fields so later evaluation logic can match retrieved chunks without inventing a second locator vocabulary.
- Story 3.4, Story 3.5, and Story 3.6 established the repo's preferred pattern for repeatability: explicit identifiers, canonical JSON hashing, secret-safe persisted metadata, and additive DTO changes. Dataset identity should follow that pattern where useful instead of inventing an incompatible benchmark-specific identity scheme.
- `docs/benchmarks.md` already says benchmark baselines may contain both human-authored queries and reviewed synthetic queries. Story 4.1 should keep the first implementation local-first and human-authored by default while leaving room for reviewed synthetic cases later.
- Runtime-managed directories under `.codeman/` are for generated outputs, indexes, logs, caches, and metadata. Authored benchmark input files do not belong there yet.
- Story 5.1 and Story 5.2 will later standardize broader CLI surfaces and stable failure contracts, but Story 4.1 should already use the current typed-error pattern so Story 4.2 can plug benchmark validation into the CLI cleanly.

### Technical Guardrails

- Keep the implementation local-first and explicit. Do not send benchmark queries, repository content, or judgments to external providers in this story. [Source: docs/project-context.md; docs/benchmarks.md]
- Do not anchor benchmark truth to `chunk_id`, `source_file_id`, `snapshot_id`, or other snapshot-scoped identifiers. Those values are intentionally ephemeral across reindexing and chunk regeneration. [Source: src/codeman/contracts/chunking.py; src/codeman/contracts/retrieval.py]
- Prefer normalized repository-relative POSIX paths plus optional 1-based line spans for target locators. This keeps judgments human-reviewable and matchable against current retrieval outputs. [Source: src/codeman/contracts/retrieval.py]
- Keep dataset DTOs strict with `ConfigDict(extra="forbid")`, explicit fields, and deterministic serialization. Do not accept loose free-form dictionaries as the long-term internal shape. [Source: docs/project-context.md; src/codeman/contracts/common.py]
- Keep validation errors actionable but compact. Identify the dataset path, `query_id`, and offending field; do not dump full dataset contents or large code excerpts into operator-facing error messages by default. [Source: docs/project-context.md; docs/benchmarks.md]
- Do not add benchmark run persistence, report artifacts, or run-provenance workflow types yet. A successful evaluation run does not exist in the codebase until Story 4.2. [Source: docs/benchmarks.md; src/codeman/contracts/configuration.py]
- Do not add a YAML parser dependency just to author benchmark data. The current repo already leans on JSON artifacts, Pydantic JSON validation, and stdlib JSON tooling. [Source: pyproject.toml; src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- Keep any additive CLI surface under the existing `eval` group and preserve clean JSON `stdout` if you choose to expose validation publicly. [Source: src/codeman/cli/app.py; src/codeman/cli/eval.py; docs/project-context.md]

### Implementation Notes

- The architecture already reserves `contracts/evaluation.py` and `application/evaluation/` for benchmark-related work. Story 4.1 is the right time to add the smallest useful subset of that structure without jumping ahead to full benchmark execution.
- A practical canonical dataset shape for this story is:
  - dataset document: `schema_version`, `dataset_id`, `dataset_version`, optional `description`/`notes`, and `cases`
  - case: `query_id`, `query_text`, `source_kind`, optional `tags`, and `judgments`
  - judgment: `relative_path`, optional `language`, optional `start_line`/`end_line`, and `relevance_grade`
  Inference: this is enough to support repeatable retrieval evaluation now and metrics/reporting later without baking in unstable chunk IDs.
- Use one normalized judgments shape internally even if you later want an authoring shorthand. Binary relevance can be represented as `relevance_grade = 1`; stronger relevance can use higher grades for future NDCG support.
- Keep line-span anchors optional so file-level relevance can still be expressed, but when spans are present they should be validated as positive 1-based values with `end_line >= start_line`.
- The first fixture dataset should intentionally cover the existing mixed-stack repository:
  - `src/Controller/HomeController.php`
  - `assets/app.js`
  - `templates/page.html.twig`
  - optionally `public/index.html`
  Inference: this gives future benchmark runs real cross-language coverage without needing a large public corpus.
- Prefer JSON input plus `model_validate_json(...)` for the canonical load path. This matches the repo's existing artifact/document style and avoids a new parser dependency.
- If you compute a dataset fingerprint for future provenance, reuse the repo's canonical sorted JSON hashing pattern already used for retrieval profiles and effective configuration ids. Keep that fingerprint additive and do not treat it as a substitute for the human-managed `dataset_version`.
- If the implementation needs a filesystem seam for loading benchmark datasets, keep it extremely narrow. A small port + filesystem adapter is acceptable; a direct application loader is also acceptable if it stays testable and does not introduce duplicate path-validation logic all over the codebase.
- Do not create `domain/evaluation/` rules or benchmark metrics code unless a pure policy is genuinely needed for this story. Dataset definition and validation are the focus; metrics logic belongs to Story 4.3.

### File Structure Requirements

- Existing files to extend:
  - `src/codeman/contracts/errors.py`
  - `docs/benchmarks.md`
  - optionally `src/codeman/cli/eval.py` only if a tiny public validation command is added
- Likely new files for this story:
  - `src/codeman/contracts/evaluation.py`
  - `src/codeman/application/evaluation/__init__.py`
  - `src/codeman/application/evaluation/load_benchmark_dataset.py`
  - optionally `src/codeman/application/ports/benchmark_dataset_store_port.py`
  - optionally `src/codeman/infrastructure/evaluation/__init__.py`
  - optionally `src/codeman/infrastructure/evaluation/filesystem_benchmark_dataset_store.py`
  - `tests/fixtures/queries/mixed_stack_fixture_golden_queries.json`
- Likely tests to add or extend:
  - `tests/unit/application/test_load_benchmark_dataset.py`
  - `tests/unit/contracts/test_evaluation.py`
  - optionally `tests/integration/evaluation/test_filesystem_benchmark_dataset_store.py`
  - optionally `tests/unit/cli/test_eval.py` and one `tests/e2e/test_eval_validate_dataset.py` only if a public CLI validation surface is introduced

### Testing Requirements

- Add unit tests proving dataset documents reject:
  - duplicate `query_id` values
  - blank or whitespace-only query text
  - empty judgments
  - invalid `source_kind`
  - invalid line spans
  - invalid or out-of-range relevance grades
- Add application-level tests proving the loader:
  - loads a valid JSON dataset fixture successfully
  - fails clearly on a missing file path
  - fails clearly on an unsupported extension
  - fails clearly on invalid JSON
  - fails clearly on incomplete benchmark cases
- Add a regression test that validates the seeded mixed-stack dataset points at real repository fixture files and uses normalized relative paths.
- If a dataset fingerprint is produced, add a deterministic test proving semantically identical JSON yields the same fingerprint regardless of authoring key order.
- Do not require benchmark e2e runs in this story unless you deliberately add a public validation command. There is no benchmark execution workflow yet. [Source: docs/project-context.md; docs/benchmarks.md]

### Git Intelligence Summary

- Commit `c447863` (`story(3-6-key-caches-to-configuration-and-content-identity): complete code review and mark done`) is the most recent baseline. It reinforces the repo's preferred pattern: additive contracts, deterministic identities, honest docs updates, and mirrored tests rather than broad rewrites.
- Commit `4d51962` (`story(3-5-reuse-prior-configurations-in-later-experiments): complete code review and mark done`) matters because Story 4.1 should follow the same "canonical JSON + stable identity + additive DTO" approach for dataset metadata that later benchmark provenance can adopt.
- Commit `c63fb6e` (`story(3-4): finalize run configuration provenance`) matters because evaluation flows will eventually need to plug into the existing provenance model, not invent a second benchmark-only identity format.
- Commit `8c0fb68` (`feat: add retrieval strategy profiles`) matters because it established a small, deterministic hashing pattern from secret-safe JSON payloads. A dataset fingerprint helper can mirror that pattern without introducing a new serialization style.
- The recent run of Epic 3 stories shows the team is favoring bounded foundations first. Story 4.1 should do the same: define dataset truth and validation now, then let Story 4.2 and later stories build execution/reporting on top.

### Latest Technical Information

- As of March 15, 2026, Pydantic's latest official docs still center `ConfigDict` for strict models and recommend `model_validate_json()` / JSON-mode validation for JSON payloads. Inference: the benchmark dataset loader should validate the canonical JSON document through strict Pydantic models instead of hand-rolled dict checks. [Source: https://docs.pydantic.dev/latest/api/config/; https://docs.pydantic.dev/latest/concepts/models/; https://docs.pydantic.dev/latest/concepts/json/]
- Pydantic's current performance guidance still says `model_validate_json()` is generally preferable to `model_validate(json.loads(...))` when the incoming data is already JSON. Inference: Story 4.1 can keep the loader both simpler and faster by validating raw JSON text directly. [Source: https://docs.pydantic.dev/latest/concepts/performance/]
- Python 3.14.3's official `json` docs continue to document `json.load(...)`, `sort_keys=True`, and compact `separators=(',', ':')` for deterministic JSON serialization. Inference: JSON-only dataset input plus canonical sorted JSON hashing is the smallest stable choice for this story. [Source: https://docs.python.org/3/library/json.html]
- Typer's current official docs still center `app.add_typer(...)` for nested command groups. Inference: if a tiny validation command is exposed, it should live under the existing `eval` command tree rather than adding a new root CLI group. [Source: https://typer.tiangolo.com/tutorial/subcommands/add-typer/]

### Project Context Reference

- `docs/project-context.md` remains the canonical implementation ruleset: strict Pydantic boundary models, thin CLI handlers, deterministic behavior, runtime artifacts under `.codeman/`, and mirrored automated coverage for touched behavior.
- `docs/architecture/decisions.md` and `docs/architecture/patterns.md` require the CLI-first layered flow to remain intact: `cli -> application -> ports -> infrastructure -> contracts/config/runtime`.
- `docs/benchmarks.md` owns the human-facing benchmark and evaluation policy. Any implemented dataset baseline rules should be updated there instead of copied into multiple docs.
- No separate UX artifact exists for this project. For Story 4.1, the user-facing requirement is operational clarity and trustworthiness of evaluation inputs, not a new interactive interface.

### Project Structure Notes

- The planning architecture already names `contracts/evaluation.py`, `application/evaluation/`, and `tests/fixtures/queries/` as evaluation-aligned structure, but those pieces do not exist in the implemented code yet.
- Story 4.1 should introduce only the minimal subset needed for dataset truth and validation. The benchmark runner, metrics, reports, and comparisons should arrive in later Epic 4 stories instead of all at once.
- Current artifact storage under `.codeman/artifacts/` is only for generated outputs. Authored benchmark datasets belong in explicit filesystem paths and test fixtures, not copied into runtime output directories as a side effect of validation.
- `compare query-modes` already provides a comparison-oriented operator surface for a single query. Story 4.1 should not blur that with benchmark-run comparison semantics.

### References

- [Source: docs/project-context.md]
- [Source: docs/README.md]
- [Source: docs/benchmarks.md]
- [Source: docs/architecture/decisions.md]
- [Source: docs/architecture/patterns.md]
- [Source: _bmad-output/planning-artifacts/epics.md - Epic 4; Story 4.1; Story 4.2; Story 4.3]
- [Source: _bmad-output/planning-artifacts/prd.md - Measurable Outcomes; MVP Scope; Evaluation & Benchmarking FR19-FR28; NFR12-NFR23]
- [Source: _bmad-output/planning-artifacts/architecture.md - Evaluation and Benchmarking capability group; Data Architecture; Requirements to Structure Mapping; Test Organization]
- [Source: _bmad-output/planning-artifacts/implementation-readiness-report-2026-03-13.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: src/codeman/cli/app.py]
- [Source: src/codeman/cli/eval.py]
- [Source: src/codeman/runtime.py]
- [Source: src/codeman/contracts/common.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: src/codeman/contracts/chunking.py]
- [Source: src/codeman/contracts/retrieval.py]
- [Source: src/codeman/contracts/configuration.py]
- [Source: src/codeman/config/retrieval_profiles.py]
- [Source: src/codeman/config/provenance.py]
- [Source: src/codeman/application/ports/artifact_store_port.py]
- [Source: src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- [Source: tests/fixtures/repositories/mixed_stack_fixture/src/Controller/HomeController.php]
- [Source: tests/fixtures/repositories/mixed_stack_fixture/assets/app.js]
- [Source: tests/fixtures/repositories/mixed_stack_fixture/public/index.html]
- [Source: tests/fixtures/repositories/mixed_stack_fixture/templates/page.html.twig]
- [Source: git log --oneline -5]
- [Source: https://docs.pydantic.dev/latest/api/config/]
- [Source: https://docs.pydantic.dev/latest/concepts/models/]
- [Source: https://docs.pydantic.dev/latest/concepts/json/]
- [Source: https://docs.pydantic.dev/latest/concepts/performance/]
- [Source: https://docs.python.org/3/library/json.html]
- [Source: https://typer.tiangolo.com/tutorial/subcommands/add-typer/]

## Story Completion Status

- Status set to `done`.
- Completion note: `Implemented the benchmark dataset foundation, resolved the review follow-up fixes for Windows absolute paths and unbounded positive relevance grades, validated the story, and closed it.`
- Recorded assumptions:
  - The first implemented benchmark dataset format should be JSON, not YAML, because the current repo already standardizes on JSON artifacts and has no YAML dependency.
  - The initial golden dataset can be entirely human-authored, but the schema should still support `synthetic_reviewed` entries for later benchmark expansion.
  - Benchmark execution, persistence, metrics, and report generation are intentionally deferred to later Epic 4 stories after the dataset truth model exists.
  - A future benchmark run will persist dataset identity/version/fingerprint, but this story should only establish the reusable dataset contract and validation seam.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Implementation Plan

- Add strict benchmark dataset DTOs, deterministic canonical JSON hashing, and stable evaluation-specific error codes without exposing any benchmark CLI yet.
- Add a narrow JSON-only dataset loader with typed validation failures for path, syntax, duplicate query ids, invalid anchors, and invalid relevance grades.
- Seed a small human-authored mixed-stack dataset fixture, mirror the behavior with unit/application tests, and update `docs/benchmarks.md` to document the implemented schema boundaries honestly.

### Debug Log References

- 2026-03-15: Story context generated via the `bmad-create-story` workflow for backlog story `4-1-define-the-golden-query-benchmark-dataset`.
- `2026-03-15 12:10:00 +0200` Updated sprint tracking to `in-progress` and aligned the implementation plan with the story task order.
- `2026-03-15 12:18:00 +0200` Added strict benchmark dataset contracts with normalized POSIX locators, bounded relevance grades, source-kind provenance, and deterministic canonical hashing helpers.
- `2026-03-15 12:28:00 +0200` Added the JSON-only dataset loader, compact typed validation errors, and stable benchmark dataset error codes for future CLI integration.
- `2026-03-15 12:35:00 +0200` Seeded the mixed-stack golden-query fixture, updated benchmark policy docs, and validated the story with targeted tests, Ruff checks, and the full pytest suite.
- `2026-03-15 12:22:21 +0200` Resolved code review findings by rejecting Windows absolute benchmark locators, relaxing relevance grades to any positive integer, and rerunning the full regression suite before closure.

### Completion Notes

- Implemented strict benchmark dataset DTOs with required dataset/query identities, additive source provenance, normalized repository-relative path anchors, optional 1-based line spans, and canonical JSON fingerprint helpers.
- Added a narrow JSON-only `LoadBenchmarkDatasetUseCase` plus typed load/validation exceptions that report compact dataset-path, field, and `query_id` context without exposing dataset contents.
- Seeded a small human-authored mixed-stack benchmark fixture and updated `docs/benchmarks.md` to document the implemented schema, validation boundaries, and the honest Story 4.2 orchestration status.
- Resolved the post-review edge cases so Windows absolute paths are rejected as invalid locators and positive relevance grades remain future-proof for later metric work.
- Added mirrored contract/application tests, including fixture-anchor regression coverage, and validated the change set with `ruff check`, `ruff format --check`, and the full `pytest` suite (`302 passed`).

## File List

- _bmad-output/implementation-artifacts/4-1-define-the-golden-query-benchmark-dataset.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- docs/benchmarks.md
- src/codeman/application/evaluation/__init__.py
- src/codeman/application/evaluation/load_benchmark_dataset.py
- src/codeman/contracts/errors.py
- src/codeman/contracts/evaluation.py
- tests/fixtures/queries/mixed_stack_fixture_golden_queries.json
- tests/unit/application/test_load_benchmark_dataset.py
- tests/unit/contracts/test_evaluation.py

## Change Log

- `2026-03-15`: Implemented Story 4.1 with strict benchmark dataset contracts, a JSON-only benchmark dataset loader, stable validation error codes, a seeded mixed-stack golden-query fixture, benchmark policy documentation updates, and mirrored automated coverage.
- `2026-03-15`: Resolved code review findings for Windows absolute path rejection and positive unbounded relevance grades, reran validation, and marked the story done.
