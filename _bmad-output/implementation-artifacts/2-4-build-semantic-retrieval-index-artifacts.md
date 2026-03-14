# Story 2.4: Build Semantic Retrieval Index Artifacts

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want codeman to generate embedding-ready retrieval artifacts and a vector index,
so that I can run semantic queries over the same repository corpus.

## Acceptance Criteria

1. Given a repository with structured chunks, when semantic indexing is run, then codeman creates embedding documents from chunk data, records provider and model metadata, and builds a vector index for querying, and stores enough run metadata to attribute the index to a specific configuration.
2. Given no external embedding provider is configured, when semantic indexing requires provider-backed embeddings, then codeman fails with a clear, user-safe diagnostic or uses an explicitly configured local path, and does not silently send repository data to an external service.

## Tasks / Subtasks

- [x] Introduce the semantic-index build contracts, ports, and CLI surface. (AC: 1, 2)
  - [x] Add focused request/result/diagnostics DTOs plus stable error codes for semantic builds in `src/codeman/contracts/retrieval.py` and `src/codeman/contracts/errors.py`, including provider/model attribution and operator-safe failure shapes.
  - [x] Introduce the missing semantic boundaries in `src/codeman/application/ports/`, at minimum an embedding-provider port and a vector-index port, without leaking provider or vector-backend details into CLI modules.
  - [x] Add a thin CLI command in `src/codeman/cli/index.py` for `uv run codeman index build-semantic <snapshot-id>` with `--output-format json`, and wire the orchestration through `src/codeman/bootstrap.py`.
  - [x] Keep the CLI-facing orchestration as one use case, but separate the embedding stage from the vector-index stage clearly enough that Stories 2.5 and 3.x can reuse those boundaries instead of reverse-engineering one large monolith.

- [x] Build embedding documents from persisted chunk metadata and payload artifacts only. (AC: 1, 2)
  - [x] Reuse `ChunkStorePort.list_by_snapshot()` plus persisted chunk payload JSON from `FilesystemArtifactStore.read_chunk_payload()`; do not rescan the repository, reread live source files, or rerun chunk generation.
  - [x] Define a normalized embedding-document shape that remains traceable to `chunk_id`, `snapshot_id`, `repository_id`, `relative_path`, `language`, `strategy`, span metadata, source-content hash, and chunk serialization version.
  - [x] Persist embedding-ready artifacts under runtime-managed paths so semantic builds remain attributable and repeatable; keep generated state under `.codeman/` and outside the indexed repository.
  - [x] Generate embeddings in deterministic chunk order and capture the provider identity, model name/version, vector dimension, and any local-vs-external provider signal needed for later query and benchmark attribution.

- [x] Build attributable vector index artifacts without dragging Epic 3 fully forward. (AC: 1, 2)
  - [x] Add a narrow semantic build metadata persistence path, preferably as a dedicated semantic/vector index-build table and repository, rather than forcing a risky cross-epic refactor of the current lexical-only build store.
  - [x] Record enough semantic build metadata to resolve the correct current artifact later: repository id, snapshot id, revision identity/source, semantic configuration fingerprint, provider id, model id/version, vector engine id, document count, embedding dimension, artifact path, and creation timestamp.
  - [x] Keep freshness snapshot-scoped and configuration-aware so semantic queries never run against stale artifacts from an older snapshot, provider, model, or embedding-policy version.
  - [x] If the exact ANN backend choice remains unresolved, prefer a deterministic exact-search baseline artifact behind the vector-index port rather than hard-coding a heavyweight backend into the first implementation.

- [x] Keep provider usage explicit, local-first, and operator-visible. (AC: 1, 2)
  - [x] Provide an explicitly configured local path for embeddings or fail clearly with a stable error such as `embedding_provider_unavailable`; never auto-enable OpenAI or another external provider just because semantic indexing was requested.
  - [x] Surface provider/model usage in text output, JSON output, and persisted build metadata so operators can see whether repository content stayed local or was sent to an external service.
  - [x] Keep secrets out of source control, artifacts, and logs; resolve them only through explicit runtime configuration or environment variables.
  - [x] Defer reusable provider profiles, layered config resolution, semantic query execution, hybrid fusion, compare flows, and benchmark provenance beyond build-level attribution to Stories 2.5, 2.6, 2.7, and Epic 3.

- [x] Update docs and add mirrored automated coverage. (AC: 1, 2)
  - [x] Update `docs/cli-reference.md` with the semantic build command, the expected attribution fields, and the explicit provider/failure behavior.
  - [x] Add unit coverage for deterministic embedding-document assembly, provider gating, semantic configuration fingerprinting, and stable error mapping.
  - [x] Add integration coverage proving semantic indexing reads persisted chunk artifacts instead of the live repository, persists attributable build metadata, and resolves freshness across snapshots/config changes.
  - [x] Add e2e coverage for the semantic build CLI in both text and JSON modes using a deterministic local/fake embedding adapter so CI does not depend on network calls or model downloads.

## Dev Notes

### Previous Story Intelligence

- Story 2.1 already established the approved build-artifact pattern for retrieval indexing: a snapshot-scoped artifact under `.codeman/indexes/`, a dedicated build-metadata table, and repository/snapshot freshness lookup that avoids stale artifacts.
- Story 2.2 added the repository-scoped query lookup pattern and made it clear that retrieval commands must never rebuild indexes implicitly inside the query path.
- Story 2.3 established the shared agent-friendly retrieval package and made lexical formatting reusable. Story 2.4 must create semantic artifacts that later semantic and hybrid query stories can plug into that same package instead of inventing a second output contract.
- Upstream indexing stories already persist the exact inputs semantic indexing should use: `ChunkRecord` rows plus chunk payload JSON artifacts with stable ids, spans, strategies, and source-content hashes.
- Recent implementation history favors additive, narrowly scoped changes: one new use case, thin Typer commands, explicit ports/adapters, `bootstrap.py` wiring, and mirrored unit/integration/e2e coverage.

### Current Repo State

- The current codebase has no implemented semantic indexing, vector indexing, embedding-provider, semantic-query, or hybrid-query modules yet. In production code, the only semantic signal today is `RetrievalMode = Literal["lexical", "semantic", "hybrid"]` in `src/codeman/contracts/retrieval.py`.
- `src/codeman/bootstrap.py` wires repository registration, snapshot creation, source extraction, chunk generation, lexical index building, lexical query execution, and re-indexing only. No semantic pipeline is currently composed.
- `src/codeman/cli/index.py` documents `extract-sources`, `build-chunks`, `build-lexical`, and `reindex` only. There is no semantic build command yet.
- `src/codeman/application/ports/index_build_store_port.py` and `src/codeman/infrastructure/persistence/sqlite/repositories/index_build_repository.py` are lexical-specific today. The current schema has `lexical_index_builds` only.
- `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py` persists snapshot manifests and chunk payload JSON only. There is no embedding artifact writer/reader yet.
- `pyproject.toml` currently ships only Alembic, Pydantic, SQLAlchemy, and Typer. There is no embedding or vector dependency in the repo yet, so Story 2.4 must introduce any new dependency deliberately and keep the change localized.
- `docs/project-context.md` explicitly warns not to treat semantic retrieval, hybrid retrieval, or external-provider flows as already implemented just because they exist in planning artifacts.

### Technical Guardrails

- Keep the public interface CLI-only. This story must not introduce HTTP endpoints, MCP transport, background workers, or daemonized embedding services. [Source: docs/architecture/decisions.md; _bmad-output/planning-artifacts/prd.md - Project Classification; _bmad-output/planning-artifacts/architecture.md - API Boundaries]
- Preserve the established layering: CLI parses and renders, application orchestrates, infrastructure owns provider/vector-backend behavior, contracts remain the machine-readable DTO layer, and `bootstrap.py` is the single composition root. [Source: docs/architecture/patterns.md; docs/project-context.md; src/codeman/bootstrap.py]
- Build semantic artifacts only from persisted chunk rows and chunk payload artifacts. Do not rescan the repository tree, reread mutable working-tree files, or rerun parsers/chunkers in the semantic build path. [Source: docs/project-context.md; src/codeman/contracts/chunking.py; src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- Keep all generated semantic state under `.codeman/`. A pragmatic split is embedding documents under `.codeman/artifacts/snapshots/<snapshot-id>/embeddings/` and vector-index artifacts under `.codeman/indexes/vector/<repository-id>/<snapshot-id>/`. [Source: docs/project-context.md; docs/architecture/patterns.md; src/codeman/runtime.py]
- Do not silently enable external providers. If semantic indexing would require sending repository content to a provider and no explicit opt-in configuration exists, fail with a stable, user-safe error instead of falling through to a hidden network path. [Source: docs/project-context.md; docs/architecture/decisions.md; _bmad-output/planning-artifacts/epics.md - Story 2.4; _bmad-output/planning-artifacts/prd.md - NFR6, NFR7, NFR8]
- Keep provider/model metadata visible everywhere that matters: build result DTOs, persisted metadata rows, and human-readable command output. This is a product requirement, not optional logging sugar. [Source: _bmad-output/planning-artifacts/prd.md - Measurable Outcomes; NFR11; NFR15]
- Do not pull the full Epic 3 configuration model into Story 2.4. A narrow explicit request/config path for provider id, model id/version, and local model path is enough for this story if it stays deterministic and validated. Reusable profiles, layered config, and provenance reuse belong to Stories 3.1-3.5. [Source: _bmad-output/planning-artifacts/epics.md - Story 2.4; Story 3.1; Story 3.2; Story 3.3; Story 3.4; Story 3.5]
- Do not refactor the current lexical-specific build plumbing into a giant generalized abstraction unless the change remains small and clearly improves Story 2.4. A dedicated semantic/vector build table and repository is acceptable if it keeps the diff localized. Inference based on the current code shape and the repo's incremental-change discipline. [Source: docs/project-context.md; docs/architecture/patterns.md; src/codeman/application/ports/index_build_store_port.py; src/codeman/infrastructure/persistence/sqlite/tables.py]
- Keep JSON mode clean on `stdout` and progress/diagnostics on `stderr`. Reuse the shared success/failure envelopes instead of inventing a semantic-only JSON shape. [Source: docs/project-context.md; docs/cli-reference.md; src/codeman/cli/common.py]
- Preserve deterministic ordering and reproducible attribution. Build embedding documents in stable chunk order and include the semantic-policy fingerprint, provider identity, model version, and snapshot identity in persisted metadata so later comparison and query flows can explain exactly which artifact they used. [Source: docs/project-context.md; _bmad-output/planning-artifacts/prd.md - NFR10, NFR11; _bmad-output/planning-artifacts/architecture.md - Reproducibility; Data Architecture]
- Do not implement semantic query execution, hybrid fusion, compare workflows, or benchmark/judge features in this story. Those belong to Stories 2.5, 2.6, 2.7, and Epic 4. [Source: _bmad-output/planning-artifacts/epics.md - Story 2.5; Story 2.6; Story 2.7; Epic 4]

### File / Structure Guidance

- Preferred new or expanded files for this story:
  - `src/codeman/application/indexing/build_semantic_index.py` or an equivalent thin orchestration entrypoint that clearly separates embedding generation from vector-index construction
  - `src/codeman/application/indexing/build_embeddings.py`
  - `src/codeman/application/indexing/build_vector_index.py`
  - `src/codeman/application/ports/embedding_provider_port.py`
  - `src/codeman/application/ports/vector_index_port.py`
  - `src/codeman/application/ports/semantic_index_build_store_port.py`
  - `src/codeman/bootstrap.py`
  - `src/codeman/cli/index.py`
  - `src/codeman/contracts/retrieval.py`
  - `src/codeman/contracts/errors.py`
  - `src/codeman/config/semantic_indexing.py` or a very small additive extension to the current config layer
  - `src/codeman/infrastructure/embeddings/__init__.py`
  - `src/codeman/infrastructure/embeddings/local_sentence_transformer_provider.py` or another explicitly local adapter if a local baseline is chosen
  - `src/codeman/infrastructure/indexes/vector/__init__.py`
  - `src/codeman/infrastructure/indexes/vector/<chosen_backend>.py`
  - `src/codeman/infrastructure/persistence/sqlite/tables.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/semantic_index_build_repository.py`
  - `docs/cli-reference.md`
  - `migrations/versions/<timestamp>_create_semantic_index_builds_table.py`
  - `tests/unit/application/test_build_semantic_index.py`
  - `tests/unit/cli/test_index.py`
  - `tests/unit/infrastructure/test_<chosen_embedding_provider>.py`
  - `tests/unit/infrastructure/test_<chosen_vector_backend>.py`
  - `tests/integration/indexing/test_build_semantic_index_integration.py`
  - `tests/e2e/test_index_build_semantic.py`
- A pragmatic first CLI surface is:
  - `uv run codeman index build-semantic <snapshot-id>`
  - `uv run codeman index build-semantic <snapshot-id> --output-format json`
- A pragmatic semantic build result shape is:
  - `repository`
  - `snapshot`
  - `build`
  - `provider`
  - `diagnostics`
- A pragmatic semantic build metadata row shape is:
  - `id`
  - `repository_id`
  - `snapshot_id`
  - `revision_identity`
  - `revision_source`
  - `semantic_config_fingerprint`
  - `provider_id`
  - `model_id`
  - `model_version`
  - `is_external_provider`
  - `vector_engine`
  - `document_count`
  - `embedding_dimension`
  - `artifact_path`
  - `created_at`
- A pragmatic embedding-document artifact shape is:
  - `chunk_id`
  - `snapshot_id`
  - `repository_id`
  - `relative_path`
  - `language`
  - `strategy`
  - `start_line`
  - `end_line`
  - `start_byte`
  - `end_byte`
  - `source_content_hash`
  - `serialization_version`
  - `provider_id`
  - `model_id`
  - `model_version`
  - `vector_dimension`
  - `embedding`
- If the initial vector backend is an exact-search baseline rather than an ANN engine, keep that behind `VectorIndexPort` and persist a deterministic artifact plus metadata so later backends can swap in without rewriting CLI or application flows.

### Testing Guidance

- Use pytest across unit, integration, and e2e layers and keep the temp-workspace isolation pattern already used by Stories 2.1-2.3. [Source: docs/project-context.md; _bmad-output/implementation-artifacts/2-1-build-lexical-index-artifacts.md; _bmad-output/implementation-artifacts/2-2-run-lexical-retrieval-against-indexed-chunks.md; _bmad-output/implementation-artifacts/2-3-present-agent-friendly-ranked-retrieval-results.md]
- Add unit coverage for deterministic embedding-document assembly, provider/model attribution, semantic configuration fingerprint generation, and stable error mapping for missing snapshots, missing chunk baselines, missing payload artifacts, missing provider configuration, and corrupt embedding/vector artifacts.
- Add infrastructure tests for the chosen local provider and chosen vector backend, including dimension consistency, deterministic artifact writing, and operator-safe failures when the backend cannot initialize.
- Add integration coverage proving semantic indexing reads persisted chunk payload artifacts instead of the live repository: mutate a source file after chunking and verify the semantic build still reflects the stored snapshot/chunk artifacts until a new snapshot is created.
- Add integration coverage for freshness: build semantic artifacts for one snapshot, create a new snapshot or semantic configuration fingerprint, rebuild, and prove later lookups prefer the current snapshot/config artifact rather than the older one.
- Add a failure-path test where no explicit provider is configured and verify the command exits with a stable error without attempting any external call.
- Add e2e coverage for `uv run codeman index build-semantic ...` in text and JSON modes using a deterministic fake/local embedding adapter so CI stays local-first and reproducible.
- Do not make CI depend on downloading large models or hitting provider APIs. If a real provider-backed smoke test is ever added later, it should be opt-in and out of the default repository test suite. Inference based on the repo's local-first contract and current dev workflow. [Source: docs/project-context.md; _bmad-output/planning-artifacts/prd.md - NFR5, NFR6, NFR8]

### Git Intelligence Summary

- Recent implementation history continues to favor additive, narrow changes: introduce a focused use case, wire it through `bootstrap.py`, keep CLI handlers thin, and back the change with mirrored unit/integration/e2e coverage.
- Commit `0f0f4c1` (`story(2-3-present-agent-friendly-ranked-retrieval-results): complete code review and mark done`) matters because Story 2.4 should prepare semantic artifacts that later semantic/hybrid queries can package through the same retrieval result shape instead of inventing a separate semantic-only presentation layer.
- Commit `8de17fc` (`story(2-2-run-lexical-retrieval-against-indexed-chunks): complete code review and mark done`) reinforces the current-snapshot build-resolution pattern. Story 2.4 should preserve the same freshness discipline for semantic artifacts.
- Commit `54e4f83` (`story(2-1-build-lexical-index-artifacts): complete code review and mark done`) is the strongest structural baseline: snapshot-scoped artifacts, dedicated build metadata persistence, and operator-safe failure handling.

### Latest Technical Information

- The official Sentence Transformers docs recommend installation via `pip install -U sentence-transformers`, require Python `3.10+`, and document `sentence_transformers.util.semantic_search` as suitable for corpora of up to about 1 million entries. Inference: an explicit local-embedding baseline plus deterministic exact-search vector artifacts is viable for the MVP if codeman wants to avoid prematurely locking into an ANN backend before Epic 3. [Source: https://www.sbert.net/; https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html]
- The official `sqlite-vec` docs present `sqlite-vec` as a pre-v1 SQLite vector-search extension, show Python installation via `pip install sqlite-vec`, and note that macOS system SQLite builds may not support extension loading without a Homebrew-installed Python. Inference: `sqlite-vec` is a promising future vector adapter, but it is not a safe unconditional default for a Python `>=3.13,<3.14` CLI unless extension-loading compatibility is proven in the repo's supported environments. [Source: https://alexgarcia.xyz/sqlite-vec/; https://alexgarcia.xyz/sqlite-vec/python.html]
- The official Faiss installation docs say the recommended installation path is through Conda, while the official Python 3.13 support issue remains open in the Faiss repository. Inference: do not make Faiss the mandatory first semantic-index dependency for this repository's Python 3.13 target without a separate compatibility spike. [Source: https://github.com/facebookresearch/faiss/wiki/Installing-Faiss; https://github.com/facebookresearch/faiss/issues/3985]
- The current local dev shell reports Python `3.12.2`, SQLite `3.45.3`, and `sqlite3.Connection.enable_load_extension` support. Inference: local extension-backed experiments are possible on this machine, but the repository contract still targets Python `>=3.13,<3.14`, so extension loading must be treated as environment-dependent rather than assumed portable. [Source: pyproject.toml; local command `python3 - <<'PY' ... print(sys.version.split()[0]); print(sqlite3.sqlite_version); print(hasattr(sqlite3.Connection, "enable_load_extension")) ... PY`]

### Project Context Reference

- `docs/project-context.md` is now present and is the canonical agent-facing implementation guide for this repository. It explicitly says to treat current code and tests as the source of truth for implemented behavior and not to assume semantic retrieval, hybrid retrieval, or external-provider evaluation are already implemented.
- `docs/README.md` is the canonical documentation map, and `docs/architecture/decisions.md` plus `docs/architecture/patterns.md` define the stable layering and extension rules this story should preserve.
- No separate UX design artifact exists for this project. Story 2.4 is a CLI/data-flow story, so UX requirements here are limited to clear operator messaging, safe failures, and machine-stable JSON/text output.

### References

- [Source: docs/project-context.md]
- [Source: docs/README.md]
- [Source: docs/cli-reference.md]
- [Source: docs/architecture/decisions.md]
- [Source: docs/architecture/patterns.md]
- [Source: _bmad-output/planning-artifacts/epics.md - Epic 2; Story 2.4; Story 2.5; Story 2.6; Story 2.7; Epic 3]
- [Source: _bmad-output/planning-artifacts/prd.md - Executive Summary; Success Criteria; Measurable Outcomes; MVP Scope; NFR5-NFR8; NFR10-NFR11; NFR15; NFR20-NFR21]
- [Source: _bmad-output/planning-artifacts/architecture.md - Data Architecture; Deferred Decisions; API Boundaries; Service Boundaries; Data Boundaries; Requirements to Structure Mapping]
- [Source: _bmad-output/implementation-artifacts/2-1-build-lexical-index-artifacts.md]
- [Source: _bmad-output/implementation-artifacts/2-2-run-lexical-retrieval-against-indexed-chunks.md]
- [Source: _bmad-output/implementation-artifacts/2-3-present-agent-friendly-ranked-retrieval-results.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: pyproject.toml]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/runtime.py]
- [Source: src/codeman/cli/index.py]
- [Source: src/codeman/contracts/retrieval.py]
- [Source: src/codeman/contracts/chunking.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: src/codeman/application/ports/artifact_store_port.py]
- [Source: src/codeman/application/ports/chunk_store_port.py]
- [Source: src/codeman/application/ports/index_build_store_port.py]
- [Source: src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/tables.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/index_build_repository.py]
- [Source: git log --oneline -5]
- [Source: https://www.sbert.net/]
- [Source: https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html]
- [Source: https://alexgarcia.xyz/sqlite-vec/]
- [Source: https://alexgarcia.xyz/sqlite-vec/python.html]
- [Source: https://github.com/facebookresearch/faiss/wiki/Installing-Faiss]
- [Source: https://github.com/facebookresearch/faiss/issues/3985]
- [Source: local command `python3 - <<'PY' ... print(sys.version.split()[0]); print(sqlite3.sqlite_version); print(hasattr(sqlite3.Connection, "enable_load_extension")) ... PY`]

## Story Completion Status

- Status set to `done`.
- Semantic indexing implementation completed, review findings fixed, and validation rerun successfully.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Debug Log References

- 2026-03-14: Story context generated via the `bmad-create-story` workflow for backlog story `2-4-build-semantic-retrieval-index-artifacts`.
- 2026-03-14: `bmad-dev-story` selected `2-4-build-semantic-retrieval-index-artifacts` from `_bmad-output/implementation-artifacts/sprint-status.yaml` and moved it to `in-progress`.
- 2026-03-14: Implemented semantic build contracts, ports, configuration fingerprinting, local-hash embedding generation, SQLite exact vector artifacts, metadata persistence, CLI wiring, and migration support.
- 2026-03-14: Validation passed with `UV_CACHE_DIR=.local/uv-cache uv run --group dev ruff check src tests` and `UV_CACHE_DIR=.local/uv-cache uv run --group dev pytest` (`133 passed`).
- 2026-03-14: Resolved code review findings for invalid semantic configuration handling and vector-dimension validation; reran `ruff check src tests` and `pytest` successfully (`136 passed`).

### Completion Notes List

- Added `index build-semantic <snapshot-id>` with text/JSON output, provider/model attribution, stable error handling, and local-only provider gating.
- Persisted embedding artifacts under `.codeman/artifacts/` and snapshot/config-scoped SQLite exact-search vector artifacts under `.codeman/indexes/vector/`.
- Added a dedicated semantic index build table/repository plus configuration-aware freshness lookups for current snapshot/config resolution.
- Added unit, integration, and e2e coverage for deterministic embeddings, provider failure behavior, snapshot/config freshness, and CLI contract output.
- Hardened semantic config parsing so invalid `CODEMAN_SEMANTIC_VECTOR_DIMENSION` values now fail with a stable semantic-build error instead of crashing CLI bootstrap.
- Rejected mixed-dimension vector documents before persisting SQLite semantic artifacts, keeping metadata and stored rows consistent.
- Full validation completed successfully: `ruff check src tests` and `pytest` both passed (`136 passed`).

### File List

- _bmad-output/implementation-artifacts/2-4-build-semantic-retrieval-index-artifacts.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- docs/cli-reference.md
- migrations/versions/202603141500_create_semantic_index_builds_table.py
- src/codeman/application/indexing/build_embeddings.py
- src/codeman/application/indexing/build_semantic_index.py
- src/codeman/application/indexing/build_vector_index.py
- src/codeman/application/indexing/semantic_index_errors.py
- src/codeman/application/ports/artifact_store_port.py
- src/codeman/application/ports/embedding_provider_port.py
- src/codeman/application/ports/semantic_index_build_store_port.py
- src/codeman/application/ports/vector_index_port.py
- src/codeman/bootstrap.py
- src/codeman/cli/index.py
- src/codeman/config/models.py
- src/codeman/config/semantic_indexing.py
- src/codeman/contracts/errors.py
- src/codeman/contracts/retrieval.py
- src/codeman/infrastructure/artifacts/filesystem_artifact_store.py
- src/codeman/infrastructure/embeddings/__init__.py
- src/codeman/infrastructure/embeddings/local_hash_provider.py
- src/codeman/infrastructure/indexes/vector/__init__.py
- src/codeman/infrastructure/indexes/vector/sqlite_exact_builder.py
- src/codeman/infrastructure/persistence/sqlite/repositories/semantic_index_build_repository.py
- src/codeman/infrastructure/persistence/sqlite/tables.py
- tests/e2e/test_index_build_semantic.py
- tests/integration/indexing/test_build_semantic_index_integration.py
- tests/unit/application/test_build_semantic_index.py
- tests/unit/cli/test_index.py
- tests/unit/config/test_semantic_indexing.py
- tests/unit/infrastructure/test_local_hash_provider.py
- tests/unit/infrastructure/test_sqlite_exact_vector_builder.py

## Senior Developer Review (AI)

### Review Date

2026-03-14

### Outcome

Approve

### Summary

- Verified Story 2.4 acceptance criteria against the semantic indexing implementation, CLI/docs surface, and automated coverage after the review-fix pass.
- Confirmed invalid semantic vector-dimension configuration now returns a stable semantic-build failure instead of crashing CLI bootstrap with a traceback.
- Confirmed the SQLite exact vector builder now rejects mixed embedding dimensions before writing an inconsistent artifact.

### Action Items

- [x] [High] Fail semantic builds safely when `CODEMAN_SEMANTIC_VECTOR_DIMENSION` is invalid.
- [x] [Medium] Reject mixed embedding dimensions before persisting semantic vector artifacts.

## Change Log

- 2026-03-14: Implemented snapshot-scoped semantic indexing with explicit local provider gating, persisted embedding/vector artifacts, semantic build metadata persistence, CLI/docs updates, and mirrored automated coverage.
- 2026-03-14: Resolved code review findings for semantic config crash handling and vector-dimension validation; reran validation and marked story `done`.
