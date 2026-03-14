# Story 3.2: Configure Embedding Providers Independently

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a maintainer,
I want embedding provider settings to be managed separately from other indexing settings,
so that I can change provider behavior without redefining the whole system.

## Acceptance Criteria

1. Given a retrieval configuration that includes embedding settings, when I change provider-specific options, then codeman validates them through a dedicated embedding configuration model and keeps unrelated retrieval settings unchanged.
2. Given provider credentials are required, when codeman loads embedding configuration, then secrets are resolved from environment or protected local config only and secret values are not written to source control, logs, or benchmark reports.

## Tasks / Subtasks

- [x] Introduce dedicated provider configuration models and a clean selection seam. (AC: 1, 2)
  - [x] Add a dedicated provider-config module under `src/codeman/config/` such as `embedding_providers.py`, with strict Pydantic models for provider-owned settings instead of continuing to store model and path fields directly on `SemanticIndexingConfig`.
  - [x] Keep `SemanticIndexingConfig` focused on semantic workflow selection and vector-index settings such as `provider_id`, `vector_engine`, `vector_dimension`, and `fingerprint_salt`.
  - [x] Move provider-owned fields such as `model_id`, `model_version`, `local_model_path`, and any future credential fields into the dedicated provider model.
  - [x] Preserve a valid "provider not selected" state so lexical-only and other local-first workflows still run without semantic provider configuration.

- [x] Extend layered configuration loading so provider settings resolve independently and safely. (AC: 1, 2)
  - [x] Add project-default and local-config shapes that keep provider sections separate from semantic-indexing sections, for example `[tool.codeman.embedding_providers.local_hash]` or an equivalent dedicated provider table.
  - [x] Update `src/codeman/config/defaults.py`, `src/codeman/config/loader.py`, and `src/codeman/config/models.py` so environment and protected local config values hydrate the dedicated provider models while semantic and vector settings continue to resolve independently.
  - [x] Keep the deterministic precedence from Story 3.1 and avoid introducing a second configuration-resolution path.
  - [x] Do not allow secret-bearing provider values to come from committed project defaults or CLI flags; fail with `configuration_invalid` instead of silently accepting unsupported secret sources.

- [x] Preserve the current local-hash workflow while preparing a future-safe extension seam. (AC: 1, 2)
  - [x] Keep the current `local-hash` provider fully working for semantic build and query flows after the configuration split.
  - [x] Preserve current `CODEMAN_SEMANTIC_*` behavior used by tests and docs, either as first-class compatibility aliases or through a clearly documented, fully test-backed migration if provider-scoped environment variables are introduced.
  - [x] Do not introduce a real external-provider adapter, network calls, or automatic provider enablement in this story; if you add an extension seam for future providers, keep it config-only and opt-in.

- [x] Refactor semantic build and query provider resolution to consume the new provider config. (AC: 1)
  - [x] Update `src/codeman/application/indexing/build_embeddings.py`, `src/codeman/application/query/run_semantic_query.py`, and related bootstrap wiring so provider descriptors are composed from the selected provider config rather than raw `SemanticIndexingConfig` fields.
  - [x] Keep semantic fingerprinting, baseline lookup, and provider and model attribution stable by deriving provider metadata from the dedicated provider config without changing unrelated lexical or runtime configuration semantics.
  - [x] Ensure changing provider-specific fields affects only the semantic provider lineage and fingerprint, not unrelated indexing settings or runtime path resolution.

- [x] Redact or omit secrets in every operator-visible and persisted surface. (AC: 2)
  - [x] Update `config show` text and JSON output so secret-bearing provider fields are omitted or redacted, while provider identity and non-sensitive model metadata remain visible.
  - [x] Ensure secret values do not appear in CLI failures, structured error details, logs, semantic build records, embedding artifacts, or future benchmark-facing metadata surfaces.
  - [x] Keep `EmbeddingProviderDescriptor`, semantic build records, and related contracts free of raw secret fields.

- [x] Add documentation and mirrored automated coverage. (AC: 1, 2)
  - [x] Update `docs/cli-reference.md` with the separated provider configuration layout, supported env and local-config inputs, redaction behavior, and any compatibility aliases.
  - [x] Add or extend unit tests for provider config validation, loader precedence, redaction, and invalid secret-source handling.
  - [x] Add or extend integration and e2e tests proving semantic build and query still work with the separated provider config and that secret values never surface in stdout, stderr, or persisted build metadata.

## Dev Notes

### Epic Context

- Epic 3 is the configuration and provenance foundation for later profiles, run attribution, and cache correctness. Story 3.2 is the first step that turns provider settings into a distinct configuration concern instead of a few semantic-indexing fields mixed into one model.
- Story 3.1 already established the authoritative layered loader and `config show`; Story 3.2 must extend that same resolution path rather than creating a provider-specific shortcut.
- Stories 3.3 through 3.6 depend on this split: named profiles need separable provider settings, provenance needs clear provider lineage, and cache identity must later distinguish provider and model changes cleanly.

### Current Repo State

- `src/codeman/config/semantic_indexing.py` currently mixes provider selection, provider-owned metadata, local model path, vector-engine settings, and semantic fingerprint salt in one model.
- `src/codeman/config/loader.py` currently maps all `CODEMAN_SEMANTIC_*` environment variables straight into the `semantic_indexing` section. There is no dedicated provider-config namespace yet.
- `src/codeman/application/indexing/build_embeddings.py` and `src/codeman/application/query/run_semantic_query.py` both assume provider details live on `SemanticIndexingConfig` and currently only support the `local-hash` provider.
- `src/codeman/cli/config.py` reports effective semantic settings but currently has no secret-redaction concerns beyond omission of unset values.
- `pyproject.toml` now contains `[tool.codeman.semantic_indexing]` defaults, but no dedicated provider table. The repo still has no `infrastructure/config/` package or secret-loader adapter.
- The implemented codebase is still local-first and local-provider-only for semantic workflows. Do not pretend that OpenAI or another external embedding provider already exists in code.

### Cross-Story Baseline

- Story 2.4 introduced semantic index building, `EmbeddingProviderDescriptor`, `local-hash` provider infrastructure, and semantic build persistence. Story 3.2 must preserve that provider attribution and artifact compatibility path.
- Story 2.5 made semantic query baseline selection configuration-aware. If provider config is split incorrectly, semantic query can drift from the build fingerprint and falsely report missing baselines.
- Story 3.1 already moved env, file, and default merging into `load_app_config(...)`. Story 3.2 should plug provider configuration into that loader and preserve fail-fast `configuration_invalid` behavior before any workflow starts.
- Later stories need clear boundaries:
  - Story 3.3 should be able to save reusable strategy profiles without duplicating provider internals.
  - Story 3.4 will need stable provider and model provenance from the effective config.
  - Story 3.6 will later key embedding caches to provider identity, model version, and chunk serialization without reverse-engineering mixed config fields.

### Technical Guardrails

- Keep the implementation CLI-first and local-first. Do not add HTTP, MCP runtime behavior, or implicit external-provider activation. [Source: docs/project-context.md; docs/architecture/decisions.md]
- Keep config resolution centralized in `src/codeman/config/` and `bootstrap.py`. Do not read secrets directly from `os.environ` inside models, adapters, CLI handlers, or use cases. [Source: docs/project-context.md; _bmad-output/implementation-artifacts/3-1-define-the-layered-configuration-model.md]
- Keep provider-specific communication behind `src/codeman/application/ports/embedding_provider_port.py` and `src/codeman/infrastructure/embeddings/`. CLI modules must not gain provider-specific branching. [Source: docs/architecture/patterns.md; _bmad-output/planning-artifacts/architecture.md - Architectural Boundaries]
- Preserve current local-hash semantics and current semantic build and query behavior as regression guardrails. The existing semantic e2e and integration tests are the canary for whether the config split stayed compatible. [Source: tests/e2e/test_index_build_semantic.py; tests/e2e/test_query_semantic.py; tests/integration/indexing/test_build_semantic_index_integration.py]
- Keep `ConfigDict(extra="forbid")` on new config models. If secrets are introduced, use redacted, secret-aware types rather than plain strings that can leak through repr or `model_dump()`. [Source: docs/project-context.md; https://docs.pydantic.dev/latest/api/types/#secretstr]
- Do not store secrets in `pyproject.toml`, committed docs examples, build records, or artifact payloads. Provider identity and model metadata must stay visible, but secret material must stay out of logs and persisted contracts. [Source: _bmad-output/planning-artifacts/prd.md - NFR7-NFR9, NFR15; _bmad-output/planning-artifacts/architecture.md - Secrets & Sensitive Data Handling]
- Avoid changing unrelated retrieval settings when only provider options change. Vector engine, vector dimension, lexical indexing, runtime paths, and non-provider config should remain stable unless explicitly modified. [Source: Epic 3 Story 3.2 Acceptance Criteria; docs/cli-reference.md]
- Do not overbuild future-provider abstractions. A clean extension seam is useful, but a fake external adapter or speculative network implementation is out of scope for this story. [Source: AGENTS.md; docs/project-context.md]

### Implementation Notes

- Prefer a dedicated provider config structure that semantic config can reference by `provider_id`, instead of continuing to treat provider model and path fields as semantic-index settings. Inference: this is the smallest design that satisfies FR14 and keeps later profile and provenance work composable.
- A safe minimal shape is:
  - `semantic_indexing`: selection and vector-engine settings
  - `embedding_providers`: provider-owned settings keyed by provider id
  Inference: this preserves one shared semantic config while making provider behavior independently configurable.
- Keep the current `local-hash` provider as the only implemented provider. If you add a provider registry or lookup helper, start by resolving `local-hash` from the new config structure and raise the existing unavailable error for unsupported providers.
- Preserve existing env-driven workflows used throughout tests. If new provider-scoped env names are added, keep current `CODEMAN_SEMANTIC_PROVIDER_ID`, `CODEMAN_SEMANTIC_MODEL_ID`, `CODEMAN_SEMANTIC_MODEL_VERSION`, and `CODEMAN_SEMANTIC_LOCAL_MODEL_PATH` working as compatibility inputs unless you update all consuming tests and docs in the same story with a clearly documented migration.
- `config show` should become the operator-safe inspection surface for the new model. It should help a maintainer confirm which provider is selected and whether secret-bearing fields are configured, without ever echoing the secret contents.
- Keep semantic fingerprint generation stable in spirit: provider identity, model version, vector engine, vector dimension, and relevant local-model identity should still influence the fingerprint. If descriptor-building moves to provider config, keep the fingerprint payload deterministic and comparable across builds and query runs.
- Prefer extending the existing custom TOML loader instead of introducing `pydantic-settings` mid-epic unless a concrete secret-source requirement truly justifies the dependency. The repo already has a tested loader and explicit precedence model. [Inference from `src/codeman/config/loader.py` and `_bmad-output/implementation-artifacts/3-1-define-the-layered-configuration-model.md`]
- If secret-bearing provider fields are added for a future-ready config shape, wrap them in `SecretStr` and unwrap them only at the last boundary that truly needs the raw value. [Source: https://docs.pydantic.dev/latest/api/types/#secretstr]

### File Structure Requirements

- Existing files to extend:
  - `src/codeman/config/models.py`
  - `src/codeman/config/semantic_indexing.py`
  - `src/codeman/config/defaults.py`
  - `src/codeman/config/loader.py`
  - `src/codeman/bootstrap.py`
  - `src/codeman/application/indexing/build_embeddings.py`
  - `src/codeman/application/query/run_semantic_query.py`
  - `src/codeman/cli/config.py`
  - `docs/cli-reference.md`
  - `pyproject.toml`
- Likely new files for this story:
  - `src/codeman/config/embedding_providers.py`
  - optionally a small helper module if provider resolution becomes too dense
  - optionally `tests/unit/config/test_embedding_providers.py`
- Likely tests to add or extend:
  - `tests/unit/config/test_loader.py`
  - `tests/unit/config/test_semantic_indexing.py`
  - `tests/unit/config/test_models.py`
  - `tests/unit/cli/test_config.py`
  - `tests/unit/application/test_build_semantic_index.py`
  - `tests/unit/application/test_run_semantic_query.py`
  - `tests/integration/indexing/test_build_semantic_index_integration.py`
  - `tests/e2e/test_index_build_semantic.py`
  - `tests/e2e/test_query_semantic.py`
- Keep provider adapters in `src/codeman/infrastructure/embeddings/`; do not move provider logic into `config/` or CLI modules. [Source: _bmad-output/planning-artifacts/architecture.md - Project Structure & Boundaries]

### Testing Requirements

- Add unit tests for the dedicated provider-config model, including valid local-hash config, unset-provider state, secret redaction behavior, and invalid provider-specific combinations.
- Add loader tests for separated provider sections across project defaults, local config, CLI and runtime overrides, and environment final overrides.
- Add regression tests proving current semantic build and query flows still work after the config split, including same-snapshot fingerprint sensitivity when provider model or version changes.
- Add CLI tests for `config show` text and JSON output that prove provider identity remains visible while any secret-bearing fields are redacted or omitted.
- Add e2e or integration coverage for failure paths:
  - unsupported provider id
  - missing required local model path for `local-hash`
  - invalid provider section or invalid secret source
  - guarantee that stdout and stderr do not leak configured secret values
- Keep using `CliRunner` for CLI unit tests and `subprocess.run(..., check=False)` for e2e CLI flows. Continue using workspace-local runtime roots and `.local/uv-cache` in tests. [Source: docs/project-context.md]

### Git Intelligence Summary

- Commit `a37f5b6` (Story 3.1 close-out) shows the current preferred pattern for configuration work: add small focused modules under `src/codeman/config/`, wire them once through `bootstrap.py`, expose a narrow CLI inspection surface, then mirror the behavior with unit and e2e coverage.
- Commit `c05aeea` (Story 2.4) matters because it established the current semantic provider contract, local-hash adapter, semantic-index persistence, and provider attribution. Story 3.2 should extend those seams, not replace them.
- Commit `5966a34` (Story 2.5) matters because query-time baseline matching already depends on provider, model, and vector metadata. Any config refactor that changes lineage composition without synchronized build and query logic will create baseline drift bugs.
- Across recent stories, the repo consistently prefers additive refactors over sweeping rewrites: preserve stable DTOs, update docs in `docs/cli-reference.md`, and add mirrored unit, integration, and e2e tests for every CLI-contract change.

### Latest Technical Information

- Pydantic's current `SecretStr` type redacts sensitive values in display and serialization output unless explicitly unwrapped. Inference: it is a strong fit for any future secret-bearing provider fields that must be present in config models but absent from operator output. [Source: https://docs.pydantic.dev/latest/api/types/#secretstr]
- Pydantic Settings still documents explicit source customization through `settings_customise_sources`. Inference: even if `codeman` keeps its custom loader, the story should preserve explicit, testable source order and avoid implicit secret-loading magic. [Source: https://docs.pydantic.dev/latest/concepts/pydantic_settings/#customise-settings-sources]
- Python's standard-library `tomllib` remains read-only and raises `TOMLDecodeError` for invalid TOML. Inference: protected local provider config should continue to be loaded through explicit parse-and-validate steps with fail-fast errors rather than permissive fallback behavior. [Source: https://docs.python.org/3/library/tomllib.html]

### Project Context Reference

- `docs/project-context.md` remains the canonical implementation ruleset: strict Pydantic boundary models, thin CLI handlers, deterministic behavior, runtime artifacts under `.codeman/`, and mirrored testing for touched behavior.
- `docs/architecture/decisions.md` and `docs/architecture/patterns.md` require the CLI-first layered flow to remain intact: `cli -> application -> ports -> infrastructure -> contracts/config/runtime`.
- No separate UX artifact exists for this project. For Story 3.2, the user-facing requirement is operational clarity: explicit provider selection, safe config inspection, and no accidental leakage of provider secrets or surprise provider activation.

### Project Structure Notes

- The architecture planning artifact suggests richer future config and provider infrastructure than the implemented repo currently has. Story 3.2 should fill the immediate gap only: a dedicated provider-config model and safe resolution path, not full profile persistence or external-provider execution.
- `src/codeman/config/` is the right home for configuration models and loader composition. `src/codeman/infrastructure/embeddings/` remains the right home for actual provider adapters and provider-side behavior.
- The current repo does not yet have `infrastructure/config/env_secret_loader.py` or provider registries from the architecture sketch. Add those seams only if the story truly needs them; otherwise keep the change focused and reviewable.
- Because semantic builds and queries already persist provider and model metadata, the new config split must not break build and query contract DTOs or semantic baseline lookup semantics.

### References

- [Source: docs/project-context.md]
- [Source: docs/README.md]
- [Source: docs/cli-reference.md - Config Commands; index build-semantic; query semantic]
- [Source: docs/architecture/decisions.md]
- [Source: docs/architecture/patterns.md]
- [Source: _bmad-output/planning-artifacts/epics.md - Epic 3; Story 3.2; Stories 3.3-3.6]
- [Source: _bmad-output/implementation-artifacts/3-1-define-the-layered-configuration-model.md]
- [Source: _bmad-output/planning-artifacts/architecture.md - Core Architectural Decisions; Data Architecture; Authentication & Security; Architectural Boundaries; Project Structure & Boundaries; Requirements to Structure Mapping]
- [Source: _bmad-output/planning-artifacts/prd.md - FR14-FR18; NFR7-NFR9; NFR15; NFR21; NFR26]
- [Source: pyproject.toml]
- [Source: src/codeman/config/models.py]
- [Source: src/codeman/config/defaults.py]
- [Source: src/codeman/config/loader.py]
- [Source: src/codeman/config/paths.py]
- [Source: src/codeman/config/semantic_indexing.py]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/cli/config.py]
- [Source: src/codeman/application/indexing/build_embeddings.py]
- [Source: src/codeman/application/indexing/build_semantic_index.py]
- [Source: src/codeman/application/query/run_semantic_query.py]
- [Source: src/codeman/application/ports/embedding_provider_port.py]
- [Source: src/codeman/infrastructure/embeddings/local_hash_provider.py]
- [Source: src/codeman/contracts/retrieval.py]
- [Source: tests/unit/config/test_loader.py]
- [Source: tests/unit/config/test_models.py]
- [Source: tests/unit/config/test_semantic_indexing.py]
- [Source: tests/unit/cli/test_config.py]
- [Source: tests/unit/application/test_build_semantic_index.py]
- [Source: tests/integration/indexing/test_build_semantic_index_integration.py]
- [Source: tests/e2e/test_config_show.py]
- [Source: tests/e2e/test_index_build_semantic.py]
- [Source: tests/e2e/test_query_semantic.py]
- [Source: git log --oneline -5]
- [Source: git show --stat --summary a37f5b6]
- [Source: git show --stat --summary c05aeea]
- [Source: git show --stat --summary 5966a34]
- [Source: https://docs.pydantic.dev/latest/api/types/#secretstr]
- [Source: https://docs.pydantic.dev/latest/concepts/pydantic_settings/#customise-settings-sources]
- [Source: https://docs.python.org/3/library/tomllib.html]

## Story Completion Status

- Status set to `done`.
- Completion note: `Separated provider-owned embedding config from semantic workflow settings, closed the post-review compatibility findings, and verified the local-hash workflow plus secret-safe operator surfaces with full regression coverage.`
- Recorded assumptions:
  - The safest implementation is to separate provider-owned settings from semantic and vector settings while preserving the current local-hash workflow.
  - Project defaults should continue to carry only non-secret defaults; provider secrets must come from environment or protected local config only.
  - Existing `CODEMAN_SEMANTIC_*` inputs are a compatibility surface that should be preserved or migrated explicitly and test-backed within this story.
  - External-provider execution remains out of scope; only the configuration seam should become provider-aware.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Debug Log References

- 2026-03-14: Story context generated via the `bmad-create-story` workflow for backlog story `3-2-configure-embedding-providers-independently`.
- 2026-03-14: Implemented the provider config split, semantic descriptor/fingerprint wiring, safe config inspection output, and secret-source validation.
- 2026-03-14: Addressed post-review compatibility findings for legacy file-based semantic config, additive `config show` JSON fields, and explicit-empty provider env overrides.
- 2026-03-14: Validation complete with `ruff check .`, `ruff format --check` on touched Python files, and full `pytest` (`222 passed`).
- 2026-03-14: Repo-wide `ruff format --check .` still reports unrelated pre-existing formatting drift outside Story 3.2; no additional story changes were required after confirming touched files are formatted.

### Completion Notes List

- Added `src/codeman/config/embedding_providers.py` and moved provider-owned fields out of `SemanticIndexingConfig`, while keeping provider selection and vector settings stable and allowing a provider-not-selected state.
- Extended layered config loading and project defaults to support separated provider tables, provider-scoped environment variables, legacy `CODEMAN_SEMANTIC_*` compatibility aliases, and fail-fast rejection of committed provider secrets.
- Refactored semantic build and query flows to derive provider lineage, fingerprints, and descriptors from the selected provider config without changing lexical behavior or runtime path semantics.
- Closed review findings by accepting legacy `[semantic_indexing]` provider-owned file keys, restoring additive `semantic_indexing.model_id|model_version|local_model_path` JSON compatibility fields, and allowing explicit-empty env overrides to clear lower-precedence provider values.
- Updated `config show`, docs, and automated coverage so secrets are never echoed in operator-visible or persisted surfaces; validated with full repo regression coverage (`222 passed`).

### File List

- _bmad-output/implementation-artifacts/3-2-configure-embedding-providers-independently.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- docs/cli-reference.md
- pyproject.toml
- src/codeman/application/indexing/build_embeddings.py
- src/codeman/application/indexing/build_semantic_index.py
- src/codeman/application/query/run_semantic_query.py
- src/codeman/bootstrap.py
- src/codeman/cli/config.py
- src/codeman/config/defaults.py
- src/codeman/config/embedding_providers.py
- src/codeman/config/loader.py
- src/codeman/config/models.py
- src/codeman/config/semantic_indexing.py
- tests/e2e/test_config_show.py
- tests/e2e/test_index_build_semantic.py
- tests/integration/indexing/test_build_semantic_index_integration.py
- tests/integration/query/test_compare_retrieval_modes_integration.py
- tests/integration/query/test_run_hybrid_query_integration.py
- tests/unit/application/test_build_semantic_index.py
- tests/unit/application/test_run_semantic_query.py
- tests/unit/cli/test_config.py
- tests/unit/config/test_embedding_providers.py
- tests/unit/config/test_loader.py
- tests/unit/config/test_models.py
- tests/unit/config/test_semantic_indexing.py

## Change Log

- 2026-03-14: Created comprehensive ready-for-dev story context for independent embedding-provider configuration.
- 2026-03-14: Implemented separated embedding provider configuration, secret-safe config inspection, semantic provider lineage refactor, and mirrored unit/integration/e2e coverage.
- 2026-03-14: Addressed post-review compatibility findings, reran full validation, and closed Story 3.2 as done.
