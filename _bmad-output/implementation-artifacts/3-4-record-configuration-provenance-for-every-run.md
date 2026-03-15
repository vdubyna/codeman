# Story 3.4: Record Configuration Provenance for Every Run

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a maintainer,
I want each indexing and retrieval run to record the exact configuration used,
so that I can attribute outputs and benchmark results to a precise experiment context.

## Acceptance Criteria

1. Given an indexing, query, or benchmark run completes, when run metadata is stored, then codeman records the resolved configuration identity, repository state, timestamp, and relevant provider/model metadata, and the stored metadata is sufficient to distinguish runs that used different settings.
2. Given I review a past run, when I inspect its manifest or metadata record, then I can tell which configuration produced it without reconstructing settings from logs, and the provenance record is stable enough for before/after experiment comparison.

## Tasks / Subtasks

- [x] Introduce a canonical effective-configuration provenance model and stable identity. (AC: 1, 2)
  - [x] Add strict Pydantic DTOs for secret-safe effective-config provenance and operator-facing run-provenance records.
  - [x] Build a deterministic canonical payload from the effective resolved `AppConfig` after project defaults, local config, selected profile, CLI overrides, and environment overrides have been applied.
  - [x] Reuse Story 3.3's canonical JSON and hashing approach where possible so the same effective retrieval payload produces the same stable identity across save, inspect, and run-record flows.
  - [x] Record both a full `configuration_id` for the effective retrieval config and the workflow-specific fingerprints that already drive behavior today, such as `indexing_config_fingerprint` and `semantic_config_fingerprint`, instead of collapsing everything into one field.
  - [x] Keep the payload limited to currently implemented retrieval-affecting settings and non-secret provider metadata; do not persist raw `api_key` values, runtime workspace path overrides, or future eval/judge-only fields that do not exist in code yet.

- [x] Persist provenance for the currently implemented indexing and retrieval workflows without pulling Story 5.3 forward. (AC: 1, 2)
  - [x] Add a runtime SQLite table/repository for run provenance records with a stable `run_id`, `workflow_type`, repository/snapshot references, effective `configuration_id`, created timestamp, summary provider/model fields, and deterministic JSON payloads for effective config plus workflow context.
  - [x] Reuse existing authoritative rows such as `snapshots`, `reindex_runs`, `lexical_index_builds`, and `semantic_index_builds` by referencing them from provenance records instead of duplicating artifact paths or build metadata in multiple places.
  - [x] Keep query provenance local-first and operator-safe: do not persist raw query text, repository excerpts, or other unnecessary operator input in this story unless an existing CLI contract already depends on it.
  - [x] Do not introduce JSONL logs, phase-level manifests, or a parallel troubleshooting artifact system here; Story 5.3 owns structured run logs and manifests.

- [x] Record provenance from the existing use cases and return it through additive contracts. (AC: 1, 2)
  - [x] Extend the current successful result DTOs for `index build-chunks`, `index build-lexical`, `index build-semantic`, `index reindex`, `query lexical`, `query semantic`, `query hybrid`, and `compare query-modes` with additive provenance context or stable `run_id` fields.
  - [x] For lexical-oriented flows, capture snapshot identity plus indexing-fingerprint lineage; for semantic-oriented flows, capture semantic fingerprint plus provider/model/version lineage from the resolved build and effective config.
  - [x] For hybrid and compare flows, record the component lexical and semantic build ids together with one top-level provenance record for the composed run.
  - [x] Keep `SuccessEnvelope.meta` unchanged. Provenance belongs inside `data`, not in the envelope metadata.

- [x] Add a minimal operator inspection surface for stored provenance metadata. (AC: 2)
  - [x] Expose a narrow CLI surface such as `config provenance show <run-id>` so a maintainer can inspect a past run's configuration provenance without opening SQLite manually.
  - [x] Keep text output concise and JSON output envelope-based, secret-safe, and stable for automation.
  - [x] Make inspection truthful for profile-based runs by showing the effective configuration identity that actually executed; leave explicit base-profile reuse and modified-reuse semantics to Story 3.5.

- [x] Update docs and add mirrored automated coverage. (AC: 1, 2)
  - [x] Update `docs/cli-reference.md` for any new provenance fields and inspection command(s), including what is persisted, what is intentionally omitted, and the continued stdout/stderr discipline.
  - [x] Add unit tests for canonical payload construction, stable hashing/serialization, secret redaction, and workflow-specific provenance context assembly.
  - [x] Add integration and persistence tests for the new provenance repository and migration behavior.
  - [x] Add CLI and e2e tests proving distinct effective settings produce distinct provenance identities, profile-selected runs persist the expected effective config lineage, and inspection commands can round-trip stored records.

## Dev Notes

### Epic Context

- Epic 3 is the configuration and provenance foundation for later profile reuse, run attribution, and cache correctness. Story 3.4 is the first story that should make the effective configuration of a completed run inspectable without reverse-engineering CLI flags or environment state.
- Story 3.5 depends on Story 3.4 producing a stable effective configuration identity first; it will add explicit reuse ancestry and modified-reuse semantics on top of that foundation.
- Story 5.3 owns structured JSONL logs and filesystem run manifests. Story 3.4 should create the persistent provenance identity and inspection seam needed now, without pulling the full logging/manifest system forward.
- The planning docs drift slightly on FR numbering: `epics.md` maps this story to `FR16`, while `prd.md` shifts "identify which configuration was used" to `FR17`. Use this story's acceptance criteria and Epic 3 sequencing as the implementation source of truth.
- The acceptance criteria mention benchmark runs, but the current codebase does not yet implement benchmark execution. Build the provenance model additively so future `eval` workflows can adopt it later without inventing a second provenance scheme.

### Current Repo State

- `src/codeman/config/retrieval_profiles.py` already provides a canonical, secret-safe retrieval payload plus stable hashing for saved profiles. That is the nearest existing pattern for effective configuration identity.
- `src/codeman/bootstrap.py` already resolves `--profile` through a two-pass load and exposes `selected_profile` on the container, so the effective config is already knowable at one composition point before commands run.
- Provenance is currently fragmented across several existing surfaces:
  - `snapshots.indexing_config_fingerprint`
  - `reindex_runs.previous_config_fingerprint` and `current_config_fingerprint`
  - `lexical_index_builds.indexing_config_fingerprint`
  - `semantic_index_builds.semantic_config_fingerprint` plus provider/model metadata
  - returned query and compare packages that expose build context in memory but do not persist query-run provenance
- Query, hybrid, and compare results currently return attributable build metadata but do not persist a durable query-run record and do not expose a stable `run_id` that can be inspected later.
- `src/codeman/cli/eval.py` is still a placeholder Typer group. There is no benchmark run table, benchmark artifact contract, or eval CLI surface in the implemented code yet.
- There is no generic run-provenance store, no `config provenance` inspection command, and no existing `application/diagnostics` or `application/provenance` package in the current codebase.
- `src/codeman/contracts/common.py` keeps `SuccessEnvelope.meta` intentionally small (`command`, `output_format`). New provenance data should not be stuffed into that envelope metadata.

### Previous Story Intelligence

- Story 3.3 already established the canonical, secret-safe retrieval payload and stable `profile_id`. Story 3.4 should reuse that serialization and hashing approach for effective run configuration instead of inventing a second canonicalization format.
- Story 3.3 also established the selected-profile layer ordering: project defaults -> local config -> selected profile -> CLI overrides -> environment. Provenance must reflect the final effective config after that full resolution path, not merely the selected profile name.
- Story 3.2 separated provider-owned settings from semantic workflow settings and hardened secret handling. Provenance must preserve that separation and must never persist or print secret-bearing provider fields.
- Story 1.6 and Story 2.1 already record indexing-related fingerprint lineage on snapshots, reindex runs, and lexical builds. Story 3.4 should extend that attribution story, not replace it with a parallel indexing-provenance model.
- Story 2.5 and Story 2.7 treat returned retrieval packages as the current operator-visible run context. Story 3.4 should extend those packages additively and, where persistence is needed, persist the same underlying truth instead of inventing response-only metadata.

### Cross-Story Baseline

- Story 3.1 made `load_app_config(...)` the authoritative resolution path. Any provenance identity must be derived from that resolved config, not from ad hoc environment reads inside use cases or CLI handlers.
- Story 3.3 proved that runtime SQLite persistence plus summary columns and canonical JSON payloads work well in this repo. Reuse that pattern for provenance records instead of creating one table per query mode.
- Story 2.7 proved that composed workflows here are built from existing lexical and semantic result packages rather than from separate duplicated execution paths. Provenance for hybrid and compare should follow that same composition pattern.
- Story 5.3 is still responsible for detailed phase logs and manifest artifacts. Story 3.4 should stop at persistent run metadata plus a minimal inspection surface.

### Technical Guardrails

- Keep the implementation CLI-first and local-first. Do not add HTTP endpoints, MCP runtime behavior, background workers, or speculative eval workflows. [Source: docs/project-context.md; docs/architecture/decisions.md; src/codeman/cli/eval.py]
- Derive the effective configuration identity from the final resolved config using secret-safe JSON-mode serialization and deterministic key ordering. Do not hash raw environment variable dumps, unordered dict reprs, or repository rows. [Source: src/codeman/config/loader.py; src/codeman/config/retrieval_profiles.py; https://docs.pydantic.dev/latest/concepts/serialization/; https://docs.python.org/3/library/json.html]
- Persist both a universal effective `configuration_id` and the existing workflow-specific fingerprints when they already drive runtime behavior. Those fingerprints remain authoritative for baseline selection and cache/build compatibility. [Source: src/codeman/contracts/repository.py; src/codeman/contracts/retrieval.py; src/codeman/contracts/reindexing.py]
- Reuse current authoritative records. A generic provenance row may reference snapshot/build/run ids rather than duplicating artifact paths, indexed-field lists, or other metadata that already lives elsewhere. [Source: src/codeman/infrastructure/persistence/sqlite/tables.py; src/codeman/infrastructure/persistence/sqlite/repositories/index_build_repository.py; src/codeman/infrastructure/persistence/sqlite/repositories/semantic_index_build_repository.py]
- Query, hybrid, and compare provenance must remain artifact-backed and snapshot-consistent. Do not reread mutable working-tree files, rescan repositories, or infer run lineage from live source state during provenance recording. [Source: docs/project-context.md; src/codeman/application/query/run_semantic_query.py; src/codeman/application/query/run_hybrid_query.py; src/codeman/application/query/compare_retrieval_modes.py]
- Keep secrets out of persisted provenance payloads, CLI output, error details, and docs. Provider identity and model metadata may remain visible; raw secret values may not. [Source: docs/project-context.md; _bmad-output/implementation-artifacts/3-2-configure-embedding-providers-independently.md; _bmad-output/implementation-artifacts/3-3-create-reusable-retrieval-strategy-profiles.md]
- Avoid persisting raw query text in the new provenance table unless a current CLI contract truly requires it for inspection. Story 3.4 is about configuration provenance, not full activity logging. [Inference from Story 5.3 ownership and current query contracts]
- If a new inspection failure mode is needed, align it with the existing configuration error taxonomy and stable exit-code discipline instead of leaking raw repository or SQLite exceptions. [Source: docs/project-context.md; src/codeman/contracts/errors.py; src/codeman/cli/config.py]
- Keep all generated state under `.codeman/` and the runtime metadata database. Do not write provenance artifacts into `src/`, the indexed repository, or new ad hoc top-level folders. [Source: docs/project-context.md; docs/architecture/patterns.md]

### Implementation Notes

- Prefer one generic `RunConfigurationProvenanceRecord` with summary columns plus deterministic JSON payloads over separate provenance tables for lexical query, semantic query, hybrid query, and compare. Existing build/run tables already hold workflow-specific artifact metadata; the new provenance layer should unify inspection, not multiply schemas.
- A pragmatic persisted shape is:
  - `run_id`
  - `workflow_type`
  - `repository_id`
  - `snapshot_id` (nullable where the workflow truly has none)
  - `configuration_id`
  - `indexing_config_fingerprint` (nullable)
  - `semantic_config_fingerprint` (nullable)
  - `provider_id` (nullable)
  - `model_id` (nullable)
  - `model_version` (nullable)
  - `effective_config_json`
  - `workflow_context_json`
  - `created_at`
- Keep provenance recording close to the successful boundary of each use case, after the authoritative build/query context has been resolved and just before the use case returns. Failed runs should not emit misleading success provenance rows in this story.
- For hybrid and compare, record a top-level composed run plus explicit component build references in `workflow_context_json`; do not try to fake a single semantic or lexical build row for a composed workflow.
- If a minimal inspection command is added, `config provenance show <run-id>` is the cleanest fit with the current command tree. Avoid creating a new root command group just for provenance lookup.
- The effective config payload should remain centered on the payload that actually ran. Story 3.5 will add explicit base-profile reuse ancestry later, so Story 3.4 should not overmodel modified-reuse semantics yet.
- Use additive contract changes. Existing build/query/compare result shapes are already consumed by tests and docs, so provenance should appear as a new nested context or a stable `run_id`, not as a breaking structural rewrite.

### File Structure Requirements

- Existing files to extend:
  - `src/codeman/bootstrap.py`
  - `src/codeman/cli/config.py`
  - `src/codeman/cli/index.py`
  - `src/codeman/cli/query.py`
  - `src/codeman/cli/compare.py`
  - `src/codeman/contracts/common.py`
  - `src/codeman/contracts/configuration.py`
  - `src/codeman/contracts/chunking.py`
  - `src/codeman/contracts/reindexing.py`
  - `src/codeman/contracts/retrieval.py`
  - `src/codeman/config/retrieval_profiles.py`
  - `src/codeman/infrastructure/persistence/sqlite/tables.py`
  - `docs/cli-reference.md`
- Likely new files for this story:
  - `src/codeman/config/provenance.py`
  - `src/codeman/application/ports/run_provenance_store_port.py`
  - `src/codeman/application/provenance/record_run_provenance.py`
  - `src/codeman/application/provenance/show_run_provenance.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/run_provenance_repository.py`
  - `migrations/versions/<timestamp>_create_run_provenance_records_table.py`
- Likely tests to add or extend:
  - `tests/unit/config/test_provenance.py`
  - `tests/unit/cli/test_config.py`
  - `tests/unit/cli/test_index.py`
  - `tests/unit/cli/test_query.py`
  - `tests/unit/cli/test_compare.py`
  - `tests/unit/application/test_record_run_provenance.py`
  - `tests/integration/persistence/test_run_provenance_repository.py`
  - `tests/e2e/test_run_provenance.py`
  - extend targeted existing e2e files such as `tests/e2e/test_config_profiles.py`

### Testing Requirements

- Add unit tests for canonical effective-config payload construction, deterministic JSON serialization, and stable `configuration_id` generation across equivalent payload orderings.
- Add unit tests proving semantic/provider secrets are excluded or redacted from persisted provenance payloads and from any inspection output.
- Add unit tests for workflow-specific context assembly so lexical, semantic, hybrid, compare, and reindex runs each record the expected snapshot/build lineage without inventing irrelevant fields.
- Add repository-level persistence tests for the new provenance table, including migration bootstrap, round-trip loading, and deterministic ordering when multiple records exist for the same workflow.
- Add CLI tests for the inspection surface in text and JSON modes, including stable failure handling for a missing run id.
- Add e2e coverage showing that:
  - a semantic build and semantic query under one effective config produce one `configuration_id`
  - changing a relevant model/version or fingerprint input changes the stored provenance identity
  - profile-selected runs persist the effective config lineage that actually executed
  - hybrid and compare runs record their component build references correctly
- Keep using `CliRunner` for CLI unit tests and `subprocess.run(..., check=False)` with temporary workspaces for e2e flows. Continue using workspace-local `.local/uv-cache` when `uv` is invoked. [Source: docs/project-context.md]

### Git Intelligence Summary

- Commit `8c0fb68` (`feat: add retrieval strategy profiles`) is the most relevant immediate baseline. It shows the repo's preferred pattern for config-adjacent persistence: canonical payload helper, SQLite table plus repository, nested `config` CLI surface, and mirrored unit/integration/e2e coverage.
- Commit `91fd05e` (`story(3-2): configure embedding providers independently`) reinforces two key guardrails for Story 3.4: keep provider-owned settings separate from semantic workflow settings, and keep every operator-visible or persisted surface secret-safe.
- Commit `5c8304a` (`story(2-7-compare-retrieval-modes-for-the-same-question): complete code review and mark done`) matters because it shows how composed workflows are added here: reuse lexical and semantic result packages, keep CLI thin, and avoid inventing a second execution path just because the workflow is cross-cutting.
- Across recent stories, the repo consistently prefers additive, reviewable changes over sweeping rewrites: small focused modules, one composition-root update in `bootstrap.py`, docs updates in `docs/cli-reference.md`, and mirrored tests at unit, integration, and e2e levels.

### Latest Technical Information

- As of March 15, 2026, Pydantic's latest official docs still document `ConfigDict` for strict model behavior and `model_dump(mode="json")` for JSON-mode serialization. Inference: provenance DTOs and canonical payload builders should remain strict and should serialize in JSON mode before hashing or persistence. [Source: https://docs.pydantic.dev/latest/api/config/; https://docs.pydantic.dev/latest/concepts/serialization/]
- Python's standard-library `json` docs still document `sort_keys=True` for deterministic key ordering during JSON serialization. Inference: `configuration_id` and persisted context payloads should use sorted-key canonical JSON so identity stays stable across runs and platforms. [Source: https://docs.python.org/3/library/json.html]
- SQLAlchemy 2.0 Core metadata docs continue to center `Table`, `Column`, and `MetaData` as the standard schema-definition path, and Alembic operations docs continue to use `create_table()` and `add_column()` as the standard schema-evolution surface. Inference: provenance schema changes should use the existing SQLAlchemy Core plus Alembic path rather than ad hoc `sqlite3` DDL inside repositories. [Source: https://docs.sqlalchemy.org/en/20/core/metadata.html; https://alembic.sqlalchemy.org/en/latest/ops.html]

### Project Context Reference

- `docs/project-context.md` remains the canonical implementation ruleset: strict Pydantic boundary models, thin CLI handlers, deterministic behavior, runtime artifacts under `.codeman/`, and mirrored automated coverage for touched behavior.
- `docs/architecture/decisions.md` and `docs/architecture/patterns.md` require the CLI-first layered flow to remain intact: `cli -> application -> ports -> infrastructure -> contracts/config/runtime`.
- No separate UX artifact exists for this project. For Story 3.4, the user-facing requirement is operational clarity: a maintainer must be able to identify the executed configuration without exposing secrets or digging through raw SQLite tables.

### Project Structure Notes

- The planning architecture points to future diagnostics/manifests modules, but the current repo does not yet have them. Story 3.4 should add only the minimal provenance package/store needed for current workflows and leave full manifest/logging layering to Story 5.3.
- The current `eval` command group is intentionally empty. Build the provenance record model so future benchmark/eval commands can reuse it later, but do not create benchmark execution behavior in this story.
- Existing build and query result packages already expose some attribution fields. The new provenance layer should unify and persist those facts without breaking the current CLI contracts or duplicating build metadata in multiple "truth" locations.

### References

- [Source: docs/project-context.md]
- [Source: docs/README.md]
- [Source: docs/cli-reference.md - Config Commands; Index Commands; Query Commands; Compare Commands]
- [Source: docs/architecture/decisions.md]
- [Source: docs/architecture/patterns.md]
- [Source: _bmad-output/planning-artifacts/epics.md - Epic 3; Story 3.4; Story 3.5; Story 5.3]
- [Source: _bmad-output/planning-artifacts/prd.md - Iryna journey; FR17-FR18; NFR12; NFR15]
- [Source: _bmad-output/planning-artifacts/architecture.md - Core Architectural Decisions; Data Architecture; Environment Configuration; Requirements to Structure Mapping]
- [Source: _bmad-output/implementation-artifacts/1-6-re-index-after-source-or-configuration-changes.md]
- [Source: _bmad-output/implementation-artifacts/2-1-build-lexical-index-artifacts.md]
- [Source: _bmad-output/implementation-artifacts/2-5-run-semantic-retrieval-queries.md]
- [Source: _bmad-output/implementation-artifacts/2-7-compare-retrieval-modes-for-the-same-question.md]
- [Source: _bmad-output/implementation-artifacts/3-2-configure-embedding-providers-independently.md]
- [Source: _bmad-output/implementation-artifacts/3-3-create-reusable-retrieval-strategy-profiles.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/cli/app.py]
- [Source: src/codeman/cli/config.py]
- [Source: src/codeman/cli/index.py]
- [Source: src/codeman/cli/query.py]
- [Source: src/codeman/cli/compare.py]
- [Source: src/codeman/cli/eval.py]
- [Source: src/codeman/config/loader.py]
- [Source: src/codeman/config/retrieval_profiles.py]
- [Source: src/codeman/contracts/common.py]
- [Source: src/codeman/contracts/configuration.py]
- [Source: src/codeman/contracts/chunking.py]
- [Source: src/codeman/contracts/reindexing.py]
- [Source: src/codeman/contracts/repository.py]
- [Source: src/codeman/contracts/retrieval.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/tables.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/index_build_repository.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/semantic_index_build_repository.py]
- [Source: src/codeman/application/query/run_semantic_query.py]
- [Source: src/codeman/application/query/run_hybrid_query.py]
- [Source: src/codeman/application/query/compare_retrieval_modes.py]
- [Source: tests/e2e/test_config_profiles.py]
- [Source: git log --oneline -5]
- [Source: git show --stat --summary 8c0fb68]
- [Source: git show --stat --summary 91fd05e]
- [Source: git show --stat --summary 5c8304a]
- [Source: https://docs.pydantic.dev/latest/api/config/]
- [Source: https://docs.pydantic.dev/latest/concepts/serialization/]
- [Source: https://docs.python.org/3/library/json.html]
- [Source: https://docs.sqlalchemy.org/en/20/core/metadata.html]
- [Source: https://alembic.sqlalchemy.org/en/latest/ops.html]

## Story Completion Status

- Status set to `done`.
- Effective configuration provenance now persists for indexing and retrieval workflows, including additive `run_id` contracts and `config provenance show` inspection.
- Review follow-up fixes keep non-semantic provenance truthful and prevent lexical-only workflows from failing on unrelated semantic provider config.
- Validation completed with focused regression `pytest`, full `pytest -q`, `ruff check src tests`, and targeted `ruff format --check` on touched files.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Implementation Plan

- Add a canonical effective-configuration provenance helper and stable `configuration_id` generation path that reuses Story 3.3 payload rules.
- Persist one generic run-provenance record per successful indexing/retrieval workflow and expose a minimal inspection surface under `config provenance`.
- Thread additive provenance context through existing result DTOs and CLI outputs, then mirror the change with unit, integration, and e2e coverage.

### Debug Log References

- `UV_CACHE_DIR=.local/uv-cache uv run --group dev pytest -q tests/unit/config/test_provenance.py tests/unit/application/test_record_run_provenance.py tests/integration/persistence/test_run_provenance_repository.py tests/unit/cli/test_config.py tests/unit/application/test_compare_retrieval_modes.py tests/unit/application/test_run_hybrid_query.py tests/unit/application/test_run_lexical_query.py tests/unit/application/test_run_semantic_query.py tests/unit/cli/test_query.py tests/unit/cli/test_compare.py tests/unit/cli/test_index.py`
- `UV_CACHE_DIR=.local/uv-cache uv run --group dev pytest -q tests/e2e/test_run_provenance.py tests/e2e/test_config_profiles.py`
- `UV_CACHE_DIR=.local/uv-cache uv run --group dev pytest -q tests/unit/config/test_provenance.py tests/unit/application/test_record_run_provenance.py tests/unit/cli/test_config.py`
- `UV_CACHE_DIR=.local/uv-cache uv run --group dev pytest -q`
- `UV_CACHE_DIR=.local/uv-cache uv run --group dev ruff check src tests`
- `UV_CACHE_DIR=.local/uv-cache uv run --group dev ruff format src/codeman/cli/config.py tests/unit/application/test_record_run_provenance.py`
- `UV_CACHE_DIR=.local/uv-cache uv run --group dev ruff format --check <touched-files>`

### Completion Notes List

- Added secret-safe effective configuration provenance helpers and strict provenance DTOs/repositories, including a new Alembic migration for `run_provenance_records`.
- Recorded provenance for successful chunk, lexical, semantic, reindex, lexical-query, semantic-query, hybrid-query, and compare-query-modes workflows with stable `run_id` values and workflow-specific lineage context.
- Added `config provenance show <run-id>` with stable text/JSON inspection output and configuration-typed missing-run failures.
- Addressed code-review regressions so lexical/chunk/reindex provenance no longer fails on unsupported semantic provider ids and no longer backfills semantic provider/model metadata into non-semantic runs.
- Hardened `config provenance show` so blank run ids now return stable `configuration_invalid` failures instead of bubbling a raw validation error.
- Updated CLI contracts/docs to surface additive `run_id` fields and provenance-specific metadata without changing `SuccessEnvelope.meta`.
- Added mirrored unit, integration, CLI, and e2e coverage for canonical hashing, secret redaction, repository persistence, provenance inspection, profile-selected lineage, and hybrid/compare component references.

### File List

- `_bmad-output/implementation-artifacts/3-4-record-configuration-provenance-for-every-run.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/cli-reference.md`
- `migrations/versions/202603151130_create_run_provenance_records_table.py`
- `src/codeman/application/indexing/build_chunks.py`
- `src/codeman/application/indexing/build_lexical_index.py`
- `src/codeman/application/indexing/build_semantic_index.py`
- `src/codeman/application/ports/run_provenance_store_port.py`
- `src/codeman/application/provenance/__init__.py`
- `src/codeman/application/provenance/record_run_provenance.py`
- `src/codeman/application/provenance/show_run_provenance.py`
- `src/codeman/application/query/compare_retrieval_modes.py`
- `src/codeman/application/query/format_results.py`
- `src/codeman/application/query/run_hybrid_query.py`
- `src/codeman/application/query/run_lexical_query.py`
- `src/codeman/application/query/run_semantic_query.py`
- `src/codeman/application/repo/reindex_repository.py`
- `src/codeman/bootstrap.py`
- `src/codeman/cli/compare.py`
- `src/codeman/cli/config.py`
- `src/codeman/cli/index.py`
- `src/codeman/cli/query.py`
- `src/codeman/config/provenance.py`
- `src/codeman/config/provenance_errors.py`
- `src/codeman/contracts/chunking.py`
- `src/codeman/contracts/configuration.py`
- `src/codeman/contracts/errors.py`
- `src/codeman/contracts/retrieval.py`
- `src/codeman/infrastructure/persistence/sqlite/repositories/run_provenance_repository.py`
- `src/codeman/infrastructure/persistence/sqlite/tables.py`
- `tests/e2e/test_run_provenance.py`
- `tests/integration/persistence/test_run_provenance_repository.py`
- `tests/unit/application/test_record_run_provenance.py`
- `tests/unit/cli/test_config.py`
- `tests/unit/config/test_provenance.py`

### Change Log

- 2026-03-15: Implemented run configuration provenance persistence, CLI inspection, additive `run_id` contracts, docs updates, and mirrored automated coverage for Story 3.4.
- 2026-03-15: Fixed review follow-up issues around non-semantic provenance attribution, unsupported semantic-provider tolerance, and stable blank-run-id CLI failures; story marked done.
