# Story 3.3: Create Reusable Retrieval Strategy Profiles

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a maintainer,
I want to define named retrieval strategy profiles,
so that I can rerun the same chunking, embedding, and fusion setup across multiple experiments.

## Acceptance Criteria

1. Given a valid set of retrieval-related settings, when I save it as a named profile, then codeman stores the profile in a reusable form with stable identity and validated fields and the profile can be selected in later indexing or query runs.
2. Given multiple saved strategy profiles, when I inspect or select one, then I can distinguish them by meaningful identifiers and configuration content and codeman prevents ambiguous or silently overwritten profile selection.

## Tasks / Subtasks

- [x] Define the retrieval-strategy profile model, canonical payload, and stable identity. (AC: 1, 2)
  - [x] Add a strict profile payload model under `src/codeman/config/` and a persisted record DTO under `src/codeman/contracts/` only if the stored shape needs a separate operator-facing contract.
  - [x] Capture only settings that are implemented today and materially affect retrieval behavior: the canonical `semantic_indexing` block, the selected provider's non-secret fields from `embedding_providers`, and `indexing` fields only if they already affect retrieval artifacts or baseline matching.
  - [x] Derive `profile_id` from a canonical sorted JSON representation of the normalized payload so the same content keeps the same identity across save, list, and show flows.
  - [x] Persist a human-readable `name` separately from `profile_id`; treat the name as unique and fail fast on a conflicting re-save instead of silently overwriting a different payload.
  - [x] Never persist raw secret-bearing fields such as `api_key`; profiles may retain provider identity and non-sensitive model metadata only.

- [x] Add workspace-local profile persistence behind the existing ports-and-adapters boundaries. (AC: 1, 2)
  - [x] Add a new persistence port such as `RetrievalStrategyProfileStorePort` and a SQLite adapter under `src/codeman/infrastructure/persistence/sqlite/repositories/`.
  - [x] Add SQLAlchemy table metadata and an Alembic migration for profile records in the runtime metadata database, keeping mutable experiment state under `.codeman/` instead of committed TOML files or indexed repositories.
  - [x] Store both the normalized payload JSON and summary columns useful for operator inspection, such as `name`, `profile_id`, `provider_id`, `model_id`, `model_version`, `vector_engine`, `vector_dimension`, and `created_at`.
  - [x] Keep serialization deterministic and additive so later stories can attach provenance and reuse metadata without reshaping existing saved profiles.

- [x] Expose profile management commands under the existing `config` group. (AC: 1, 2)
  - [x] Add a nested Typer group such as `config profile` using `app.add_typer(...)`, with at least `save <name>`, `list`, and `show <name-or-id>` command surfaces.
  - [x] Keep CLI handlers thin: parse inputs, call one use case, and render text or JSON through the shared success/failure envelope helpers.
  - [x] Make text and JSON output distinguish profiles by meaningful identifiers and configuration summaries: name, profile id, selected provider, model/version, vector engine/dimension, and any non-secret salts or local model path values that materially affect behavior.
  - [x] Add stable failure behavior for not found, duplicate-name, and ambiguous selection/show requests; do not silently pick one of multiple candidates or overwrite on save.

- [x] Integrate selected profiles into the authoritative configuration-resolution path. (AC: 1)
  - [x] Extend the root CLI bootstrap state with a `--profile` option so later `index` and `query` commands can select one saved profile without adding duplicate per-command flags.
  - [x] Resolve the selected profile as an additional config layer after project/local file defaults and before explicit CLI/environment overrides. If the runtime path is needed to open the profile store, use a small two-pass bootstrap/load flow rather than bypassing the existing loader.
  - [x] Ensure `config show`, `index build-semantic`, `query semantic`, `query hybrid`, and `compare query-modes` all see the same effective resolved config when `--profile` is supplied.
  - [x] Keep profile scope limited to retrieval-related settings. Do not let profile selection mutate workspace root, metadata database path, config file path resolution, or unrelated repo-registration behavior.

- [x] Reuse existing configuration seams and preserve the current local-first security model. (AC: 1, 2)
  - [x] Reuse Story 3.1's loader and Story 3.2's separated `embedding_providers` model instead of creating a second parser or a profile-only config format.
  - [x] Keep the implemented provider surface local-first and `local-hash` only for now; unsupported provider ids should continue to fail through the existing typed error path.
  - [x] Preserve compatibility aliases as input-only compatibility shims, but keep saved profiles in the canonical separated shape used by current config resolution.
  - [x] Do not introduce new chunking or fusion flags just to make profiles look richer. Persist only the retrieval knobs that are actually implemented today and structure the model so future fields can be added additively.
  - [x] Never write provider secrets to project defaults, profile records, logs, or CLI output.

- [x] Document the CLI contract and add mirrored automated coverage. (AC: 1, 2)
  - [x] Update `docs/cli-reference.md` with `config profile` commands, the `--profile` selection flow, precedence including the selected-profile layer, no-silent-overwrite behavior, and secret-handling rules.
  - [x] Add unit tests for normalized profile payload extraction, stable id generation, duplicate-name prevention, loader precedence with `--profile`, and config-show selection behavior.
  - [x] Add CLI unit tests for `config profile save/list/show` in text and JSON modes.
  - [x] Add integration or e2e flows that save a profile, reuse it on `config show`, `index build-semantic`, and `query semantic`, plus failure tests for missing profile selection and secret leakage.

## Dev Notes

### Epic Context

- Epic 3 is the configuration and provenance foundation for later profile reuse, run attribution, and cache correctness.
- Story 3.3 is the first story that should materialize a named configuration identity a maintainer can save, inspect, and select later; Stories 3.4 and 3.5 depend on that identity being stable and reusable.
- The planning docs currently drift on FR numbering: `epics.md` maps this story to `FR15`, while `prd.md` shifts retrieval-strategy configuration to `FR16` and reuse to `FR18`. For implementation, use this story's acceptance criteria and Epic 3 sequencing as the source of truth.

### Current Repo State

- `src/codeman/config/loader.py` currently resolves exactly four layers: project defaults, optional local config, CLI overrides, and environment overrides. There is no profile layer yet.
- `src/codeman/cli/config.py` currently exposes only `config show`; there is no save/list/show workflow for named retrieval profiles.
- `src/codeman/bootstrap.py` wires config, stores, and use cases directly; there is no application/configuration package or profile store in the current container.
- `src/codeman/infrastructure/persistence/sqlite/tables.py` currently defines repository, snapshot, source-file, chunk, reindex, lexical-build, and semantic-build tables only. There is no persisted `ExperimentConfig` or retrieval-profile entity in code yet.
- The currently implemented retrieval knobs are still narrow:
  - `indexing.fingerprint_salt`
  - `semantic_indexing.provider_id`
  - `semantic_indexing.vector_engine`
  - `semantic_indexing.vector_dimension`
  - `semantic_indexing.fingerprint_salt`
  - selected provider fields under `embedding_providers.local_hash`
- Hybrid retrieval is implemented, but its fusion parameters are not user-configurable today. `DEFAULT_HYBRID_CANDIDATE_WINDOW = 50` and `DEFAULT_HYBRID_RANK_CONSTANT = 60` are fixed in code.
- Chunk generation already records per-chunk `strategy`, but chunking strategy is not yet a maintainer-facing config surface. Do not invent new chunking knobs in this story just because the epic language mentions chunking.

### Previous Story Intelligence

- Story 3.2 deliberately separated provider-owned settings from `semantic_indexing`. Story 3.3 should save and reuse the canonical separated shape rather than collapsing provider settings back into semantic config.
- Story 3.2 also established the operator-safe `config show` surface and secret-handling expectations. Profile save/list/show and `--profile` selection should remain secret-safe and should never echo `api_key` or similar fields.
- Semantic fingerprinting and baseline selection already depend on the selected provider, model, vector engine, and vector dimension. Profile selection must feed the same fingerprint path so later semantic builds and queries remain aligned.
- Story 3.2 explicitly warned that Story 3.3 should save reusable profiles without duplicating provider internals. Treat that as a hard guardrail: profile payloads should include selected provider configuration in canonical, non-secret form, not a second shadow model.

### Cross-Story Baseline

- Story 3.1 introduced the authoritative layered loader, root CLI override handling, and `config show`. Story 3.3 should extend that same resolution path rather than adding profile lookup ad hoc inside individual commands.
- Story 2.5 established semantic baseline lookup keyed by semantic config fingerprint. If profile selection bypasses the loader or changes fingerprint composition inconsistently, semantic query will drift from the persisted build baseline.
- Story 2.7 established compare/hybrid flows as compositions of the lexical and semantic paths. Once profiles exist, those composed flows should inherit the selected profile automatically instead of growing custom selection logic.
- Story 3.4 will need a stable saved configuration identity to record provenance per run. Story 3.5 will need to treat a saved profile as a reusable base configuration with later overrides. Story 3.3 should introduce the stable identity and selection seam, not the full provenance or override ancestry model.

### Technical Guardrails

- Keep the implementation CLI-first and local-first. Do not introduce HTTP surfaces, MCP runtime behavior, remote profile registries, or implicit provider auto-enablement in this story. [Source: docs/project-context.md; docs/architecture/decisions.md]
- Keep configuration resolution centralized in `src/codeman/config/` and `bootstrap.py`. If profile selection requires reading runtime-managed state, perform that lookup near bootstrap and re-enter the shared loader instead of reading SQLite directly from CLI handlers or query/index use cases. [Source: docs/project-context.md; docs/architecture/patterns.md]
- Use strict Pydantic models with `ConfigDict(extra="forbid")` for saved profile payloads and operator-facing DTOs. Unknown profile keys should fail fast rather than being silently ignored. [Source: docs/project-context.md; https://docs.pydantic.dev/latest/api/config/]
- Keep secrets out of persisted profile payloads, logs, benchmark-facing metadata, and CLI text/JSON output. Provider identity and non-sensitive model metadata may remain visible; secret values may not. [Source: _bmad-output/planning-artifacts/prd.md - NFR7-NFR9; _bmad-output/planning-artifacts/architecture.md - Secrets & Sensitive Data Handling; https://docs.pydantic.dev/latest/api/types/#secretstr]
- Do not store mutable retrieval profiles in `pyproject.toml`. Project defaults are committed source-controlled configuration, while profiles are mutable experiment state. The standard-library `tomllib` is read-only, so mutating TOML would require an additional writer dependency or brittle text rewriting. [Source: docs/project-context.md; https://docs.python.org/3/library/tomllib.html]
- Preserve clean JSON `stdout` and route human progress or diagnostics to `stderr`. New profile commands must keep the same envelope and CLI formatting discipline used elsewhere in the repo. [Source: docs/project-context.md; docs/cli-reference.md]
- Do not add new retrieval knobs purely for future ambition. Persist only implemented settings today and leave obvious additive seams for later chunking/fusion/reranking fields. [Inference from current code and Epic 3 sequencing]

### Implementation Notes

- Recommended persistence choice: workspace-local runtime SQLite (`.codeman/metadata.sqlite3`) rather than mutating `pyproject.toml` or the optional user-local TOML file. Inference: this matches the architecture's first-class `ExperimentConfig` direction, fits the existing Alembic-backed metadata pattern, and keeps mutable experiment state out of committed sources.
- A practical minimal stored profile shape is:
  - `profile_id`
  - unique `name`
  - canonical normalized payload JSON
  - summary columns for `provider_id`, `model_id`, `model_version`, `vector_engine`, `vector_dimension`
  - `created_at`
  Inference: summary columns make list/show/select efficient while the payload JSON remains future-extensible.
- Build the normalized profile payload from the effective config after Story 3.1 and 3.2 resolution. Hash the canonical sorted JSON to derive `profile_id`. Save idempotently when the same name points to the same payload; fail when the same name points to different content unless an explicit overwrite path is introduced in a later story.
- Because runtime path selection already happens through root CLI options and environment overrides, bootstrap can resolve base runtime config first, open the profile store, load the selected profile payload, and then call the shared loader again with that payload as an extra layer. Keep that complexity inside bootstrap/loader rather than pushing it into every command.
- Keep saved profile content canonical in the separated shape:
  - `semantic_indexing`
  - selected `embedding_providers.<provider>`
  - optionally `indexing` only when the field materially affects retrieval artifacts already
  Inference: this is the smallest profile surface that matches current code and stays compatible with later provenance/reuse stories.
- `config profile show` and `config show --profile <name>` should surface both the human-readable name and stable `profile_id`, so operators can tell whether two similarly named profiles actually resolve to different content.
- Stable failure behavior will likely need new typed errors and error codes such as `configuration_profile_not_found`, `configuration_profile_name_conflict`, and possibly `configuration_profile_ambiguous`. Keep the naming aligned with the repo's existing error taxonomy and map them through stable exit codes.

### File Structure Requirements

- Existing files to extend:
  - `src/codeman/cli/app.py`
  - `src/codeman/cli/config.py`
  - `src/codeman/bootstrap.py`
  - `src/codeman/config/loader.py`
  - `src/codeman/config/models.py`
  - `src/codeman/contracts/errors.py`
  - `src/codeman/infrastructure/persistence/sqlite/tables.py`
  - `docs/cli-reference.md`
- Likely new files for this story:
  - `src/codeman/config/retrieval_profiles.py`
  - `src/codeman/application/ports/retrieval_profile_store_port.py`
  - `src/codeman/application/config/save_retrieval_strategy_profile.py`
  - `src/codeman/application/config/list_retrieval_strategy_profiles.py`
  - `src/codeman/application/config/show_retrieval_strategy_profile.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/retrieval_profile_repository.py`
  - `migrations/versions/<timestamp>_create_retrieval_strategy_profiles_table.py`
- Likely tests to add or extend:
  - `tests/unit/config/test_retrieval_profiles.py`
  - `tests/unit/config/test_loader.py`
  - `tests/unit/cli/test_config.py`
  - `tests/integration/persistence/test_retrieval_profile_repository.py`
  - `tests/e2e/test_config_profiles.py`
- Keep runtime-managed profile state under `.codeman/`. Do not write generated profile artifacts into `src/`, `tests/fixtures/`, or the indexed target repository. [Source: docs/project-context.md]

### Testing Requirements

- Add unit tests for canonical profile payload extraction from effective config, stable `profile_id` generation, and deterministic serialization ordering.
- Add unit tests for duplicate-name rejection, idempotent same-name same-payload saves, and ambiguous/not-found show or selection failures.
- Add loader/bootstrap tests proving a selected profile is applied before explicit CLI/environment overrides and that `config show --profile ...` reflects the same effective values seen by runtime commands.
- Add CLI tests for `config profile save`, `config profile list`, and `config profile show` in both text and JSON modes, including clean `stdout` / `stderr` separation.
- Add integration or e2e tests proving a saved profile can drive `index build-semantic`, `query semantic`, and `compare query-modes` without manual re-entry of the same settings.
- Add regression tests proving secret-bearing provider fields are never written into profile records or printed to stdout/stderr, even when the current config includes them through env or protected local config.
- Keep using `CliRunner` for CLI unit tests and `subprocess.run(..., check=False)` plus temporary workspaces for e2e flows. Continue using workspace-local `.local/uv-cache` when `uv` is invoked. [Source: docs/project-context.md]

### Git Intelligence Summary

- Commit `a37f5b6` (Story 3.1) shows the preferred pattern for config work in this repo: add focused modules under `src/codeman/config/`, wire the behavior once through `bootstrap.py` and root CLI options, update `docs/cli-reference.md`, and mirror the change with unit and e2e coverage.
- Commit `91fd05e` (Story 3.2) shows the current preferred profile-adjacent pattern: keep provider-owned config separate, keep operator surfaces secret-safe, and preserve compatibility aliases only as inputs rather than as the canonical stored shape.
- Commit `5966a34` (Story 2.5) matters because semantic query baseline selection already depends on the semantic fingerprint. Profile selection must route through the same fingerprint builder or the system will misreport missing baselines.
- Commit `5c8304a` (Story 2.7) matters because it demonstrates how new cross-cutting query functionality is added here: one focused application seam, thin CLI wiring, contract additions, and mirrored tests instead of broad rewrites.
- Across recent stories, the repo consistently prefers additive refactors over sweeping rewrites. Preserve stable DTOs, extend the nearest fitting module, and keep docs/tests synchronized with the CLI contract.

### Latest Technical Information

- Python's standard-library `tomllib` remains a read-only TOML parser. Inference: using runtime SQLite for mutable saved profiles is lower risk than introducing brittle TOML rewriting or a new writer dependency just to persist experiment state. [Source: https://docs.python.org/3/library/tomllib.html]
- Pydantic's `ConfigDict(extra="forbid")` remains the standard strict-model mechanism for rejecting unknown fields. Inference: saved profile payloads and operator DTOs should use it so unexpected config keys do not get silently accepted. [Source: https://docs.pydantic.dev/latest/api/config/]
- Pydantic `SecretStr` continues to redact sensitive values in display and serialization unless explicitly unwrapped. Inference: if any provider-owned secret-bearing field ever touches profile-adjacent DTOs, keep it wrapped and exclude it from the persisted normalized payload. [Source: https://docs.pydantic.dev/latest/api/types/#secretstr]
- Typer continues to support nested command groups through `app.add_typer(...)`. Inference: `config profile ...` is a natural extension of the existing CLI tree and does not require a new root command group. [Source: https://typer.tiangolo.com/tutorial/subcommands/add-typer/]

### Project Context Reference

- `docs/project-context.md` is the canonical implementation ruleset: strict Pydantic boundary models, thin CLI handlers, deterministic behavior, runtime artifacts under `.codeman/`, and mirrored automated coverage for touched behavior.
- `docs/architecture/decisions.md` and `docs/architecture/patterns.md` require the CLI-first layered flow to remain intact: `cli -> application -> ports -> infrastructure -> contracts/config/runtime`.
- No separate UX artifact exists for this project. For Story 3.3, the user-facing requirement is operational clarity: profile names and IDs must be understandable, selections must be explicit, and profile behavior must be inspectable without exposing secrets.

### Project Structure Notes

- The planning architecture mentions a broader `ExperimentConfig` direction and richer future config infrastructure than the implemented repo currently has. Story 3.3 should add only enough persistence and CLI control to support save, list, show, and select for current retrieval settings.
- The runtime metadata database and `.codeman/` boundary already exist and are the right home for mutable saved profile state in the current implementation.
- Current code does not yet have provenance records, profile ancestry, or override-tracking semantics. Keep this story focused on canonical save/select identity and leave full run provenance and modified-reuse semantics to Stories 3.4 and 3.5.

### References

- [Source: docs/project-context.md]
- [Source: docs/README.md]
- [Source: docs/cli-reference.md - Index Commands; `config show`; `query semantic`; `query hybrid`; `compare query-modes`]
- [Source: docs/architecture/decisions.md]
- [Source: docs/architecture/patterns.md]
- [Source: _bmad-output/planning-artifacts/epics.md - Epic 3; Story 3.2; Story 3.3; Story 3.4; Story 3.5]
- [Source: _bmad-output/planning-artifacts/architecture.md - Data Architecture; Authentication & Security; API & Communication Patterns; Structure Patterns; Project Structure & Boundaries; Requirements to Structure Mapping]
- [Source: _bmad-output/planning-artifacts/prd.md - Journey 4; Retrieval Configuration & Experiment Control; NFR5-NFR9; NFR12-NFR18; NFR20-NFR26]
- [Source: _bmad-output/implementation-artifacts/3-1-define-the-layered-configuration-model.md]
- [Source: _bmad-output/implementation-artifacts/3-2-configure-embedding-providers-independently.md]
- [Source: pyproject.toml]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/cli/app.py]
- [Source: src/codeman/cli/config.py]
- [Source: src/codeman/config/defaults.py]
- [Source: src/codeman/config/loader.py]
- [Source: src/codeman/config/models.py]
- [Source: src/codeman/config/semantic_indexing.py]
- [Source: src/codeman/config/embedding_providers.py]
- [Source: src/codeman/application/query/run_hybrid_query.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: src/codeman/contracts/retrieval.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/tables.py]
- [Source: tests/e2e/test_config_show.py]
- [Source: tests/unit/config/test_loader.py]
- [Source: git log --oneline -5]
- [Source: git show --stat --summary a37f5b6]
- [Source: git show --stat --summary 91fd05e]
- [Source: git show --stat --summary 5966a34]
- [Source: git show --stat --summary 5c8304a]
- [Source: https://docs.python.org/3/library/tomllib.html]
- [Source: https://docs.pydantic.dev/latest/api/config/]
- [Source: https://docs.pydantic.dev/latest/api/types/#secretstr]
- [Source: https://typer.tiangolo.com/tutorial/subcommands/add-typer/]

## Story Completion Status

- Status set to `done`.
- Completion note: `Implemented reusable retrieval strategy profiles with profile-aware config resolution, CLI management commands, workspace-local persistence, and post-review hardening for normalized identifiers plus side-effect-free read-only lookups.`
- Recorded assumptions:
  - Retrieval strategy profiles should be persisted in the workspace runtime metadata store rather than in committed or user-local TOML files.
  - The initial saved profile scope should contain only currently implemented retrieval-affecting settings and the selected provider's non-secret config.
  - The selected-profile layer should sit between file-based config inputs and explicit CLI/environment overrides.
  - Saving the same name with identical content should be idempotent; saving the same name with different content should fail unless an explicit overwrite feature is introduced later.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Debug Log References

- 2026-03-14: Story context generated via the `bmad-create-story` workflow for backlog story `3-3-create-reusable-retrieval-strategy-profiles`.
- 2026-03-15: Implemented retrieval profile persistence, CLI commands, `--profile` config resolution, docs updates, and automated validation.
- 2026-03-15: Closed review findings around profile-name normalization and read-only profile lookup side effects, then reran the full validation suite.

### Completion Notes List

- Implemented canonical retrieval-strategy profile models, deterministic payload hashing, and operator-facing DTOs for saved profile inspection.
- Added workspace-local SQLite persistence, Alembic migration coverage, and typed not-found/name-conflict/ambiguous profile selection failures.
- Added `config profile save/list/show` plus root-level `--profile` resolution wired through the shared bootstrap and loader path for `config show`, `index build-semantic`, `query semantic`, `query hybrid`, and `compare query-modes`.
- Closed the post-review gaps by normalizing profile identifiers, rejecting blank names, and keeping read-only `list`/`show`/`--profile` resolution free of runtime-metadata side effects until a write path initializes the store.
- Updated `docs/cli-reference.md` to document profile commands, selected-profile precedence, conflict behavior, and secret-handling guarantees.
- Added unit, integration, and e2e coverage for canonical payload extraction, loader precedence, CLI behavior, persistence, missing/ambiguous selection, cross-command profile reuse, and secret redaction.
- Verified the implementation with `uv run --group dev ruff check src tests` and a full `uv run --group dev pytest` run (`240 passed`).

### File List

- _bmad-output/implementation-artifacts/3-3-create-reusable-retrieval-strategy-profiles.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- docs/cli-reference.md
- migrations/versions/202603151000_create_retrieval_strategy_profiles_table.py
- src/codeman/application/config/__init__.py
- src/codeman/application/config/list_retrieval_strategy_profiles.py
- src/codeman/application/config/retrieval_profile_selection.py
- src/codeman/application/config/save_retrieval_strategy_profile.py
- src/codeman/application/config/show_retrieval_strategy_profile.py
- src/codeman/application/ports/retrieval_profile_store_port.py
- src/codeman/bootstrap.py
- src/codeman/cli/app.py
- src/codeman/cli/config.py
- src/codeman/config/loader.py
- src/codeman/config/profile_errors.py
- src/codeman/config/retrieval_profiles.py
- src/codeman/contracts/configuration.py
- src/codeman/contracts/errors.py
- src/codeman/infrastructure/persistence/sqlite/repositories/retrieval_profile_repository.py
- src/codeman/infrastructure/persistence/sqlite/tables.py
- tests/e2e/test_config_profiles.py
- tests/e2e/test_config_show.py
- tests/integration/persistence/test_retrieval_profile_repository.py
- tests/unit/cli/test_config.py
- tests/unit/config/test_loader.py
- tests/unit/config/test_retrieval_profiles.py

## Change Log

- 2026-03-14: Created comprehensive ready-for-dev story context for reusable retrieval strategy profiles.
- 2026-03-15: Implemented reusable retrieval strategy profiles, profile-aware config resolution, workspace-local persistence, CLI management commands, CLI documentation updates, and mirrored automated coverage.
- 2026-03-15: Closed review findings by normalizing profile identifiers, preventing blank-name saves, and removing read-only runtime metadata side effects for profile lookups.
