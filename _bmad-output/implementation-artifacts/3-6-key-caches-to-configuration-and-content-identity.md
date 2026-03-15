# Story 3.6: Key Caches to Configuration and Content Identity

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a maintainer,
I want cache reuse to depend on repository content and configuration identity,
so that codeman never reuses stale parser, chunk, or embedding artifacts incorrectly.

## Acceptance Criteria

1. Given parser, chunk, or embedding artifacts already exist, when codeman checks whether they can be reused, then cache decisions are based on content hashes and relevant configuration identity and embedding cache keys include provider identity, model version, and chunk serialization version.
2. Given a cache entry no longer matches the active repository or configuration context, when codeman evaluates reuse, then it rebuilds the affected artifacts instead of reusing stale outputs and the run metadata indicates whether artifacts were reused or regenerated.

## Tasks / Subtasks

- [x] Introduce deterministic cache identity builders and a dedicated runtime cache seam. (AC: 1, 2)
  - [x] Add canonical cache-key helpers for parser, chunk, and embedding reuse. Reuse `build_indexing_fingerprint(...)`, `build_semantic_indexing_fingerprint(...)`, provider attribution, and `CHUNK_SERIALIZATION_VERSION` instead of inventing another configuration-hash path.
  - [x] Prefer a dedicated cache boundary rooted in `.codeman/cache/` rather than overloading canonical snapshot artifacts under `.codeman/artifacts/` or adding ad hoc top-level folders.
  - [x] If parser outputs or reusable chunk templates need persistent serialization, define explicit DTOs under `src/codeman/contracts/` instead of pickling dataclasses or writing unvalidated dicts.

- [x] Make `index build-chunks` and `index reindex` reuse parser/chunk cache entries only when content and indexing identity match. (AC: 1, 2)
  - [x] Extend `BuildChunksUseCase` and/or `ChunkMaterializer` to consult cached parser outputs and reusable chunk material keyed by source content identity plus indexing fingerprint before reparsing and rechunking.
  - [x] Keep snapshot safety intact: chunk generation must still validate the live repository against the stored snapshot before any cache reuse, and reused outputs must be re-materialized into the current snapshot namespace instead of mutating prior snapshot artifacts.
  - [x] Rebuild when parser/chunker policy, fallback-vs-structural mode, chunk serialization version, or source content hash changes.

- [x] Reuse embedding artifacts only when the semantic input identity truly matches. (AC: 1, 2)
  - [x] Teach `BuildEmbeddingsStage` and `BuildSemanticIndexUseCase` to reuse cached embedding documents when the current semantic fingerprint and normalized chunk identity match.
  - [x] Ensure embedding cache keys include provider identity, model version, chunk serialization version, and enough chunk/span identity to distinguish multiple chunks produced from the same source file.
  - [x] Rebuild embeddings when provider/model/version, vector dimension, semantic fingerprint, or chunk content identity changes; do not treat an existing `documents.json` or vector artifact as a cache hit unless its recorded metadata still matches.

- [x] Surface cache reuse and regeneration truthfully in diagnostics and provenance. (AC: 2)
  - [x] Add additive cache summary fields to `ChunkGenerationDiagnostics`, `SemanticIndexBuildDiagnostics`, and any relevant `RunProvenanceWorkflowContext` so text/JSON output and `config provenance show` can tell what was reused vs regenerated.
  - [x] Keep `SuccessEnvelope.meta` unchanged and keep operator-safe cache details in `data`, diagnostics, or provenance rather than stderr-only status lines.
  - [x] Update `docs/cli-reference.md` for `index build-chunks`, `index build-semantic`, and `index reindex` to document cache reuse rules and current-configuration invalidation behavior.

- [x] Add mirrored automated coverage for cache-key correctness and stale-cache rejection. (AC: 1, 2)
  - [x] Add unit tests for deterministic cache-key generation and invalidation triggers.
  - [x] Add integration tests for repeated chunk and semantic builds, reindex reuse, and stale-artifact rejection after content or configuration drift.
  - [x] Add e2e tests proving current-configuration or profile changes force rebuilds and that diagnostics/provenance report reuse vs regeneration truthfully.

## Dev Notes

### Epic Context

- Epic 3 is the configuration, provenance, and repeatability foundation for later experimentation. Story 3.6 is where those identities start governing real cache reuse rather than just attribution.
- Story 1.6 already established safe chunk reuse across snapshots when source `content_hash` and `indexing_config_fingerprint` match. Story 3.6 should generalize that truthfulness to direct `build-chunks` runs and semantic embedding reuse without weakening snapshot immutability.
- Story 2.4 and Story 2.5 already bound semantic build/query behavior to persisted chunk artifacts plus `semantic_config_fingerprint`. Story 3.6 must preserve that same baseline discipline while reducing unnecessary recomputation.
- Story 3.4 and Story 3.5 already introduced `run_id`, `configuration_id`, workflow fingerprints, and selected-profile reuse lineage. Cache reuse should report through those same seams instead of inventing a second run-tracking channel.
- The planning docs explicitly call out parser-output caching even though current code does not yet persist parser boundaries. Treat that as a requirement for this story, but implement it in the smallest shape that fits the existing architecture.

### Current Repo State

- `src/codeman/runtime.py` already provisions `.codeman/cache/`, but no current use case or adapter stores parser, chunk, or embedding cache entries there.
- `src/codeman/application/indexing/build_chunks.py` always walks the full source inventory for the target snapshot and re-materializes chunk payloads. It records `indexing_config_fingerprint` on the snapshot, but it does not consult a reusable parser/chunk cache before calling `ChunkMaterializer`.
- `src/codeman/application/indexing/chunk_materializer.py` parses live source text and writes snapshot-local chunk payload artifacts. Structural parser boundaries are transient dataclasses today; they have no persistent cache representation.
- `src/codeman/application/repo/reindex_repository.py` can already clone unchanged chunk payloads from the latest indexed baseline when `content_hash` and `indexing_config_fingerprint` match. That is the strongest existing reuse pattern in code and should remain the truth baseline.
- `src/codeman/application/indexing/build_semantic_index.py` and `src/codeman/application/indexing/build_embeddings.py` always load chunk payloads, call the embedding provider, and rewrite `documents.json` for the snapshot/config pair. There is no cache-hit path for unchanged embedding inputs.
- `src/codeman/infrastructure/indexes/vector/sqlite_exact_builder.py` can report `refreshed_existing_artifact=True` when overwriting an existing vector file, but that is overwrite detection, not proof that embeddings were safely reused.
- `src/codeman/contracts/configuration.py` and `src/codeman/application/provenance/record_run_provenance.py` already persist configuration fingerprints and profile-reuse lineage, but they do not yet record parser/chunk/embedding reuse summaries.
- `build_chunk_id(...)` includes `source_file_id`, so the same unchanged file content cloned into a new snapshot gets a new `chunk_id`. Any cross-snapshot cache key based only on `chunk_id` will miss safe reuse or misclassify stale data.

### Previous Story Intelligence

- Story 3.5 tightened lexical baseline lookup to the current effective indexing fingerprint. Cache reuse in Story 3.6 must follow the same principle: "current configuration" means the selected profile plus layered CLI/environment overrides, not merely "latest artifact on disk".
- Story 3.4 introduced `run_id`, `configuration_id`, workflow-specific fingerprints, and `config provenance show`. Cache metadata should piggyback on those operator surfaces instead of creating a separate cache-inspection command.
- Story 3.3 and `src/codeman/config/retrieval_profiles.py` established canonical secret-safe configuration payload hashing. Cache identity should reuse those existing fingerprint builders rather than hashing raw environment state or ad hoc dicts.
- Story 2.4 established snapshot/config-scoped semantic build metadata, persisted embedding artifacts, and vector artifacts under `.codeman/indexes/vector/<repository-id>/<snapshot-id>/<semantic-config-fingerprint>/`.
- Story 2.5 established that semantic query stays artifact-only, configuration-aware, and truthful about missing baselines after snapshot or config drift. Story 3.6 must not weaken those failure guarantees.
- Story 1.6 proved that cloning immutable chunk payloads into a fresh snapshot namespace is safer than mutating prior snapshot artifacts in place.

### Cross-Story Baseline

- `index build-lexical`, `query lexical`, `query semantic`, `query hybrid`, and `compare query-modes` already depend on current fingerprint/baseline matching to reject stale artifacts. Cache reuse must not silently mask a baseline-missing or corruption condition those workflows already surface clearly.
- `RunProvenanceWorkflowContext` is workflow-specific and already persists as JSON, so additive cache summary fields can live there without introducing another mutable metadata table.
- `.codeman/artifacts/` holds canonical snapshot outputs, `.codeman/indexes/` holds built indexes, and `.codeman/cache/` should hold reusable intermediates. Do not blur those responsibilities.
- Reindex diagnostics already expose `source_files_reused` and `chunks_reused`. Story 3.6 should align new cache summary terminology with those existing counters instead of inventing a conflicting vocabulary.

### Technical Guardrails

- Keep the implementation CLI-first and local-first. Do not add remote caches, background workers, or speculative eval flows in this story. [Source: docs/project-context.md; docs/architecture/decisions.md; src/codeman/cli/eval.py]
- Do not use `chunk_id` alone as a cross-snapshot cache key. `build_chunk_id(...)` hashes `source_file_id`, so unchanged content in a new snapshot receives a different `chunk_id`. [Source: src/codeman/application/indexing/chunk_materializer.py]
- Do not use `source_content_hash` alone as an embedding cache key. It is file-scoped and one file can yield multiple chunks; embedding reuse must also include stable chunk/span/strategy identity plus `serialization_version`. [Source: src/codeman/contracts/chunking.py; src/codeman/contracts/retrieval.py]
- Preserve snapshot immutability. Reused artifacts must be copied or re-materialized into the current snapshot/build namespace; never rewrite prior snapshot artifacts or vector indexes in place to "update" them. [Source: _bmad-output/implementation-artifacts/1-6-re-index-after-source-or-configuration-changes.md; docs/project-context.md]
- Preserve the current fingerprint builders as the authoritative compatibility signals: `build_indexing_fingerprint(...)` for parser/chunker compatibility and `build_semantic_indexing_fingerprint(...)` plus provider/model attribution for semantic compatibility. [Source: src/codeman/config/indexing.py; src/codeman/config/semantic_indexing.py]
- Cache reuse must never bypass corruption checks. If a cached chunk payload, cached embedding document set, or vector artifact fails validation against recorded metadata, treat it as stale/corrupt and rebuild it. [Source: src/codeman/application/indexing/build_semantic_index.py; src/codeman/application/indexing/build_lexical_index.py; src/codeman/application/query/run_semantic_query.py]
- Keep cache artifacts secret-safe. Provider identity and model metadata may be visible, but raw secret-bearing config values must not be written into cache manifests, diagnostics, or provenance payloads. [Source: docs/project-context.md; _bmad-output/implementation-artifacts/3-2-configure-embedding-providers-independently.md]
- Keep generated state under `.codeman/` only. Use `.codeman/cache/` for reusable caches, `.codeman/artifacts/` for canonical snapshot artifacts, and `.codeman/indexes/` for built index files. [Source: docs/project-context.md; docs/architecture/patterns.md; src/codeman/runtime.py]
- Prefer additive DTO and diagnostic changes. Existing CLI JSON envelopes, result packages, and `run_id` behavior must remain backward-compatible for tests and automation. [Source: docs/project-context.md; docs/cli-reference.md; src/codeman/contracts/chunking.py; src/codeman/contracts/retrieval.py]
- Do not auto-rebuild missing baselines inside query commands just because a cache exists. Query workflows remain truthful read operations; cache reuse belongs in build/indexing paths. [Inference from current query command contracts and Story 2.5 / Story 3.5 behavior]

### Implementation Notes

- Preferred architecture: add a dedicated cache port/adapter rooted in `.codeman/cache/` rather than overloading `ArtifactStorePort`, because snapshot artifacts are canonical outputs while caches are reusable intermediates with different invalidation rules.
- If parser boundaries need persistent serialization, introduce explicit machine-readable DTOs for cached parser outputs instead of serializing raw `StructuralBoundary` dataclasses implicitly. Inference: this keeps cache payloads strict, debuggable, and versionable.
- A practical cache-identity pattern is to build canonical JSON descriptors and hash them with sorted keys:
  - parser cache key: language, relevant parser policy identity, and source content identity
  - chunk cache key: source identity, indexing fingerprint, chunk serialization version, and stable boundary/strategy identity
  - embedding cache key: semantic fingerprint, provider/model identity, vector dimension, chunk serialization version, and stable chunk/span/content identity
  Inference: this keeps keys deterministic and traceable while reusing existing fingerprint builders.
- For cross-snapshot embedding reuse, derive identity from normalized chunk content/span metadata rather than `chunk_id`, because `chunk_id` changes whenever `source_file_id` changes on reindex.
- Keep cache lookup close to build orchestration:
  - `BuildChunksUseCase` and `ChunkMaterializer` decide parser/chunk reuse
  - `BuildEmbeddingsStage` and `BuildSemanticIndexUseCase` decide embedding reuse
  - `RecordRunConfigurationProvenanceUseCase` records what happened
  Avoid spreading cache decisions across CLI handlers or query-only code.
- Reuse existing artifact readers and validation helpers where possible. Cached embedding documents should still validate through `SemanticEmbeddingArtifactDocument`, and cached chunk payloads should remain consistent with `ChunkPayloadDocument`.
- `SemanticIndexBuildDiagnostics.refreshed_existing_artifact` should not be repurposed to mean cache hit. If cache reuse becomes visible, add a separate explicit field instead of changing the meaning of an existing one.
- Prefer explicit counters/booleans that are easy to assert in tests, for example cache-hit and regenerated counts, rather than free-form text. Inference: mirrored unit/e2e coverage will be simpler and the CLI contract will stay machine-readable.
- If the implementation needs durable cache manifests, keep them as filesystem JSON under `.codeman/cache/` by default and reuse current Pydantic JSON-mode serialization rules. Avoid a new SQLite table unless a concrete queryable cache-use case appears. Inference from current architecture and runtime boundaries.

### File Structure Requirements

- Existing files to extend:
  - `src/codeman/bootstrap.py`
  - `src/codeman/runtime.py`
  - `src/codeman/cli/index.py`
  - `src/codeman/config/indexing.py`
  - `src/codeman/config/semantic_indexing.py`
  - `src/codeman/contracts/chunking.py`
  - `src/codeman/contracts/retrieval.py`
  - `src/codeman/contracts/configuration.py`
  - `src/codeman/application/indexing/build_chunks.py`
  - `src/codeman/application/indexing/chunk_materializer.py`
  - `src/codeman/application/indexing/build_embeddings.py`
  - `src/codeman/application/indexing/build_semantic_index.py`
  - `src/codeman/application/repo/reindex_repository.py`
  - `src/codeman/application/provenance/record_run_provenance.py`
  - `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py`
  - `docs/cli-reference.md`
- Likely new files for this story:
  - `src/codeman/contracts/cache.py`
  - `src/codeman/config/cache_identity.py`
  - `src/codeman/application/ports/cache_store_port.py`
  - `src/codeman/infrastructure/cache/filesystem_cache_store.py`
- Likely tests to add or extend:
  - `tests/unit/config/test_cache_identity.py`
  - `tests/unit/application/test_build_chunks.py`
  - `tests/unit/application/test_build_semantic_index.py`
  - `tests/unit/application/test_reindex_repository.py`
  - `tests/unit/application/test_record_run_provenance.py`
  - `tests/unit/cli/test_index.py`
  - `tests/integration/indexing/test_build_chunks_integration.py`
  - `tests/integration/indexing/test_build_semantic_index_integration.py`
  - `tests/e2e/test_index_build_chunks.py`
  - `tests/e2e/test_index_build_semantic.py`
  - `tests/e2e/test_index_reindex.py`
  - `tests/e2e/test_run_provenance.py`

### Testing Requirements

- Add unit tests for deterministic parser/chunk/embedding cache-key generation, including stable ordering and the negative case that `chunk_id` alone is not reusable across snapshots.
- Add unit tests proving parser/chunk cache reuse only occurs when source content and indexing identity match, and that changes to `CHUNK_SERIALIZATION_VERSION`, parser/chunker policy identity, or `fingerprint_salt` invalidate prior cache entries.
- Add unit tests proving embedding reuse occurs only when semantic fingerprint, provider/model lineage, vector dimension, and normalized chunk identity still match, and that model-version or serialization-version drift forces regeneration.
- Add unit tests proving corrupt or missing cached parser/chunk/embedding artifacts fall back to rebuild rather than silently reporting a cache hit.
- Add integration tests for repeated `build-chunks` runs against the same snapshot/config and for `reindex` reuse across snapshots with unchanged content, verifying cache summaries and immutable snapshot artifact namespaces.
- Add integration tests for repeated `build-semantic` runs against the same snapshot/config, profile-driven config drift, and changed chunk serialization/version inputs so cached embedding documents are reused only when safe.
- Add CLI tests for text and JSON output to ensure cache summaries are rendered predictably without polluting `stdout` JSON envelopes.
- Add provenance tests proving `config provenance show <run-id>` exposes cache reuse vs regeneration fields consistently for chunk, semantic, and reindex workflows.
- Keep using `CliRunner` for CLI unit tests and `subprocess.run(..., check=False)` with temporary workspaces for e2e flows. Continue using workspace-local `.local/uv-cache` when `uv` is invoked. [Source: docs/project-context.md]

### Git Intelligence Summary

- Commit `4d51962` (`story(3-5-reuse-prior-configurations-in-later-experiments): complete code review and mark done`) is the immediate baseline. It shows the repo's preferred pattern for cross-cutting behavior: additive contract changes, one central provenance seam, docs updates in `docs/cli-reference.md`, and mirrored unit/integration/e2e coverage.
- Commit `c63fb6e` (`story(3-4): finalize run configuration provenance`) matters because Story 3.6 needs to reuse the existing run-provenance path for cache summaries instead of inventing a second persistence channel.
- Commit `8c0fb68` (`feat: add retrieval strategy profiles`) matters because the current effective configuration may come from `--profile` plus later overrides. Cache invalidation must honor the same resolved-config path used there.
- Commit `91fd05e` (`story(3-2): configure embedding providers independently`) reinforces two embedding-cache guardrails: provider-owned settings remain separate from semantic workflow settings, and any persisted/operator-visible surface must stay secret-safe.
- Commit `a37f5b6` (`story(3-1-define-the-layered-configuration-model): complete code review and mark done`) established the authoritative loader precedence. Story 3.6 should derive cache identity from the final resolved config rather than from ad hoc environment inspection.

### Latest Technical Information

- As of March 15, 2026, Pydantic's latest official docs still document `ConfigDict` for strict model behavior and `model_dump(mode="json")` for JSON-mode serialization. Inference: cached parser/embedding manifests and cache-key descriptors should use strict DTOs and JSON-mode dumps before hashing or persistence. [Source: https://docs.pydantic.dev/latest/api/config/; https://docs.pydantic.dev/latest/concepts/serialization/]
- Python's standard-library `json` docs still document `sort_keys=True` and compact separators for deterministic JSON output. Inference: cache-identity descriptors should use canonical sorted JSON so the same cache key is produced across runs and platforms. [Source: https://docs.python.org/3/library/json.html]
- SQLAlchemy 2.0 Core metadata docs and Alembic operations docs continue to center explicit `Table` / `Column` definitions and migration ops such as `create_table()` and `add_column()`. Inference: if the implementation later needs persisted cache metadata beyond filesystem JSON, it should reuse the existing SQLAlchemy/Alembic path rather than ad hoc `sqlite3` DDL. [Source: https://docs.sqlalchemy.org/en/20/core/metadata.html; https://alembic.sqlalchemy.org/en/latest/ops.html]
- The project remains pinned to the versions documented in `docs/project-context.md` and current dependency constraints. Story 3.6 should preserve those pins and avoid bundling unrelated library upgrades with cache work. [Source: docs/project-context.md]

### Project Context Reference

- `docs/project-context.md` remains the canonical implementation ruleset: strict Pydantic boundary models, thin CLI handlers, deterministic behavior, runtime artifacts under `.codeman/`, and mirrored automated coverage for touched behavior.
- `docs/architecture/decisions.md` and `docs/architecture/patterns.md` require the CLI-first layered flow to remain intact: `cli -> application -> ports -> infrastructure -> contracts/config/runtime`.
- `docs/cli-reference.md` owns the supported CLI contract and must be updated whenever cache summaries or current-configuration invalidation behavior changes.
- No separate UX artifact exists for this project. For Story 3.6, the user-facing requirement is operational clarity: maintainers must be able to tell which artifacts were reused vs regenerated without exposing secrets or reverse-engineering `.codeman/` manually.

### Project Structure Notes

- `.codeman/cache/` already exists but is currently unused. Story 3.6 is the first story that should give it a concrete, bounded responsibility.
- Current snapshot artifacts and index artifacts are already scoped by snapshot/config. Reusable caches should not replace those canonical outputs; they should only accelerate rebuilds while preserving existing attribution and baseline behavior.
- The planning docs mention parser-output caching, but current code never persists parser boundaries. Keep the implementation minimal and explicit rather than inventing a generic distributed cache framework.
- No benchmark/eval implementation belongs here. `src/codeman/cli/eval.py` remains a placeholder Typer group and should stay that way in this story.

### References

- [Source: docs/project-context.md]
- [Source: docs/README.md]
- [Source: docs/cli-reference.md - Index Commands; Config Commands]
- [Source: docs/architecture/decisions.md]
- [Source: docs/architecture/patterns.md]
- [Source: _bmad-output/planning-artifacts/epics.md - Epic 3; Story 3.6]
- [Source: _bmad-output/planning-artifacts/prd.md - Retrieval Configuration & Experiment Control; NFR10-NFR20]
- [Source: _bmad-output/planning-artifacts/architecture.md - Caching Strategy; Data Architecture; Project Structure & Boundaries]
- [Source: _bmad-output/implementation-artifacts/1-6-re-index-after-source-or-configuration-changes.md]
- [Source: _bmad-output/implementation-artifacts/2-4-build-semantic-retrieval-index-artifacts.md]
- [Source: _bmad-output/implementation-artifacts/2-5-run-semantic-retrieval-queries.md]
- [Source: _bmad-output/implementation-artifacts/3-3-create-reusable-retrieval-strategy-profiles.md]
- [Source: _bmad-output/implementation-artifacts/3-4-record-configuration-provenance-for-every-run.md]
- [Source: _bmad-output/implementation-artifacts/3-5-reuse-prior-configurations-in-later-experiments.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: src/codeman/runtime.py]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/cli/index.py]
- [Source: src/codeman/application/indexing/build_chunks.py]
- [Source: src/codeman/application/indexing/chunk_materializer.py]
- [Source: src/codeman/application/indexing/build_embeddings.py]
- [Source: src/codeman/application/indexing/build_semantic_index.py]
- [Source: src/codeman/application/indexing/build_vector_index.py]
- [Source: src/codeman/application/repo/reindex_repository.py]
- [Source: src/codeman/application/provenance/record_run_provenance.py]
- [Source: src/codeman/application/ports/parser_port.py]
- [Source: src/codeman/application/ports/artifact_store_port.py]
- [Source: src/codeman/contracts/chunking.py]
- [Source: src/codeman/contracts/retrieval.py]
- [Source: src/codeman/contracts/repository.py]
- [Source: src/codeman/contracts/configuration.py]
- [Source: src/codeman/config/indexing.py]
- [Source: src/codeman/config/semantic_indexing.py]
- [Source: src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- [Source: src/codeman/infrastructure/indexes/vector/sqlite_exact_builder.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/tables.py]
- [Source: tests/unit/application/test_build_chunks.py]
- [Source: tests/unit/application/test_build_semantic_index.py]
- [Source: tests/unit/application/test_reindex_repository.py]
- [Source: tests/unit/application/test_record_run_provenance.py]
- [Source: tests/unit/cli/test_index.py]
- [Source: tests/integration/indexing/test_build_semantic_index_integration.py]
- [Source: tests/e2e/test_index_build_chunks.py]
- [Source: tests/e2e/test_index_build_semantic.py]
- [Source: tests/e2e/test_index_reindex.py]
- [Source: tests/e2e/test_run_provenance.py]
- [Source: git log --oneline -5]
- [Source: git show --stat --summary 4d51962]
- [Source: git show --stat --summary c63fb6e]
- [Source: git show --stat --summary 8c0fb68]
- [Source: git show --stat --summary 91fd05e]
- [Source: git show --stat --summary a37f5b6]
- [Source: https://docs.pydantic.dev/latest/api/config/]
- [Source: https://docs.pydantic.dev/latest/concepts/serialization/]
- [Source: https://docs.python.org/3/library/json.html]
- [Source: https://docs.sqlalchemy.org/en/20/core/metadata.html]
- [Source: https://alembic.sqlalchemy.org/en/latest/ops.html]

## Story Completion Status

- Status set to `done`.
- Completion note: `Implemented filesystem-backed parser/chunk/embedding cache reuse with deterministic identities, additive diagnostics/provenance summaries, docs updates, mirrored unit/integration/e2e coverage, and resolved the follow-up code review findings before closure.`
- Recorded assumptions:
  - The preferred implementation uses filesystem-backed cache manifests under `.codeman/cache/` instead of new mutable SQLite tables unless a concrete queryable cache use case appears.
  - Cache identity derives from the final resolved effective configuration after selected-profile, CLI, and environment overrides are applied.
  - Cross-snapshot embedding reuse must key off normalized chunk content/span identity rather than `chunk_id`, because `chunk_id` changes with `source_file_id`.
  - Vector artifacts may still be rebuilt even when embedding documents are reused; if so, that behavior should be reported explicitly rather than conflated with cache-hit semantics.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Implementation Plan

- Introduce strict cache DTOs plus deterministic cache-identity helpers, then wire a filesystem-backed cache adapter through `bootstrap.py`.
- Integrate cache lookup and invalidation into `build-chunks`, `reindex`, and semantic embedding/build orchestration without weakening snapshot or provenance truthfulness.
- Surface reuse/regeneration summaries through diagnostics, provenance, docs, and mirrored tests before implementation is considered complete.

### Debug Log References

- `2026-03-15 10:54:33 +0200` Updated sprint status to `in-progress` and aligned implementation with the ready-for-dev story order.
- `2026-03-15 11:33:32 +0200` Added cache DTOs, cache identity helpers, filesystem cache adapter, and cache-aware build/reindex orchestration.
- `2026-03-15 11:33:32 +0200` Added additive cache summaries to chunk/semantic/reindex diagnostics and run provenance, then updated CLI output/docs.
- `2026-03-15 11:33:32 +0200` Added unit, integration, and e2e coverage for deterministic cache keys, cache reuse, invalidation, and provenance reporting.
- `2026-03-15 11:48:39 +0200` Resolved code review findings for fallback-cache recovery, truncated embedding-cache rejection, and truthful reindex provenance reuse counters before marking the story done.

### Completion Notes

- Implemented a dedicated `.codeman/cache/` seam with strict parser, chunk, and embedding cache artifacts plus deterministic identity helpers under `src/codeman/config/cache_identity.py`.
- Taught `build-chunks` to reuse chunk drafts and parser boundaries safely, re-materializing snapshot-local chunk payloads without mutating prior snapshot artifacts.
- Taught semantic builds to reuse embedding vectors via snapshot-independent normalized chunk identity while keeping canonical `documents.json` and vector artifacts snapshot-scoped outputs.
- Surfaced truthful cache reuse/regeneration summaries in CLI diagnostics, JSON output, and `config provenance show`.
- Fixed the post-review edge cases so fallback chunk cache upgrades to structural output when parsing recovers, schema-valid truncated embedding caches are rejected, and reindex provenance now records source/chunk reuse counters even on no-op runs.
- Added mirrored automated coverage across unit, integration, and e2e layers for stable keys, repeated-build reuse, configuration invalidation, corrupt-cache fallback, and provenance visibility.

## File List

- `_bmad-output/implementation-artifacts/3-6-key-caches-to-configuration-and-content-identity.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/cli-reference.md`
- `src/codeman/application/indexing/build_chunks.py`
- `src/codeman/application/indexing/build_embeddings.py`
- `src/codeman/application/indexing/build_semantic_index.py`
- `src/codeman/application/indexing/chunk_materializer.py`
- `src/codeman/application/ports/cache_store_port.py`
- `src/codeman/application/repo/reindex_repository.py`
- `src/codeman/bootstrap.py`
- `src/codeman/cli/index.py`
- `src/codeman/config/cache_identity.py`
- `src/codeman/contracts/cache.py`
- `src/codeman/contracts/chunking.py`
- `src/codeman/contracts/configuration.py`
- `src/codeman/contracts/reindexing.py`
- `src/codeman/contracts/retrieval.py`
- `src/codeman/infrastructure/cache/filesystem_cache_store.py`
- `tests/e2e/test_index_build_chunks.py`
- `tests/e2e/test_index_build_semantic.py`
- `tests/e2e/test_index_reindex.py`
- `tests/e2e/test_run_provenance.py`
- `tests/integration/indexing/test_build_chunks_integration.py`
- `tests/integration/indexing/test_build_semantic_index_integration.py`
- `tests/unit/application/test_build_chunks.py`
- `tests/unit/application/test_build_semantic_index.py`
- `tests/unit/application/test_reindex_repository.py`
- `tests/unit/config/test_cache_identity.py`

## Change Log

- `2026-03-15`: Implemented Story 3.6 with filesystem-backed cache reuse for parser/chunk/embedding workflows, additive diagnostics/provenance summaries, CLI/docs updates, and mirrored automated coverage.
- `2026-03-15`: Resolved code review findings for fallback cache invalidation, embedding cache corruption rejection, and truthful reindex provenance reuse reporting; validated the story and marked it done.
