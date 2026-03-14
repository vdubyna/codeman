# Story 1.5: Generate Structure-Aware Retrieval Chunks

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an internal engineer,
I want codeman to generate structured retrieval units from supported files,
so that later search operates on coherent chunks instead of coarse whole-file blobs.

## Acceptance Criteria

1. Given extracted supported source files, when chunk generation runs, then codeman produces chunk records with stable identifiers, source references, language metadata, and location/span metadata, and persists both metadata records and local chunk payload artifacts.
2. Given parser coverage is incomplete for a supported language file, when chunk generation cannot use the preferred structural strategy, then codeman degrades gracefully to a safe fallback chunking path, and records diagnostic context without failing the entire run unnecessarily.

## Tasks / Subtasks

- [x] Introduce the chunk-generation use case, DTOs, and CLI surface. (AC: 1, 2)
  - [x] Add chunk-generation request/result DTOs plus diagnostics payloads, preferably in a focused companion contract module such as `src/codeman/contracts/chunking.py`, or extend `src/codeman/contracts/repository.py` only if that remains readable.
  - [x] Create `src/codeman/application/indexing/build_chunks.py` as the orchestration entrypoint and keep `src/codeman/cli/index.py` limited to argument parsing, envelope formatting, and exit handling.
  - [x] Add the first chunking CLI surface as `uv run codeman index build-chunks <snapshot-id>` with `--output-format json`, reusing `get_container(ctx)`, `build_command_meta()`, and the existing success/failure envelope discipline.
  - [x] Introduce only the minimal new stable error codes needed for chunk generation, most likely a dedicated failure for missing extracted source inventory and a generic chunk-generation failure.

- [x] Add parser/chunker boundaries and language-aware registries without collapsing the architecture. (AC: 1, 2)
  - [x] Add explicit parser and chunker ports under `src/codeman/application/ports/` so the use case depends on capabilities, not concrete libraries.
  - [x] Introduce concrete registries under `src/codeman/infrastructure/parsers/` and `src/codeman/infrastructure/chunkers/` that resolve implementations by the normalized `SourceLanguage` already persisted in Story 1.4.
  - [x] Implement a preferred structure-aware path for PHP, JavaScript, HTML, and Twig that targets meaningful boundaries such as declarations, blocks, or template sections rather than naive whole-file blobs.
  - [x] Require a safe bounded fallback chunker for every supported language so parser errors, unsupported syntax, or partial coverage degrade per file instead of failing the full run.
  - [x] Keep parser/chunker diagnostics machine-readable and per-file, including whether the preferred structural path or fallback path was used.

- [x] Persist chunk metadata and chunk payload artifacts in the approved runtime locations. (AC: 1)
  - [x] Add a dedicated chunk metadata persistence port plus a SQLite adapter under `src/codeman/infrastructure/persistence/sqlite/repositories/`, following the same SQLAlchemy Core + Alembic approach used for `snapshots` and `source_files`.
  - [x] Add a `chunks` table that stores, at minimum: deterministic `chunk_id`, `snapshot_id`, `repository_id`, `source_file_id`, normalized `relative_path`, `language`, chunking strategy, source content hash, line-span and byte-span metadata, payload artifact path, and creation timestamp.
  - [x] Extend `FilesystemArtifactStore` with chunk payload writing under `.codeman/artifacts/snapshots/<snapshot-id>/chunks/` instead of writing payload files ad hoc from the use case.
  - [x] Make reruns for the same immutable snapshot idempotent so chunk metadata rows and payload artifacts do not silently duplicate on repeated execution.

- [x] Produce downstream-friendly outputs and operator-safe diagnostics. (AC: 1, 2)
  - [x] Return totals by language and by chunking strategy, plus counts of files that required fallback and counts of files skipped or partially degraded due to parser limitations.
  - [x] Keep default diagnostics summary-oriented and path-oriented; do not print raw chunk contents to the terminal in text mode or JSON mode.
  - [x] Preserve JSON-mode discipline: `stdout` contains only the final success/failure envelope, while any progress text such as `Generating chunks` goes to `stderr`.
  - [x] Update `docs/cli-reference.md` once the command shape and arguments are finalized.

- [x] Add automated coverage and mixed-stack fixtures that exercise both structural and fallback paths. (AC: 1, 2)
  - [x] Add unit tests for deterministic chunk ID generation, span calculation, parser failure handling, fallback chunk boundary behavior, and payload serialization.
  - [x] Add integration tests that prove Alembic creates the `chunks` schema, chunk rows are persisted with traceable source references, and payload artifacts are written to the expected runtime directory.
  - [x] Add an end-to-end CLI test that registers a repository, creates a snapshot, extracts sources, runs `index build-chunks`, and verifies both human-readable and JSON output flows.
  - [x] Extend the mixed-stack fixture set with at least one intentionally malformed-but-supported file so the story proves graceful fallback behavior instead of only the happy path.

## Dev Notes

### Previous Story Intelligence

- Story 1.4 established the key input contract for this story: `source_files` rows are now the authoritative inventory of supported files for a snapshot, with deterministic `source_file_id`, normalized relative paths, language labels, and content hashes already persisted.
- Story 1.4 also proved the preferred implementation style for codeman: thin Typer commands, one primary application use case per file, SQLAlchemy Core repositories, Alembic-managed schema changes, and runtime-managed artifacts under `.codeman/`.
- Snapshot safety is already part of the workflow. Story 1.5 should continue to treat chunk generation as snapshot-scoped work, not as a free scan of the mutable live repository tree.
- The most recent code-review fixes for Story 1.4 reinforced two behaviors worth preserving here: use Git-aware repository discovery rules instead of inventing a parallel file-walk policy, and keep operator diagnostics accurate without leaking repository content.

### Current Repo State

- `src/codeman/application/indexing/` currently contains only `extract_source_files.py`; there is no chunk-generation orchestration yet.
- `src/codeman/cli/index.py` exposes only `extract-sources`, so this story introduces the next real `index` workflow rather than a placeholder.
- `src/codeman/bootstrap.py` wires repository registration, snapshot creation, and source extraction only. There is no parser registry, chunker registry, chunk store, or chunk payload artifact support in the container today.
- `src/codeman/contracts/repository.py` already models `SourceFileRecord` and extraction diagnostics, but there is no chunk DTO contract yet.
- `src/codeman/infrastructure/persistence/sqlite/tables.py` currently defines `repositories`, `snapshots`, and `source_files`; there is no `chunks` table yet.
- `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py` currently writes snapshot manifests only, so chunk payload writing should extend that adapter rather than bypass it.
- The mixed-stack fixture introduced in Story 1.4 already covers representative PHP, JavaScript, HTML, Twig, unsupported, ignored, and binary files. This story should reuse it and extend it only where fallback scenarios require malformed source.
- The codebase does not yet contain the broader `domain/chunking/`, parser, or chunker packages shown in the architecture target tree. Introduce only the minimal structure required to deliver Story 1.5 cleanly.

### Technical Guardrails

- Keep the public interface CLI-only. This story must not introduce HTTP endpoints, MCP behavior, daemon processes, or background workers. [Source: _bmad-output/planning-artifacts/prd.md - Project Classification; _bmad-output/planning-artifacts/architecture.md - API & Communication Patterns]
- Treat extracted source inventory as the required upstream input. Chunk generation should consume persisted `source_files` rows for a snapshot, not re-scan the repository and not recreate Story 1.4's discovery logic. [Source: _bmad-output/implementation-artifacts/1-4-extract-supported-source-files-into-a-source-inventory.md]
- Preserve the modular-monolith boundary already working in the repository: CLI parses and formats, application orchestrates, infrastructure owns parser/chunker/SQLite/filesystem details, and contracts remain the stable DTO layer. [Source: _bmad-output/planning-artifacts/architecture.md - Architectural Boundaries; Service Boundaries]
- `bootstrap.py` remains the single composition root. Wire parser registries, chunkers, repositories, and artifact adapters there instead of constructing them inside CLI commands or tests. [Source: _bmad-output/planning-artifacts/architecture.md - Project Structure & Boundaries]
- Keep runtime path ownership inside `src/codeman/runtime.py`. Chunk artifacts and any future parser intermediates belong under `.codeman/`, not under `src/` or checked-in fixture directories. [Source: _bmad-output/planning-artifacts/architecture.md - Data Boundaries; File Organization Patterns]
- Stay on the approved foundation already pinned in `pyproject.toml`: Python `>=3.13,<3.14`, Typer `0.20.x`, Pydantic `2.12.x`, SQLAlchemy Core `2.0.x`, and Alembic `1.17.x`. Do not turn Story 1.5 into a dependency-upgrade story. [Source: pyproject.toml; _bmad-output/planning-artifacts/architecture.md - Core Architectural Decisions]
- Chunk metadata must be traceable enough for later lexical retrieval, semantic retrieval, diagnostics, and benchmarking. At minimum that means stable chunk identity, source-file identity, repository/snapshot identity, normalized language label, strategy metadata, and line/byte spans. [Source: _bmad-output/planning-artifacts/epics.md - Story 1.5; Story 2.3; Story 2.5]
- Persist payload content outside SQLite. The database should store metadata and artifact paths; the actual chunk text or serialized payload belongs in the filesystem artifact store. [Source: _bmad-output/planning-artifacts/architecture.md - Data Architecture]
- Do not wait for perfect AST fidelity before shipping Story 1.5. The PRD explicitly allows parser maturity to vary, so a useful structure-aware implementation with mandatory per-file fallback is better than blocking the story on complete grammar coverage. [Source: _bmad-output/planning-artifacts/prd.md - Product Scope; Domain-Specific Requirements; Risk Mitigations]
- Fallback chunking must still produce bounded, ordered, traceable chunks. A fallback that emits whole-file blobs would violate the story intent and weaken later retrieval quality. [Source: _bmad-output/planning-artifacts/prd.md - Executive Summary; Success Criteria]
- Keep default diagnostics privacy-safe. Parser failures and fallback counts are useful; dumping raw source excerpts or chunk payloads to console output is not. [Source: _bmad-output/planning-artifacts/architecture.md - Authentication & Security; Process Patterns]
- Record enough metadata now to unblock Story 1.6 re-indexing later: deterministic chunk IDs, source content hash, chunking strategy, and a serialization/version marker are more valuable than clever cache invalidation logic in this story. [Source: _bmad-output/planning-artifacts/epics.md - Story 1.6; Additional Requirements]

### File / Structure Guidance

- Preferred new or expanded files for this story:
  - `src/codeman/application/indexing/build_chunks.py`
  - `src/codeman/application/ports/parser_port.py`
  - `src/codeman/application/ports/chunker_port.py`
  - `src/codeman/application/ports/chunk_store_port.py`
  - `src/codeman/bootstrap.py`
  - `src/codeman/cli/index.py`
  - `src/codeman/contracts/chunking.py`
  - `src/codeman/contracts/errors.py`
  - `src/codeman/infrastructure/parsers/__init__.py`
  - `src/codeman/infrastructure/parsers/parser_registry.py`
  - `src/codeman/infrastructure/parsers/php_parser.py`
  - `src/codeman/infrastructure/parsers/javascript_parser.py`
  - `src/codeman/infrastructure/parsers/html_parser.py`
  - `src/codeman/infrastructure/parsers/twig_parser.py`
  - `src/codeman/infrastructure/chunkers/__init__.py`
  - `src/codeman/infrastructure/chunkers/chunker_registry.py`
  - `src/codeman/infrastructure/chunkers/php_chunker.py`
  - `src/codeman/infrastructure/chunkers/javascript_chunker.py`
  - `src/codeman/infrastructure/chunkers/html_chunker.py`
  - `src/codeman/infrastructure/chunkers/twig_chunker.py`
  - `src/codeman/infrastructure/artifacts/filesystem_artifact_store.py`
  - `src/codeman/infrastructure/persistence/sqlite/tables.py`
  - `src/codeman/infrastructure/persistence/sqlite/repositories/chunk_repository.py`
  - `migrations/versions/<timestamp>_create_chunks_table.py`
  - `docs/cli-reference.md`
  - `tests/e2e/test_index_build_chunks.py`
  - `tests/integration/persistence/test_chunk_generation.py`
  - `tests/unit/application/test_build_chunks.py`
  - `tests/unit/cli/test_index.py`
  - `tests/unit/infrastructure/test_chunker_registry.py`
  - `tests/unit/infrastructure/test_parsers.py`
- A pragmatic first CLI surface is:
  - `uv run codeman index build-chunks <snapshot-id>`
  - `uv run codeman index build-chunks <snapshot-id> --output-format json`
- A pragmatic metadata row shape for `chunks` is:
  - `id`
  - `snapshot_id`
  - `repository_id`
  - `source_file_id`
  - `relative_path`
  - `language`
  - `strategy`
  - `source_content_hash`
  - `start_line`
  - `end_line`
  - `start_byte`
  - `end_byte`
  - `payload_path`
  - `created_at`
- A pragmatic payload artifact shape is a per-chunk JSON document under `.codeman/artifacts/snapshots/<snapshot-id>/chunks/<chunk-id>.json` containing chunk content plus the same traceability metadata needed by later indexing stages.
- A good deterministic chunk ID strategy is a hash over `source_file_id`, strategy, normalized span metadata, and a chunk-serialization version string. This keeps IDs stable for the same immutable source input while leaving room for later serialization changes.
- If parser-specific node objects are needed internally, keep them infrastructure-local and convert them into project DTOs before they cross application boundaries.

### Testing Guidance

- Use pytest across unit, integration, and e2e layers and keep the same temp-workspace isolation pattern already used in Stories 1.3 and 1.4. [Source: _bmad-output/implementation-artifacts/1-4-extract-supported-source-files-into-a-source-inventory.md - Testing Guidance]
- Add at least one unit test proving chunk IDs remain deterministic even if parser traversal order changes internally.
- Add explicit coverage that parser failure on one supported file triggers fallback for that file and does not fail chunk generation for the whole snapshot.
- Add coverage that fallback chunks still preserve ordered spans and do not collapse into a single whole-file blob unless the file is genuinely tiny and already within the configured chunk boundary.
- Add integration coverage that rerunning chunk generation for the same snapshot is idempotent for both SQLite rows and artifact files.
- Add a negative-path test for invoking chunk generation before source extraction has populated inventory rows, and ensure the command fails with a stable error contract instead of a generic stack trace.
- Add e2e coverage for JSON mode proving `stdout` contains only the final envelope and no progress noise, while human-readable diagnostics stay useful. [Source: _bmad-output/planning-artifacts/architecture.md - Process Patterns]

### Git Intelligence Summary

- Recent implementation history shows a consistent additive pattern: Story 1.3 added snapshot creation through new ports, a focused use case, a SQLite repository adapter, and mirrored tests rather than restructuring the project.
- Story 1.4 followed the same pattern and expanded the repository with `extract_source_files.py`, a dedicated source-inventory port and repository, fixture coverage, and `index` CLI wiring. Story 1.5 should continue that approach instead of introducing a second implementation style.
- The latest commit, `d1eebe2`, confirmed that review fixes are landing directly in the same files rather than through wrapper abstractions. Favor small explicit modules and tight tests over prematurely broad framework layers.
- Current history also shows the repository prefers mirrored coverage under `tests/unit/`, `tests/integration/`, and `tests/e2e/`. New chunking behavior should ship with the same test symmetry.

### Latest Technical Information

- As of March 14, 2026, Python `3.13.12` was released on February 3, 2026 as the twelfth maintenance release of the 3.13 line, while Python 3.14 is the latest feature series. The repository's `>=3.13,<3.14` pin is therefore still a deliberate stability choice for this story, not outdated drift. [Source: https://www.python.org/downloads/release/python-31312/]
- Typer `0.20.0` officially added command suggestions on typo by default and support for Python 3.14. The current project pin to `0.20.x` remains aligned with modern Typer behavior, so Story 1.5 should reuse the existing multi-command Typer patterns rather than redesigning the CLI surface. [Source: https://typer.tiangolo.com/release-notes/]
- Pydantic `v2.12` added initial Python 3.14 support on October 7, 2025. The repository's current `BaseModel` + `ConfigDict(extra="forbid")` contract style remains the correct v2-era pattern, and there is no reason for Story 1.5 to introduce Pydantic v1 compatibility code. [Source: https://pydantic.dev/articles/pydantic-v2-12-release]
- SQLAlchemy's official site lists `2.0.48` as the current 2.0 release as of March 2, 2026, newer than the architecture-pinned `2.0.44`. Because the project explicitly approved the 2.0 Core line already, Story 1.5 should stay on SQLAlchemy Core patterns and avoid opportunistic persistence-stack upgrades. [Source: https://www.sqlalchemy.org/blog/2025/10/10/sqlalchemy-2.0.44-released/]
- Alembic `1.17.2` was released on November 14, 2025 and the current docs have already moved on to `1.18.x`. That means the migration strategy in this repository is still modern, but Story 1.5 should continue the existing Alembic workflow instead of mixing in hand-written schema bootstrapping. [Source: https://alembic.sqlalchemy.org/en/latest/changelog.html]
- Tree-sitter's official documentation describes it as robust enough to provide useful results even in the presence of syntax errors, and the official Python bindings provide pre-compiled wheels for major platforms. If Story 1.5 introduces parser-backed chunking, Tree-sitter is a strong candidate for the parser layer, but fallback chunking remains mandatory because parser coverage and grammar maturity can still vary across file types. [Source: https://tree-sitter.github.io/tree-sitter/; https://github.com/tree-sitter/py-tree-sitter]

### Project Context Reference

- No `project-context.md` file was found in the repository, so the authoritative guidance remains the PRD, architecture, epics, sprint status, and the completed Stories 1.3 and 1.4 artifacts.
- No separate UX design artifact exists for this project, and Story 1.5 remains a CLI/data-flow story with no dedicated UI requirements.

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Story 1.5; Story 1.6; Additional Requirements]
- [Source: _bmad-output/planning-artifacts/prd.md - Executive Summary; Product Scope; Success Criteria; User Journeys; Domain-Specific Requirements; Risk Mitigations]
- [Source: _bmad-output/planning-artifacts/architecture.md - Core Architectural Decisions; Data Architecture; Process Patterns; Project Structure & Boundaries; Architectural Boundaries; Data Boundaries; File Organization Patterns]
- [Source: _bmad-output/implementation-artifacts/1-4-extract-supported-source-files-into-a-source-inventory.md]
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml]
- [Source: README.md]
- [Source: pyproject.toml]
- [Source: docs/cli-reference.md]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/cli/index.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: src/codeman/contracts/repository.py]
- [Source: src/codeman/application/indexing/extract_source_files.py]
- [Source: src/codeman/application/ports/source_inventory_port.py]
- [Source: src/codeman/application/ports/snapshot_port.py]
- [Source: src/codeman/infrastructure/artifacts/filesystem_artifact_store.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/tables.py]
- [Source: src/codeman/infrastructure/persistence/sqlite/repositories/source_file_repository.py]
- [Source: src/codeman/infrastructure/snapshotting/local_repository_scanner.py]
- [Source: tests/unit/application/test_extract_source_files.py]
- [Source: tests/unit/cli/test_index.py]
- [Source: tests/integration/persistence/test_source_inventory_extraction.py]
- [Source: tests/e2e/test_repo_snapshot.py]
- [Source: git log --oneline -5]
- [Source: git show --stat --summary 0230d47]
- [Source: git show --stat --summary d1eebe2]
- [Source: https://www.python.org/downloads/release/python-31312/]
- [Source: https://typer.tiangolo.com/release-notes/]
- [Source: https://pydantic.dev/articles/pydantic-v2-12-release]
- [Source: https://www.sqlalchemy.org/blog/2025/10/10/sqlalchemy-2.0.44-released/]
- [Source: https://alembic.sqlalchemy.org/en/latest/changelog.html]
- [Source: https://tree-sitter.github.io/tree-sitter/]
- [Source: https://github.com/tree-sitter/py-tree-sitter]

## Story Completion Status

- Status set to `ready-for-dev`.
- Ultimate context engine analysis completed - comprehensive developer guide created.
- The next expected workflow is implementation via the dev-story/dev agent, followed by code review once development is complete.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Debug Log References

- `PYTHONPATH=src python -m pytest -q tests/unit/application/test_build_chunks.py tests/unit/infrastructure/test_parsers.py tests/unit/infrastructure/test_chunker_registry.py tests/unit/infrastructure/test_filesystem_artifact_store.py tests/unit/cli/test_index.py tests/integration/persistence/test_source_inventory_extraction.py tests/integration/persistence/test_chunk_generation.py tests/e2e/test_index_extract_sources.py tests/e2e/test_index_build_chunks.py`
- `UV_CACHE_DIR=/Users/vdubyna/Workspace/AI__AGENTS/codeman/.local/uv-cache uv run ruff check src tests`

### Completion Notes List

- Implemented `index build-chunks` with stable chunk DTOs, snapshot-scoped orchestration, CLI success/failure envelopes, and dedicated error handling for missing source inventory and generic chunk-generation failures.
- Added parser/chunker ports plus language-aware parser and chunker registries for PHP, JavaScript, HTML, and Twig, including bounded per-file fallback and machine-readable fallback diagnostics.
- Persisted chunk metadata through a new `chunks` SQLite schema and repository adapter, and wrote per-chunk payload artifacts under `.codeman/artifacts/snapshots/<snapshot-id>/chunks/`.
- Extended the mixed-stack fixture with a malformed supported JavaScript file and added unit, integration, and e2e coverage for deterministic IDs, span behavior, fallback execution, idempotent reruns, CLI JSON discipline, and artifact persistence.
- Resolved review findings by distinguishing empty extracted inventories from missing extraction state, splitting single-boundary files into preamble plus structural chunks, and falling back for any preferred-path parser/chunker exception on a per-file basis.

### File List

- _bmad-output/implementation-artifacts/1-5-generate-structure-aware-retrieval-chunks.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- docs/cli-reference.md
- migrations/versions/202603141100_create_chunks_table.py
- migrations/versions/202603141215_add_source_inventory_extracted_at_to_snapshots.py
- src/codeman/application/indexing/build_chunks.py
- src/codeman/application/indexing/extract_source_files.py
- src/codeman/application/ports/artifact_store_port.py
- src/codeman/application/ports/chunk_store_port.py
- src/codeman/application/ports/chunker_port.py
- src/codeman/application/ports/parser_port.py
- src/codeman/application/ports/snapshot_port.py
- src/codeman/application/ports/source_inventory_port.py
- src/codeman/bootstrap.py
- src/codeman/cli/index.py
- src/codeman/contracts/chunking.py
- src/codeman/contracts/errors.py
- src/codeman/contracts/repository.py
- src/codeman/infrastructure/artifacts/filesystem_artifact_store.py
- src/codeman/infrastructure/chunkers/__init__.py
- src/codeman/infrastructure/chunkers/chunker_registry.py
- src/codeman/infrastructure/chunkers/common.py
- src/codeman/infrastructure/chunkers/fallback_chunker.py
- src/codeman/infrastructure/chunkers/html_chunker.py
- src/codeman/infrastructure/chunkers/javascript_chunker.py
- src/codeman/infrastructure/chunkers/php_chunker.py
- src/codeman/infrastructure/chunkers/twig_chunker.py
- src/codeman/infrastructure/parsers/__init__.py
- src/codeman/infrastructure/parsers/html_parser.py
- src/codeman/infrastructure/parsers/javascript_parser.py
- src/codeman/infrastructure/parsers/parser_registry.py
- src/codeman/infrastructure/parsers/php_parser.py
- src/codeman/infrastructure/parsers/twig_parser.py
- src/codeman/infrastructure/persistence/sqlite/repositories/chunk_repository.py
- src/codeman/infrastructure/persistence/sqlite/repositories/snapshot_repository.py
- src/codeman/infrastructure/persistence/sqlite/repositories/source_file_repository.py
- src/codeman/infrastructure/persistence/sqlite/tables.py
- tests/e2e/test_index_build_chunks.py
- tests/e2e/test_index_extract_sources.py
- tests/fixtures/repositories/mixed_stack_fixture/assets/broken.js
- tests/unit/application/test_create_snapshot.py
- tests/unit/application/test_extract_source_files.py
- tests/integration/persistence/test_chunk_generation.py
- tests/integration/persistence/test_source_inventory_extraction.py
- tests/unit/application/test_build_chunks.py
- tests/unit/cli/test_index.py
- tests/unit/infrastructure/test_chunker_registry.py
- tests/unit/infrastructure/test_filesystem_artifact_store.py
- tests/unit/infrastructure/test_parsers.py

## Change Log

- 2026-03-14: Story created and marked `ready-for-dev` with parser/chunker, artifact, persistence, diagnostics, and testing guidance for structure-aware chunk generation.
- 2026-03-14: Implemented structure-aware chunk generation with parser/fallback registries, chunk metadata persistence, payload artifacts, CLI outputs, and automated coverage; status moved to `review`.
- 2026-03-14: Fixed review findings around empty extracted inventories, single-boundary whole-file chunking, and non-`ParserFailure` preferred-path exceptions.
- 2026-03-14: Final validation passed, story status moved to `done`, and sprint tracking synced for release commit.
