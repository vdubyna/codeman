# Story 3.5: Reuse Prior Configurations in Later Experiments

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a maintainer,
I want to rerun workflows using previously defined configurations,
so that experiments are repeatable and easier to compare over time.

## Acceptance Criteria

1. Given a previously saved configuration profile, when I launch a new indexing, query, or evaluation workflow with that profile, then codeman uses the saved configuration as the basis for the run and records that the workflow reused an existing configuration identity.
2. Given I override part of a reused configuration at runtime, when the run starts, then codeman records both the base profile identity and the effective resolved configuration and makes it clear that the run is a modified reuse rather than an untouched replay.

## Tasks / Subtasks

- [x] Add a first-class configuration-reuse lineage model and reuse-state classifier. (AC: 1, 2)
  - [x] Add additive DTO(s) for base-profile lineage under `src/codeman/contracts/configuration.py` and reuse them from both `config show` and persisted run provenance. Prefer an explicit machine-readable enum/literal such as `ad_hoc`, `profile_reuse`, and `modified_profile_reuse` over loosely related booleans.
  - [x] Derive reuse state from the resolved `RetrievalStrategyProfileRecord` selected in bootstrap plus the effective secret-safe payload already produced for Story 3.4. If the selected profile `profile_id` matches the effective `configuration_id`, treat the run as an untouched replay; otherwise treat it as modified reuse.
  - [x] Keep identity computation single-sourced by reusing Story 3.3's canonical profile hashing and Story 3.4's effective-configuration hashing rather than introducing a third canonicalization path.
  - [x] Keep runs with no selected profile truthful by recording no base-profile identity and a non-profile reuse state.

- [x] Persist base-profile reuse lineage in successful run provenance and operator inspection surfaces. (AC: 1, 2)
  - [x] Extend the run-provenance schema, DTOs, and repository mapping with nullable summary fields such as `base_profile_id`, `base_profile_name`, and `reuse_kind`, while preserving the existing `configuration_id` as the effective configuration that actually executed.
  - [x] Update `RecordRunConfigurationProvenanceUseCase` so it receives `selected_profile` context from `bootstrap.py` rather than trying to reconstruct base-profile lineage later from CLI flags or database joins.
  - [x] Keep cross-workflow reuse metadata separate from `workflow_context`; workflow context should stay focused on workflow-specific references such as build ids, compared modes, and max-results settings.
  - [x] Update `config provenance show <run-id>` text and JSON output to expose the base profile identity, effective configuration identity, and explicit reuse state without leaking secrets.

- [x] Make reused configurations govern current implemented workflows truthfully, including lexical baselines. (AC: 1)
  - [x] Keep indexing flows (`index build-chunks`, `index build-lexical`, `index build-semantic`, `index reindex`) on the shared resolved-config path so a selected profile still acts as the base layer before CLI and environment overrides.
  - [x] Tighten lexical-query baseline resolution to the current effective indexing fingerprint instead of "latest build for repository". Add or extend the store API so `query lexical` resolves the latest build for the latest eligible snapshot and the current indexing fingerprint, then fails with a stable baseline-missing error when no matching build exists.
  - [x] Let `query hybrid` and `compare query-modes` inherit the corrected lexical-baseline behavior through `RunLexicalQueryUseCase`; do not duplicate lexical selection logic in composed workflows.
  - [x] Do not implement evaluation commands in this story. `src/codeman/cli/eval.py` is still a placeholder; add only the additive reuse and provenance seams that future evaluation workflows can adopt later.

- [x] Surface modified-vs-unmodified reuse clearly before and after runs. (AC: 1, 2)
  - [x] Extend `config show` metadata to expose the selected base profile, effective `configuration_id`, and whether the current invocation is an untouched profile replay or a modified reuse.
  - [x] Keep successful build/query/compare result contracts additive. Existing `run_id` fields remain the minimal inline hook; operators can inspect full reuse lineage through `config provenance show` instead of duplicating the entire provenance payload in every workflow result.
  - [x] Update human-readable baseline error messages so "current configuration" is explicit whenever a selected profile points to a fingerprint that has no matching lexical or semantic build yet.

- [x] Update docs and add mirrored automated coverage. (AC: 1, 2)
  - [x] Update `docs/cli-reference.md` for reuse-state semantics, selected-profile preview behavior in `config show`, provenance inspection fields, and config-scoped lexical/hybrid/compare baseline behavior.
  - [x] Add unit tests for reuse-state classification, effective-vs-base profile matching, and secret-safe serialization of reuse metadata.
  - [x] Add persistence and integration tests for the extended run-provenance schema and the lexical-build lookup semantics keyed by indexing fingerprint.
  - [x] Add e2e coverage for exact profile replay, modified reuse via CLI or environment override, provenance inspection of both cases, and lexical/hybrid/compare failure until a matching baseline exists for the selected profile.

## Dev Notes

### Epic Context

- Epic 3 is the configuration and provenance foundation for repeatable experiments. Story 3.5 is where Story 3.3's saved profile identity and Story 3.4's effective run-provenance identity become explicit reuse lineage.
- Story 3.6 owns cache-key correctness and stale-artifact prevention. Story 3.5 should stop at truthful config reuse, baseline selection, and provenance rather than pulling cache invalidation policy forward.
- The planning docs drift slightly on FR numbering: `epics.md` maps this story to `FR17`, while `prd.md` shifts configuration reuse to `FR18`. Use this story's acceptance criteria and Epic 3 ordering as the implementation source of truth.
- The acceptance criteria mention evaluation workflows, but the current codebase still exposes only a placeholder `eval` command group. Build additive reuse/provenance seams that future eval commands can call later; do not invent benchmark execution behavior now.

### Current Repo State

- `src/codeman/bootstrap.py` already resolves `--profile`, loads the selected `RetrievalStrategyProfileRecord`, and stores it on the shared container before the final config load.
- `src/codeman/application/provenance/record_run_provenance.py` currently records only the effective configuration identity; it has no visibility into the selected base profile or whether CLI/environment overrides changed that base profile.
- `src/codeman/contracts/configuration.py` and `src/codeman/infrastructure/persistence/sqlite/tables.py` currently have no first-class base-profile lineage or reuse-state fields in run provenance.
- `src/codeman/cli/config.py` already exposes `selected_profile` metadata in `config show`, but it does not tell the operator whether the current invocation is an untouched profile replay or a modified reuse, and it does not surface the effective `configuration_id`.
- `src/codeman/application/query/run_lexical_query.py` still uses `get_latest_build_for_repository(...)` and ignores the current indexing fingerprint. That was acceptable before profile-driven repeatability mattered, but it is now a truthfulness gap for lexical, hybrid, and compare workflows under `--profile`.
- `src/codeman/application/query/run_semantic_query.py` already resolves the current semantic fingerprint and fails when no matching baseline exists. Story 3.5 should bring lexical-path truthfulness closer to that standard rather than keeping a latest-build shortcut.
- `src/codeman/cli/eval.py` remains a placeholder Typer group with no implemented evaluation workflows yet.

### Previous Story Intelligence

- Story 3.4 established the secret-safe effective configuration payload, the stable effective `configuration_id`, the run-provenance store, and `config provenance show <run-id>`. Story 3.5 should extend that foundation instead of creating a second run-attribution mechanism.
- Story 3.3 established the stable `profile_id`, the selected-profile config layer, and workspace-local persistence for saved retrieval profiles. A saved profile's identity should remain the base configuration identity recorded for reuse lineage.
- Story 3.2 separated provider-owned settings from `semantic_indexing` and hardened secret handling. Reuse lineage may expose provider/model metadata, but it must never persist or print raw provider secrets.
- Story 2.7 proved that hybrid and compare workflows here are compositions of the lexical and semantic use cases. Any lexical baseline fix for profile reuse should land in the shared lexical path and flow through composed workflows automatically.
- Story 1.6 and Story 2.1 already treat indexing fingerprints as real lineage signals on snapshots, reindex runs, and lexical builds. Story 3.5 should reuse those fingerprints instead of inventing ad hoc lexical build selection rules.

### Cross-Story Baseline

- `load_app_config(...)` remains the authoritative configuration-resolution path. Reuse state must be computed from the resolved selected profile plus the final effective config, not from ad hoc environment reads inside CLI handlers or query/index use cases.
- An untouched profile replay should naturally produce `base_profile_id == configuration_id`. Modified reuse should preserve the same `base_profile_id` but a different effective `configuration_id`.
- `workflow_context` is intentionally workflow-specific. Base-profile lineage is cross-workflow provenance and should be modeled explicitly rather than hidden inside generic JSON blobs.
- `SuccessEnvelope.meta` remains intentionally small and command-oriented. Reuse lineage belongs inside `data`, not in the envelope metadata.
- Future evaluation workflows should reuse the same provenance and reuse-lineage model rather than introducing a parallel "eval config ancestry" format.

### Technical Guardrails

- Keep the implementation CLI-first and local-first. Do not add HTTP surfaces, MCP runtime behavior, remote profile registries, or new evaluation commands in this story. [Source: docs/project-context.md; docs/architecture/decisions.md; src/codeman/cli/eval.py]
- Derive reuse state from the selected profile record plus the effective secret-safe payload, not from raw CLI args, raw environment dumps, or hand-built dictionaries. [Source: src/codeman/bootstrap.py; src/codeman/config/retrieval_profiles.py; src/codeman/config/provenance.py]
- Never persist or print raw provider secrets, workspace-root overrides, or other non-retrieval operator state as part of base-profile lineage. Provider identity and non-secret model metadata may remain visible. [Source: docs/project-context.md; _bmad-output/implementation-artifacts/3-2-configure-embedding-providers-independently.md; _bmad-output/implementation-artifacts/3-4-record-configuration-provenance-for-every-run.md]
- When a selected profile changes indexing settings, lexical query, hybrid query, and compare must not silently fall back to an unmatched lexical build. Missing baselines should fail with stable, actionable errors rather than pretending the experiment is repeatable. [Source: src/codeman/application/query/run_lexical_query.py; src/codeman/application/query/run_hybrid_query.py; src/codeman/application/query/compare_retrieval_modes.py]
- Keep identity generation deterministic by serializing through strict Pydantic models in JSON mode and canonical sorted JSON. Do not hash `repr(...)`, unsorted dicts, or mutable SQLite rows directly. [Source: src/codeman/config/retrieval_profiles.py; src/codeman/config/provenance.py; https://docs.pydantic.dev/latest/concepts/serialization/; https://docs.python.org/3/library/json.html]
- Prefer additive schema and contract changes. Existing `run_id` result fields, CLI JSON envelopes, and provenance lookup behavior should remain backward-compatible for current tests and automation. [Source: docs/project-context.md; docs/cli-reference.md; src/codeman/contracts/configuration.py; src/codeman/contracts/retrieval.py]
- Keep all mutable reuse/provenance state in the runtime SQLite database under `.codeman/`; do not write new mutable experiment state into `pyproject.toml`, committed docs, or indexed target repositories. [Source: docs/project-context.md; docs/architecture/patterns.md; _bmad-output/implementation-artifacts/3-3-create-reusable-retrieval-strategy-profiles.md]
- Do not auto-rebuild missing baselines during query commands just because a profile was selected. Query workflows should remain truthful read operations that either find the matching baseline or fail clearly. [Inference from current query command contracts and Epic 3 repeatability requirements]

### Implementation Notes

- A practical additive reuse-lineage shape is a dedicated nested contract such as `ConfigurationReuseLineage` with:
  - `reuse_kind`
  - `base_profile_id`
  - `base_profile_name`
  - optional operator-facing `effective_configuration_id` where it improves CLI preview surfaces
  Inference: this keeps reuse semantics reusable between `config show` and run provenance without overloading unrelated workflow-specific DTOs.
- For persisted run provenance, summary columns such as `base_profile_id`, `base_profile_name`, and `reuse_kind` are worth storing directly alongside the existing top-level provenance fields. Inference: they keep repository-scoped provenance queryable and stable without reopening JSON payloads just to answer basic lineage questions.
- `RecordRunConfigurationProvenanceUseCase` is the right central place to attach reuse lineage, but it needs the selected profile injected from bootstrap. Prefer constructor-time dependency (`selected_profile: RetrievalStrategyProfileRecord | None`) or an equivalent explicit request field instead of a hidden global lookup.
- Reuse the existing effective configuration payload for lineage comparison. If `selected_profile.profile_id == build_effective_config_provenance_id(effective_payload)`, the run is an untouched replay; otherwise it is modified reuse and must record both identities.
- `config show` should reuse the same helper used by run provenance so preview semantics match persisted run semantics exactly. Avoid reimplementing the comparison logic separately in CLI formatting code.
- Lexical baseline resolution likely needs a new repository/store method such as "latest lexical build for repository + current snapshot + indexing fingerprint". Keep that logic inside the store/use-case seam, not in CLI handlers.
- Update lexical baseline error copy to mirror semantic truthfulness: "current configuration" should mean the selected profile plus any explicit overrides after layering, not merely "latest build in the database".
- Hybrid and compare provenance should continue to record component build ids and compared modes as they do today; the new reuse lineage should sit alongside that information rather than replacing it.
- Future `eval` workflows should be able to call the same run-provenance use case with the same reuse-lineage model once real evaluation commands exist. Do not invent eval-specific reuse terminology in this story.

### File Structure Requirements

- Existing files to extend:
  - `src/codeman/bootstrap.py`
  - `src/codeman/cli/config.py`
  - `src/codeman/config/provenance.py`
  - `src/codeman/contracts/configuration.py`
  - `src/codeman/application/provenance/record_run_provenance.py`
  - `src/codeman/application/provenance/show_run_provenance.py`
  - `src/codeman/application/query/run_lexical_query.py`
  - `src/codeman/application/query/run_hybrid_query.py`
  - `src/codeman/application/query/compare_retrieval_modes.py`
  - `src/codeman/application/ports/index_build_store_port.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/index_build_repository.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/run_provenance_repository.py`
  - `src/codeman/infrastructure/persistence/sqlite/tables.py`
  - `docs/cli-reference.md`
- Likely new files for this story:
  - `src/codeman/config/configuration_reuse.py`
  - `migrations/versions/<timestamp>_add_profile_reuse_lineage_to_run_provenance.py`
- Likely tests to add or extend:
  - `tests/unit/config/test_configuration_reuse.py`
  - `tests/unit/config/test_provenance.py`
  - `tests/unit/cli/test_config.py`
  - `tests/unit/application/test_record_run_provenance.py`
  - `tests/unit/application/test_run_lexical_query.py`
  - `tests/unit/application/test_run_hybrid_query.py`
  - `tests/unit/application/test_compare_retrieval_modes.py`
  - `tests/integration/persistence/test_run_provenance_repository.py`
  - `tests/integration/indexing/test_build_lexical_index_integration.py`
  - `tests/e2e/test_run_provenance.py`
  - `tests/e2e/test_config_profiles.py`
  - `tests/e2e/test_query_lexical.py`
  - `tests/e2e/test_compare_query_modes.py`

### Testing Requirements

- Add unit tests for reuse-lineage classification covering:
  - no selected profile -> `ad_hoc`
  - selected profile with matching effective config -> untouched profile reuse
  - selected profile with CLI or environment overrides that change effective config -> modified reuse
- Add unit tests proving `config show --profile ...` surfaces the same base-profile and effective-config relationship that run provenance persists after a successful run.
- Add persistence tests for the extended run-provenance table, including migration bootstrap, round-trip loading of the new reuse fields, and deterministic repository-scoped ordering.
- Add unit/integration tests for the lexical-build lookup keyed by indexing fingerprint so profile-driven lexical, hybrid, and compare queries fail when no matching lexical baseline exists and succeed once the matching baseline is built.
- Add e2e coverage showing:
  - an exact profile replay records `base_profile_id == configuration_id`
  - a modified reuse keeps the same `base_profile_id` but records a different effective `configuration_id`
  - `config provenance show` makes the difference explicit in both text and JSON modes
  - profile-driven lexical, hybrid, and compare workflows do not silently reuse unmatched lexical baselines
- Keep using `CliRunner` for CLI unit tests and `subprocess.run(..., check=False)` with temporary workspaces for e2e execution. Continue using workspace-local `.local/uv-cache` when `uv` is invoked. [Source: docs/project-context.md]

### Git Intelligence Summary

- Commit `c63fb6e` (`story(3-4): finalize run configuration provenance`) is the immediate baseline. It shows the repo's preferred pattern for extending provenance: additive schema changes, one central provenance use case, thin CLI inspection, and mirrored unit/integration/e2e coverage.
- Commit `8c0fb68` (`feat: add retrieval strategy profiles`) matters because it already centralized profile selection in bootstrap and `config` CLI commands. Story 3.5 should extend that seam rather than adding per-command profile ancestry logic.
- Commit `91fd05e` (`story(3-2): configure embedding providers independently`) reinforces two critical guardrails: provider-owned settings stay separate from semantic workflow settings, and every operator-visible or persisted config surface must remain secret-safe.
- Commit `a37f5b6` (`story(3-1-define-the-layered-configuration-model): complete code review and mark done`) established the authoritative layer order. Story 3.5 should preserve that precedence and only add reuse interpretation on top of the resolved result.
- Commit `5c8304a` (`story(2-7-compare-retrieval-modes-for-the-same-question): complete code review and mark done`) matters because it shows how composed workflows are handled here: fix shared underlying seams and let hybrid/compare inherit the change instead of duplicating logic.

### Latest Technical Information

- As of March 15, 2026, Pydantic's latest official docs still use `ConfigDict` for strict model behavior and document `model_dump(mode='json')` / JSON mode serialization for JSON-compatible payloads. Inference: reuse lineage and effective-config identity should stay on strict Pydantic DTOs and JSON-mode dumps before hashing or persistence. [Source: https://docs.pydantic.dev/latest/api/config/; https://docs.pydantic.dev/latest/concepts/serialization/]
- Python 3.14.3's standard-library `json` docs still document `sort_keys=True` and compact separators for deterministic JSON output. Inference: stable configuration and reuse identities should keep using sorted-key canonical JSON rather than unordered dumps. [Source: https://docs.python.org/3/library/json.html]
- Typer's official subcommands docs still center `app.add_typer(...)` for nested command groups. Inference: any additive reuse inspection or preview surface should stay under the existing `config` tree instead of creating a new root command group. [Source: https://typer.tiangolo.com/tutorial/subcommands/add-typer/]
- SQLAlchemy 2.0 Core metadata docs and Alembic's latest ops docs continue to center `MetaData`, `Table`, `Column`, and migration operations such as `create_table()`. Inference: extend runtime SQLite schema through the existing SQLAlchemy Core plus Alembic path rather than ad hoc `sqlite3` DDL inside repositories or CLI code. [Source: https://docs.sqlalchemy.org/en/20/core/metadata.html; https://alembic.sqlalchemy.org/en/latest/ops.html]
- The project remains pinned to the versions documented in `docs/project-context.md` and the existing dependency constraints. This story should preserve those pins and use current patterns without bundling unrelated library upgrades. [Source: docs/project-context.md]

### Project Context Reference

- `docs/project-context.md` remains the canonical implementation ruleset: strict Pydantic boundary models, thin CLI handlers, deterministic behavior, runtime artifacts under `.codeman/`, and mirrored automated coverage for touched behavior.
- `docs/architecture/decisions.md` and `docs/architecture/patterns.md` require the CLI-first layered flow to remain intact: `cli -> application -> ports -> infrastructure -> contracts/config/runtime`.
- `docs/cli-reference.md` owns the supported CLI contract and must be updated whenever selected-profile reuse semantics or baseline behavior changes.
- No separate UX artifact exists for this project. For Story 3.5, the user-facing requirement is operational clarity: a maintainer must be able to tell whether a run was an exact profile replay or a modified reuse without exposing secrets or reverse-engineering config layers.

### Project Structure Notes

- The planning architecture mentions broader diagnostics and evaluation packages that do not yet exist in the implementation. Story 3.5 should add only the minimal reuse-lineage and lexical-baseline seams needed for current workflows.
- `RunProvenanceWorkflowContext` already stores workflow-specific build references cleanly. Base-profile lineage should be modeled explicitly rather than squeezed into that workflow-context JSON as pseudo-build metadata.
- Current result DTOs already expose `run_id` for the workflows that persist provenance. Use that seam for operator inspection instead of embedding full provenance payloads into every successful workflow response.
- Lexical baseline selection belongs in the lexical query store/use-case boundary, not in CLI handlers or config-formatting helpers. The composed hybrid/compare paths should inherit that behavior from the shared lexical query use case.

### References

- [Source: docs/project-context.md]
- [Source: docs/README.md]
- [Source: docs/cli-reference.md - Index Commands; Query Commands; Config Commands]
- [Source: docs/architecture/decisions.md]
- [Source: docs/architecture/patterns.md]
- [Source: _bmad-output/planning-artifacts/epics.md - Epic 3; Story 3.5; Story 3.6]
- [Source: _bmad-output/planning-artifacts/prd.md - Journey 4; repeatability and experiment-control requirements]
- [Source: _bmad-output/planning-artifacts/architecture.md - Environment Configuration; Architectural Boundaries; Requirements to Structure Mapping]
- [Source: _bmad-output/implementation-artifacts/3-3-create-reusable-retrieval-strategy-profiles.md]
- [Source: _bmad-output/implementation-artifacts/3-4-record-configuration-provenance-for-every-run.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/cli/app.py]
- [Source: src/codeman/cli/config.py]
- [Source: src/codeman/cli/eval.py]
- [Source: src/codeman/config/loader.py]
- [Source: src/codeman/config/retrieval_profiles.py]
- [Source: src/codeman/config/provenance.py]
- [Source: src/codeman/contracts/configuration.py]
- [Source: src/codeman/application/provenance/record_run_provenance.py]
- [Source: src/codeman/application/query/run_lexical_query.py]
- [Source: src/codeman/application/query/run_semantic_query.py]
- [Source: src/codeman/application/query/run_hybrid_query.py]
- [Source: src/codeman/application/query/compare_retrieval_modes.py]
- [Source: src/codeman/application/ports/index_build_store_port.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/index_build_repository.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/run_provenance_repository.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/tables.py]
- [Source: tests/e2e/test_config_profiles.py]
- [Source: tests/e2e/test_run_provenance.py]
- [Source: git log --oneline -5]
- [Source: git show --stat --summary c63fb6e]
- [Source: git show --stat --summary 8c0fb68]
- [Source: git show --stat --summary 91fd05e]
- [Source: git show --stat --summary a37f5b6]
- [Source: git show --stat --summary 5c8304a]
- [Source: https://docs.pydantic.dev/latest/api/config/]
- [Source: https://docs.pydantic.dev/latest/concepts/serialization/]
- [Source: https://docs.python.org/3/library/json.html]
- [Source: https://typer.tiangolo.com/tutorial/subcommands/add-typer/]
- [Source: https://docs.sqlalchemy.org/en/20/core/metadata.html]
- [Source: https://alembic.sqlalchemy.org/en/latest/ops.html]

## Story Completion Status

- Status set to `ready-for-dev`.
- Completion note: `Ultimate context engine analysis completed - comprehensive developer guide created.`
- Recorded assumptions:
  - A saved profile's `profile_id` remains the base configuration identity recorded for reuse lineage.
  - Profile-driven repeatability requires lexical query, hybrid query, and compare to stop selecting an arbitrary latest lexical build and instead honor the current effective indexing fingerprint.
  - Evaluation workflows remain future-facing in this story and should receive only additive provenance/reuse seams, not new command implementations.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Implementation Plan

- Introduce a reusable `ConfigurationReuseLineage` contract plus a shared helper that derives `ad_hoc`, `profile_reuse`, and `modified_profile_reuse` from the selected profile and effective secret-safe config payload.
- Thread selected-profile context from `bootstrap.py` into run provenance, persist additive reuse summary columns, and expose the same lineage in `config show` and `config provenance show`.
- Tighten lexical baseline lookup to the latest eligible snapshot plus current indexing fingerprint so lexical, hybrid, and compare workflows all fail truthfully when profile-driven baselines drift.
- Mirror the behavior with unit, integration, and e2e coverage; then validate with `ruff check` and the full `pytest` suite.

### Debug Log References

- 2026-03-15: Story context generated via the `bmad-create-story` workflow for backlog story `3-5-reuse-prior-configurations-in-later-experiments`.
- 2026-03-15: Implemented reuse-lineage DTO/helper, additive provenance schema changes, CLI preview updates, and fingerprint-scoped lexical baseline lookup.
- 2026-03-15: Validation run completed with `env UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev ruff check src tests`.
- 2026-03-15: Validation run completed with `env UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run --group dev pytest -q`.
- 2026-03-15: Addressed code-review feedback by making `index build-lexical` fail when snapshot chunk lineage does not match the current indexing fingerprint, then reran targeted validation plus full `ruff check src tests` and `pytest -q`.

### Completion Notes List

- Added `ConfigurationReuseLineage` plus a shared reuse classifier so `config show` previews and persisted run provenance now agree on exact replay vs modified profile reuse.
- Extended run provenance storage with additive reuse summary fields, threaded selected-profile context from bootstrap, and surfaced base/effective configuration identity in operator-facing text and JSON outputs.
- Keyed lexical baseline resolution to the current indexing fingerprint and blocked `index build-lexical` when snapshot chunks belong to a different fingerprint, so lexical, hybrid, and compare workflows now stay truthful under `--profile`.
- Updated CLI reference text and added mirrored unit, integration, and e2e coverage for ad hoc runs, exact profile replay, modified reuse, provenance inspection, and profile-driven baseline mismatches.
- Passed `ruff check src tests`, targeted unit/integration/e2e suites, and the full `pytest -q` regression suite (`265 passed`).

### File List

- `_bmad-output/implementation-artifacts/3-5-reuse-prior-configurations-in-later-experiments.md`
- `docs/cli-reference.md`
- `migrations/versions/202603151330_add_profile_reuse_lineage_to_run_provenance.py`
- `src/codeman/application/indexing/build_lexical_index.py`
- `src/codeman/application/ports/index_build_store_port.py`
- `src/codeman/application/provenance/record_run_provenance.py`
- `src/codeman/application/query/run_lexical_query.py`
- `src/codeman/bootstrap.py`
- `src/codeman/cli/config.py`
- `src/codeman/config/configuration_reuse.py`
- `src/codeman/contracts/configuration.py`
- `src/codeman/infrastructure/persistence/sqlite/repositories/index_build_repository.py`
- `src/codeman/infrastructure/persistence/sqlite/repositories/run_provenance_repository.py`
- `src/codeman/infrastructure/persistence/sqlite/tables.py`
- `tests/e2e/test_config_profiles.py`
- `tests/e2e/test_run_provenance.py`
- `tests/integration/indexing/test_build_lexical_index_integration.py`
- `tests/integration/persistence/test_run_provenance_repository.py`
- `tests/integration/query/test_run_lexical_query_integration.py`
- `tests/unit/application/test_build_lexical_index.py`
- `tests/unit/application/test_record_run_provenance.py`
- `tests/unit/application/test_run_lexical_query.py`
- `tests/unit/cli/test_config.py`
- `tests/unit/config/test_configuration_reuse.py`

## Change Log

- 2026-03-15: Implemented selected-profile reuse lineage, additive run-provenance persistence, fingerprint-scoped lexical baseline lookup, truthful `build-lexical` mismatch handling, CLI/docs updates, and mirrored automated coverage; validated with `ruff check` and full `pytest`.
