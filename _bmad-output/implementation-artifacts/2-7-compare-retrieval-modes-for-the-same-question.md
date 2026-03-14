# Story 2.7: Compare Retrieval Modes for the Same Question

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want to compare lexical, semantic, and hybrid results for the same repository question,
so that I can judge which retrieval mode is most useful for a given task.

## Acceptance Criteria

1. Given the same repository question can be executed across multiple retrieval modes, when I request a comparison workflow, then codeman returns mode-specific result sets in a comparable structure, and makes it clear which results came from lexical, semantic, and hybrid retrieval respectively.
2. Given a retrieval mode comparison is complete, when I review the output, then I can inspect differences in ranking and relevance between modes without manually reconstructing the runs, and the comparison output remains attributable to the same repository state and configuration context.

## Tasks / Subtasks

- [x] Add retrieval-mode comparison contracts, typed errors, and a reusable hybrid-composition seam. (AC: 1, 2)
  - [x] Extend `src/codeman/contracts/retrieval.py` with additive DTOs such as `CompareRetrievalModesRequest`, `CompareRetrievalModesResult`, `RetrievalModeComparisonEntry`, `RetrievalModeRankAlignment`, and comparison-level diagnostics that reuse the existing retrieval item shape.
  - [x] Add stable compare-specific failure codes in `src/codeman/contracts/errors.py` plus typed application errors in a new comparison use case instead of surfacing raw lexical/semantic/hybrid failures as the top-level compare contract.
  - [x] Extract the smallest internal helper needed so hybrid results can be assembled from already-resolved lexical and semantic packages, avoiding duplicate lexical/semantic execution during one comparison run.

- [x] Implement a comparison use case in `src/codeman/application/query/` that composes the current retrieval flows without duplicating them. (AC: 1, 2)
  - [x] Add `src/codeman/application/query/compare_retrieval_modes.py` (or a similarly narrow module name) as the primary orchestration entrypoint for this story.
  - [x] Reuse the existing lexical and semantic query use cases plus the extracted hybrid helper, and keep the comparison pipeline artifact-only: do not rescan the repository, rebuild indexes, or reread mutable working-tree files during comparison.
  - [x] Enforce a single comparable repository and snapshot context across lexical, semantic, and hybrid entries; if any compared mode points to a different snapshot or repository state, fail with a clear compare-specific mismatch error.
  - [x] Build a deterministic alignment section keyed by `chunk_id` that shows where each chunk ranked in lexical, semantic, and hybrid outputs so users can inspect overlap and rank deltas without manual reconstruction.

- [x] Add the compare CLI surface and truthful text/JSON rendering. (AC: 1, 2)
  - [x] Implement `uv run codeman compare query-modes <repository-id> "<query>"` with the same `--query` escape hatch pattern used by `query lexical`, `query semantic`, and `query hybrid`.
  - [x] Wire the new use case through `src/codeman/bootstrap.py` and keep `src/codeman/cli/compare.py` thin: parse input, resolve the container, call one use case, and render either text or the standard JSON success/failure envelopes.
  - [x] Keep progress and operator diagnostics on `stderr`, while machine-readable comparison output stays on `stdout` only in JSON mode.
  - [x] In text mode, render shared repository/snapshot/query metadata, per-mode summary lines, a compact overlap or rank-delta section, and then clearly labeled lexical, semantic, and hybrid result blocks.

- [x] Update docs and add mirrored automated coverage. (AC: 1, 2)
  - [x] Update `docs/cli-reference.md` with the new `compare query-modes` command, text output expectations, JSON contract shape, and failure semantics.
  - [x] Add unit coverage for comparison ordering, alignment generation, same-snapshot enforcement, error mapping, and any helper extracted from hybrid orchestration.
  - [x] Add integration coverage proving the comparison is built from persisted artifacts only, fails on snapshot drift or missing component baselines, and succeeds again once the lexical and semantic baselines align for the latest snapshot.
  - [x] Add e2e coverage for `uv run codeman compare query-modes ...` in text and JSON modes, including `stdout`/`stderr` separation and clearly labeled mode-specific result sets.

## Dev Notes

### Previous Story Intelligence

- Story 2.6 already established the truthful hybrid-query baseline: deterministic fusion, same-snapshot enforcement, explicit component diagnostics, and clear failure behavior when one retrieval path is unavailable.
- Story 2.5 established the semantic-query baseline: current semantic-build lookup keyed to the active semantic configuration fingerprint, local-provider gating, provider/model attribution, and persisted-artifact-only result enrichment.
- Story 2.3 established the shared retrieval package and compact `RetrievalResultItem` shape. Story 2.7 should preserve that shared result-item contract instead of inventing a second per-mode item schema.
- Story 2.7 owns side-by-side mode comparison for the same question. It should not add benchmark comparison, run history comparison, or retrieval profile management; those belong to later epics.

### Current Repo State

- `src/codeman/cli/compare.py` is still a placeholder Typer group with no subcommands.
- `src/codeman/cli/app.py` already mounts the `compare` command group, so this story should extend that existing surface rather than creating a new root or moving the workflow under `query`.
- `src/codeman/application/query/` currently contains `run_lexical_query.py`, `run_semantic_query.py`, `run_hybrid_query.py`, `hybrid_fusion.py`, and `format_results.py`; there is no comparison orchestration module yet.
- The current codebase does not have an implemented `src/codeman/application/evaluation/` package, even though the planning architecture shows it as a future direction. For this story, `application/query/` is the nearest real extension point.
- `src/codeman/contracts/retrieval.py` already defines the stable package shapes for lexical, semantic, and hybrid retrieval, but it does not yet define a comparison DTO that can group those mode outputs under one attributable result.
- `src/codeman/contracts/errors.py` has lexical, semantic, hybrid, and indexing errors, but no compare-specific error codes yet.
- `docs/cli-reference.md` documents `query lexical`, `query semantic`, and `query hybrid`, but no `compare` subcommand yet.
- `src/codeman/cli/query.py` already contains reusable text-rendering patterns for result blocks and summary lines. If compare needs the same presentation helpers, extract the smallest neutral helper into `src/codeman/cli/common.py` instead of duplicating format logic.

### Technical Guardrails

- Keep the workflow CLI-first and local-first. Do not add HTTP routes, MCP transport, background workers, benchmark stores, or provider-backed evaluation features in this story. [Source: docs/architecture/decisions.md; docs/project-context.md]
- Extend the existing `compare` CLI group. Do not hide comparison behavior inside `query.py`, and do not create a second comparison entrypoint outside the root Typer tree. [Source: src/codeman/cli/app.py; docs/architecture/patterns.md]
- Keep the command thin: parse input, resolve `BootstrapContainer`, call one comparison use case, and render either text or JSON envelopes. [Source: docs/project-context.md; docs/architecture/patterns.md]
- Reuse the existing lexical, semantic, and hybrid retrieval behavior instead of re-implementing index lookups, provider initialization, artifact loading, or result-item enrichment in the compare flow. [Source: src/codeman/application/query/run_lexical_query.py; src/codeman/application/query/run_semantic_query.py; src/codeman/application/query/run_hybrid_query.py]
- Avoid double-running lexical and semantic retrieval inside one comparison request. Extract or add the smallest seam that lets the compare flow build a hybrid package from already-resolved lexical and semantic packages, so the same query run is compared once, not recomputed multiple times.
- Keep comparison output attributable to one repository state and configuration context. If lexical, semantic, or hybrid entries resolve different snapshots or repositories, fail clearly instead of presenting a misleading side-by-side comparison. [Source: _bmad-output/planning-artifacts/epics.md - Story 2.7; _bmad-output/planning-artifacts/prd.md - FR12, NFR15]
- Keep JSON output envelope-based, with machine-readable payloads on `stdout` and progress/diagnostics on `stderr`. [Source: docs/architecture/decisions.md; docs/project-context.md; src/codeman/cli/common.py]
- Keep DTOs strict with `ConfigDict(extra="forbid")`, and keep new use-case or helper classes as typed `@dataclass(slots=True)` structures to match the current codebase style. [Source: docs/project-context.md; src/codeman/bootstrap.py]
- Do not create benchmark comparison behavior, persisted compare artifacts, run manifests, configuration profiles, or MCP reuse hooks in this story. Epic 3 through Epic 5 own those surfaces later.
- Keep deterministic ordering everywhere: fixed mode order (`lexical`, `semantic`, `hybrid`), stable result ordering inside each mode, and stable alignment ordering for the cross-mode comparison section. [Source: docs/project-context.md]

### Implementation Notes

- Prefer a comparison result shape that shares `query`, `repository`, and `snapshot` context at the top level, then nests per-mode entries in stable order.
- Each per-mode entry should make the mode explicit and keep the existing retrieval package semantics: build metadata, diagnostics, and `RetrievalResultItem` results remain grouped under that mode instead of being flattened into one ambiguous list.
- Add an alignment section keyed by `chunk_id` so users can compare overlap and rank deltas directly. Include compact stable metadata such as `relative_path`, `language`, `strategy`, plus `lexical_rank`, `semantic_rank`, `hybrid_rank`, and optionally the corresponding scores when they help explain the delta.
- Use additive comparison DTOs rather than union-heavy or text-only output logic. The JSON contract should stay predictable for tests and future automation.
- Fail comparison strictly by default if one required mode is unavailable. If future stories want partial-success comparison behavior, keep it additive and explicit rather than silently degrading the compare workflow now.
- Keep the comparison orchestration inside `src/codeman/application/query/` because the current implemented codebase has retrieval orchestration there and does not yet have a real evaluation package to extend.
- Reuse the existing result-item content previews and explanations. The comparison workflow should make differences easier to inspect, not invent a third formatting path for retrieval results.

### File Structure Requirements

- Primary new implementation targets should be:
  - `src/codeman/application/query/compare_retrieval_modes.py`
  - `src/codeman/cli/compare.py`
  - `src/codeman/bootstrap.py`
  - `src/codeman/contracts/retrieval.py`
  - `src/codeman/contracts/errors.py`
  - `docs/cli-reference.md`
- Likely new or updated tests should include:
  - `tests/unit/application/test_compare_retrieval_modes.py`
  - `tests/unit/cli/test_compare.py`
  - `tests/integration/query/test_compare_retrieval_modes_integration.py`
  - `tests/e2e/test_compare_query_modes.py`
  - any existing hybrid unit tests if a helper is extracted from `run_hybrid_query.py`
- Do not create planned-but-not-yet-implemented packages just because the planning architecture listed them. Extend the nearest real module instead.

### Testing Requirements

- Add unit tests that prove lexical, semantic, and hybrid entries are emitted in stable order and that the alignment section is deterministic for the same input packages.
- Add unit tests for strict failure mapping when a required mode baseline is missing, unavailable, or resolves a different snapshot than the rest of the comparison.
- Add unit tests for option-like queries passed through `--query`, and for text/json rendering in `src/codeman/cli/compare.py`.
- Add integration tests proving comparison is built from persisted retrieval artifacts only and does not reread modified live repository files after indexing.
- Add integration tests covering snapshot drift after reindex: comparison should fail while lexical and semantic baselines refer to different snapshots, then succeed once both baselines are rebuilt for the latest snapshot.
- Add e2e tests for `uv run codeman compare query-modes ...` in text and JSON modes, asserting `stdout`/`stderr` separation, labeled mode sections, stable JSON envelope shape, and the presence of overlap or rank-delta data that makes differences inspectable without manual reconstruction.

### Git Intelligence Summary

- Recent retrieval work follows a tight additive pattern: extend one use case, wire it through `bootstrap.py`, update the matching CLI module, update `docs/cli-reference.md`, and add mirrored unit, integration, and e2e coverage instead of broad architectural rewrites.
- Commit `d8d9d5c` (`story(2-6-run-hybrid-retrieval-with-fused-ranking): complete code review and mark done`) matters because Story 2.7 should reuse the completed hybrid query behavior and its truthful diagnostics instead of re-implementing hybrid fusion in compare mode.
- Commit `5966a34` (`story(2-5-run-semantic-retrieval-queries): resolve review findings`) matters because compare mode must preserve semantic provider/model lineage, corruption handling, and current-configuration baseline lookup.
- Commit `c05aeea` (`story(2-4-build-semantic-retrieval-index-artifacts): complete code review and mark done`) matters because comparison should treat semantic builds as persisted attributed artifacts rather than as ad hoc query-time vectors.
- Commit `0f0f4c1` (`story(2-3-present-agent-friendly-ranked-retrieval-results): complete code review and mark done`) matters because Story 2.7 should preserve the shared retrieval package and human-readable result formatting expectations.
- Commit `79fb2de` (`docs: add agent context and update evaluation PRD`) matters because it refreshed the canonical project-context and architecture rules that now govern compare-mode implementation boundaries.

### Latest Technical Information

- Typer's current official subcommand guidance continues to use separate `Typer()` apps combined with `app.add_typer(...)` for nested command groups. Inference: Story 2.7 should extend `src/codeman/cli/compare.py` and keep the root registration in `src/codeman/cli/app.py` rather than inventing a separate command tree. [Source: https://typer.tiangolo.com/tutorial/subcommands/]
- Pydantic's current `ConfigDict` documentation still requires explicit `extra="forbid"` when strict boundary DTOs must reject unexpected fields. Inference: all new comparison DTOs should keep explicit forbid-mode models instead of relying on defaults. [Source: https://docs.pydantic.dev/latest/api/config/#pydantic.config.ConfigDict]
- Python's official `dataclasses` documentation continues to support `slots=True` for fixed-field dataclasses, with caveats around inherited slots and no-arg `super()`. Inference: new comparison use cases or tiny helpers should follow the current repo pattern of `@dataclass(slots=True)` and avoid clever inheritance-heavy structures. [Source: https://docs.python.org/3/library/dataclasses.html]
- The repository is already pinned to Python 3.13, Typer 0.20, and Pydantic 2.12 in local project rules. Inference: Story 2.7 should follow those repo-pinned versions and coding patterns rather than chasing upstream upgrades as part of this feature. [Source: docs/project-context.md]

### Project Context Reference

- `docs/project-context.md` is the canonical agent-facing implementation guide. It explicitly says to trust code and tests first, keep runtime artifacts under `.codeman/`, preserve deterministic ordering, and avoid treating planned surfaces such as MCP or placeholder command groups as already implemented.
- `docs/architecture/decisions.md` and `docs/architecture/patterns.md` define the stable CLI-first layering this story must preserve.
- No separate UX artifact exists for this project. For Story 2.7, the UX requirement is a clear CLI comparison experience with truthful output labeling and machine-stable JSON contracts.

### References

- [Source: docs/project-context.md]
- [Source: docs/README.md]
- [Source: docs/cli-reference.md]
- [Source: docs/architecture/decisions.md]
- [Source: docs/architecture/patterns.md]
- [Source: _bmad-output/planning-artifacts/epics.md - Epic 2; Story 2.3; Story 2.5; Story 2.6; Story 2.7]
- [Source: _bmad-output/planning-artifacts/prd.md - FR12; NFR15; NFR18; NFR20; NFR21; NFR22]
- [Source: _bmad-output/planning-artifacts/architecture.md - Naming Patterns; Project Structure & Boundaries; Requirements to Structure Mapping]
- [Source: _bmad-output/implementation-artifacts/2-6-run-hybrid-retrieval-with-fused-ranking.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: src/codeman/cli/app.py]
- [Source: src/codeman/cli/compare.py]
- [Source: src/codeman/cli/query.py]
- [Source: src/codeman/cli/common.py]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/contracts/retrieval.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: src/codeman/application/query/run_lexical_query.py]
- [Source: src/codeman/application/query/run_semantic_query.py]
- [Source: src/codeman/application/query/run_hybrid_query.py]
- [Source: tests/unit/cli/test_query.py]
- [Source: tests/integration/query/test_run_hybrid_query_integration.py]
- [Source: tests/e2e/test_query_hybrid.py]
- [Source: git log --oneline -5]
- [Source: https://typer.tiangolo.com/tutorial/subcommands/]
- [Source: https://docs.pydantic.dev/latest/api/config/#pydantic.config.ConfigDict]
- [Source: https://docs.python.org/3/library/dataclasses.html]

## Story Completion Status

- Status set to `ready-for-dev`.
- Completion note: `Ultimate context engine analysis completed - comprehensive developer guide created.`
- Recorded assumptions:
  - The compare CLI entrypoint should be `compare query-modes` under the existing `compare` group.
  - The first implementation should compare all three retrieval modes (`lexical`, `semantic`, `hybrid`) in one strict workflow instead of introducing optional mode-selection flags or partial-success behavior.
  - No separate UX design artifact exists, so CLI clarity and JSON contract stability are the relevant UX constraints for this story.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Debug Log References

- 2026-03-14: Story context generated via the `bmad-create-story` workflow for backlog story `2-7-compare-retrieval-modes-for-the-same-question`.
- 2026-03-14: Implemented the compare retrieval workflow, extracted a reusable hybrid composition seam, added compare CLI/docs/tests, and validated with `ruff check`, `ruff format --check`, and full `pytest` (`189 passed`).
- 2026-03-14: Fixed the review finding where alignment dropped hybrid ranks outside the displayed hybrid top-N window, revalidated compare coverage, and reran full `pytest` (`189 passed`).

### Implementation Plan

- Add strict comparison DTOs and compare-specific error mapping while preserving the existing retrieval item contract.
- Reuse lexical and semantic query use cases once, compose hybrid from those already-resolved packages, and build deterministic cross-mode rank alignment keyed by `chunk_id`.
- Expose the workflow under `compare query-modes`, reuse neutral CLI helpers for query parsing and result blocks, and mirror the behavior with unit, integration, e2e, and doc coverage.

### Completion Notes List

- Added `CompareRetrievalModesUseCase` plus strict comparison DTOs, compare-specific failure codes, and deterministic cross-mode alignment output keyed by `chunk_id`.
- Extracted `compose_hybrid_result_from_components(...)` so compare mode can build hybrid output from the already-resolved lexical and semantic packages without double-running those flows.
- Implemented `uv run codeman compare query-modes ...` with truthful text/JSON output, shared CLI helpers for query parsing/result blocks, and stable stderr/stdout separation.
- Updated the CLI reference and added mirrored coverage in unit, integration, and e2e layers, then validated the complete repository with `ruff check`, `ruff format --check`, and `UV_CACHE_DIR=.local/uv-cache uv run --group dev pytest` (`189 passed`).
- Addressed the code review finding by sourcing hybrid alignment ranks from the full fused hybrid result set instead of only the displayed hybrid top-N block, which keeps rank deltas and overlap counts truthful for compared chunks that fall below the hybrid display cutoff.

### File List

- _bmad-output/implementation-artifacts/2-7-compare-retrieval-modes-for-the-same-question.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- docs/cli-reference.md
- src/codeman/application/query/compare_retrieval_modes.py
- src/codeman/application/query/run_hybrid_query.py
- src/codeman/bootstrap.py
- src/codeman/cli/common.py
- src/codeman/cli/compare.py
- src/codeman/cli/query.py
- src/codeman/contracts/errors.py
- src/codeman/contracts/retrieval.py
- tests/e2e/test_compare_query_modes.py
- tests/integration/query/test_compare_retrieval_modes_integration.py
- tests/unit/application/test_compare_retrieval_modes.py
- tests/unit/application/test_run_hybrid_query.py
- tests/unit/cli/test_compare.py

## Change Log

- 2026-03-14: Created comprehensive ready-for-dev story context for retrieval-mode comparison.
- 2026-03-14: Implemented retrieval-mode comparison across lexical, semantic, and hybrid workflows; updated CLI/docs; added mirrored automated coverage; and validated the full suite for review.
- 2026-03-14: Fixed the compare alignment/hybrid-rank review finding, revalidated story 2.7 against acceptance criteria, and marked the story done.
