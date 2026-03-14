---
stepsCompleted:
  - step-01-init
  - step-02-context
  - step-03-starter
  - step-04-decisions
  - step-05-patterns
  - step-06-structure
  - step-07-validation
  - step-08-complete
inputDocuments:
  - /Users/vdubyna/Workspace/AI__AGENTS/codeman/_bmad-output/planning-artifacts/prd.md
workflowType: 'architecture'
lastStep: 8
status: 'complete'
completedAt: '2026-03-13T22:39:25+0200'
project_name: 'codeman'
user_name: 'Vdubyna'
date: '2026-03-13T22:15:54+0200'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
The product defines 31 functional requirements across six capability areas. Architecturally, the most important implication is that the system is not a single search feature but a modular retrieval platform with a complete operational lifecycle.

The first capability group covers repository ingestion and content structuring. The architecture must support local repository registration, repository snapshot creation, source extraction across PHP, JavaScript, HTML, and Twig, structure-aware chunk generation, metadata preservation, and re-indexing after source or configuration changes.

The second capability group covers search and retrieval workflows. The system must support lexical, semantic, and hybrid retrieval over a shared indexed corpus, return ranked results, expose agent-usable retrieval packages, and allow comparative inspection across retrieval modes. This implies a shared query orchestration layer over multiple retrieval engines rather than isolated implementations.

The third capability group covers retrieval configuration and experiment control. Maintainers must be able to configure embeddings, retrieval strategies, and experiment variants independently, identify which configuration produced a run, and reuse prior configurations. This creates a strong need for explicit configuration models and experiment metadata capture.

The fourth capability group covers evaluation and benchmarking. Benchmark execution, golden-query evaluation, result review, strategy comparison, regression detection, and attribution of results to configuration are first-class capabilities. Architecturally, evaluation cannot be an afterthought or a loose script; it must be integrated into the platform design.

The fifth capability group covers CLI operations and troubleshooting. The CLI is the MVP interface and must support repeated operational workflows while also helping maintainers diagnose failed indexing, retrieval, and evaluation runs. This implies deterministic command design, explicit failure modes, and subsystem-oriented diagnostics.

The sixth capability group covers future interface expansion. MCP is planned for Phase 2, with an explicit requirement that it reuse the same retrieval core and preserve behavior consistency with the CLI baseline. This means interface concerns must remain separate from core indexing, retrieval, and evaluation services from the start.

**Non-Functional Requirements:**
The non-functional requirements strongly shape the architecture.

Performance expectations are moderate but explicit: lexical retrieval should return within 2 seconds on the reference benchmark repository, while semantic and hybrid retrieval should return within 5 seconds. More importantly, the system must record latency and indexing time in a consistent way that supports before/after comparison across configurations.

Security and data handling requirements establish a local-first operating model. Repository contents and derived artifacts must stay local by default, external provider usage must be explicit, secrets must stay out of source control, and diagnostic output must avoid exposing repository contents unless explicitly enabled.

Reliability and reproducibility are central architectural drivers. Every indexing, query, and benchmark run must capture sufficient metadata to reproduce and attribute the result. Operational workflows must produce clear success and failure outcomes, and failures must surface actionable diagnostic information tied to likely subsystems.

Maintainability and extensibility requirements require bounded module responsibilities across repository snapshotting, parsing, chunking, embeddings, lexical retrieval, vector retrieval, fusion, output formatting, and evaluation. Future changes such as a new chunking strategy or embedding provider must remain localized.

Integration consistency requirements require a stable, scriptable CLI in the MVP and a future MCP layer that reuses the same retrieval semantics and services rather than creating a parallel path.

**Scale & Complexity:**
This is a medium-complexity project with high architectural discipline requirements. It does not appear enterprise-scale in terms of user load, multi-tenancy, or regulatory overhead, but it is architecture-sensitive because the product's value depends on modularity, experiment repeatability, and evaluable retrieval quality.

- Primary domain: backend developer tool / retrieval platform
- Complexity level: medium
- Estimated architectural components: 10

### Technical Constraints & Dependencies

The implementation stack is Python with uv as the official workflow for environment setup, dependency management, execution, testing, and benchmarking.

The MVP must support parsing and indexing for PHP, JavaScript, HTML, and Twig repositories. This creates a dependency on language-specific parsing adapters or structure-aware extraction mechanisms with uneven parser maturity handled gracefully.

The system must remain CLI-first in the MVP, with MCP explicitly deferred to Phase 2. External embedding providers are optional dependencies, but if used, the architecture must make provider boundaries, model versions, and privacy implications explicit.

Benchmark comparability is a hard technical constraint. The architecture must preserve repository revision identity, retrieval configuration identity, provider/model metadata, and execution timestamps for reproducible runs and regression analysis.

### Cross-Cutting Concerns Identified

Reproducibility is a platform-wide concern affecting indexing, retrieval, evaluation, and reporting.

Configuration traceability is a cross-cutting requirement because retrieval quality depends on chunking strategy, provider choice, model version, index settings, and fusion strategy.

Local-first privacy boundaries affect embedding workflows, provider integration, runtime messaging, and operational defaults.

Diagnostics and failure attribution must cut across ingestion, parsing, chunking, retrieval, and evaluation so maintainers can isolate degraded or failed runs quickly.

Interface consistency is a forward-looking concern: the CLI and future MCP interface must share the same retrieval core, output semantics, and evaluation assumptions.

Bounded modularity is the central architectural quality attribute. The system must remain easy to extend experimentally without turning into a tightly coupled pipeline.

## Starter Template Evaluation

### Primary Technology Domain

CLI tool / backend developer tool based on project requirements analysis.

### Starter Options Considered

**Option 1: Official uv packaged application starter**
The official `uv init --package` starter is the lowest-ceremony foundation and fits the project's internal-tool character well. It creates a packaged application with `src/` layout, a script entry point in `pyproject.toml`, a pinned Python version file, and a build backend already configured.

Architecturally, this option gives the project a clean package boundary and predictable entrypoint model without introducing accidental architecture. It establishes only the minimum structure required to begin implementation while preserving freedom to design retrieval-specific module boundaries intentionally.

**Option 2: audreyfeldroy/cookiecutter-pypackage**
This is a long-standing Python package template with pytest, GitHub Actions, optional release automation, and broader project scaffolding. It is stronger if the immediate goal is public package maturity, release workflow standardization, and documentation process from day one.

For this project, it appears heavier than necessary for the MVP. It front-loads packaging and release concerns that are not core to validating the retrieval platform.

**Option 3: browniebroke/pypackage-template**
This Copier-based template offers a modern opinionated Python package setup with uv-friendly workflows, testing, linting, documentation scaffolding, and optional CLI enhancements.

Its strength is also its trade-off: it introduces many repository-process decisions early. For an internal R&D retrieval platform, that risks shifting attention away from the retrieval core and toward template-governed process structure before the MVP proves its value.

### Selected Starter: Official uv packaged application starter

**Rationale for Selection:**
This project needs a strong package boundary, a clean CLI entry point, and a reproducible Python workflow without prematurely committing to heavyweight release or documentation scaffolding.

The official uv packaged application starter is the best fit because it:
- aligns directly with the PRD's Python + uv requirement;
- supports a packaged CLI shape from day one;
- keeps the architecture low-ceremony and modular;
- avoids locking the MVP into public-package conventions that are not yet required;
- creates an MVP-honest foundation that does not introduce accidental architecture through template opinions;
- leaves room to add Typer, pytest, Ruff, and benchmark tooling intentionally as early implementation stories.

This choice does not reject richer templates forever. It simply defers those heavier process decisions until the project has proven enough value to justify stronger packaging, release, and documentation automation.

**Initialization Command:**

```bash
uv init --package codeman
```

**Architectural Decisions Provided by Starter:**

**Language & Runtime:**
Python packaged application with a `src/` layout, `pyproject.toml`, `.python-version`, and a script entry point wired through `[project.scripts]`.

**Styling Solution:**
Not applicable for this CLI-first backend tool.

**Build Tooling:**
uv-managed project setup with a build backend configured by the generated template. This provides a modern packaging baseline without forcing a broader framework stack.

**Testing Framework:**
No testing framework is imposed by the starter. This is a positive trade-off here because testing can be added deliberately to match the retrieval core, benchmark harness, and CLI workflow requirements.

**Code Organization:**
A clean packaged layout with separation between project metadata and source package code. This is suitable for building bounded modules such as snapshotting, parsing, chunking, retrieval, fusion, evaluation, and CLI orchestration.

**Development Experience:**
Simple uv-native developer workflow, predictable entrypoint execution, and minimal generated boilerplate. This keeps the first implementation story focused on actual product architecture instead of template cleanup.

**Follow-up Foundation Stories:**
Early implementation should explicitly add:
- a CLI framework layer, with Typer as the leading fit for multi-command workflows;
- pytest-based testing for core retrieval modules;
- Ruff for linting and formatting;
- benchmark-oriented CLI flows for evaluation and comparison.

**Note:** Project initialization using this command should be the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Runtime baseline: Python 3.13.x on the uv-packaged application foundation. Although Python 3.14.3 is the latest active feature release, Python 3.13.12 remains on active bugfix support and is the more conservative baseline for an internal experimentation platform.
- Application shape: modular monolith with explicit ports-and-adapters boundaries.
- Persistence model: split storage architecture with a local metadata database plus filesystem-managed artifact storage.
- CLI contract: a multi-command CLI implemented with Typer 0.20.0, with human-readable default output and machine-readable JSON output for automation and agent workflows.
- Validation and schema evolution: Pydantic 2.12.5 for configuration and boundary DTO validation, SQLAlchemy Core 2.0.44 for relational persistence access, and Alembic 1.17.2 for schema migrations.
- Security boundary: local single-operator trust model in the MVP, with external provider usage disabled by default and made explicit whenever enabled.

**Important Decisions (Shape Architecture):**
- Incremental indexing and embedding caches keyed by repository revision, content hash, provider, and model metadata.
- In-process communication only in the MVP; no service mesh, message broker, or HTTP API.
- Structured run manifests and JSONL logging for diagnostics, provenance, and regression investigation.
- Repo-native CI requirements defined now, even if the exact CI host can follow repository hosting later.
- Layered configuration model with defaults, local config, per-run overrides, and environment-provided secrets.

**Deferred Decisions (Post-MVP or Early Spike):**
- Exact lexical index library selection.
- Exact vector index library selection.
- Default embedding provider selection beyond interface definition.
- MCP authentication and authorization model.
- External observability backend.
- Containerized or hosted deployment strategy.

### Data Architecture

**Primary Persistence Decision:**
Use a split local persistence architecture:
- a SQLite-compatible relational metadata store for repositories, snapshots, chunks, runs, benchmark records, and experiment metadata;
- a filesystem artifact store for snapshot manifests, chunk payload exports, index artifacts, and benchmark reports;
- adapter-owned local index directories for lexical and vector engine implementation details.

This keeps provenance and reproducibility explicit without forcing all heavy retrieval artifacts into one storage mechanism.

**Data Modeling Approach:**
The core model should treat the following as first-class entities:
- Repository
- Snapshot
- SourceFile
- Chunk
- EmbeddingDocument
- IndexBuild
- QueryRun
- BenchmarkRun
- ExperimentConfig

The architecture should prefer immutable snapshot/run records so benchmark comparisons remain attributable and repeatable.

**Validation Strategy:**
Use Pydantic 2.12.5 for:
- CLI input parsing
- configuration validation
- provider configuration
- external adapter contracts
- serialized output DTOs

Use lightweight internal Python types for hot-path core logic rather than making the entire domain model Pydantic-native.

**Migration Strategy:**
Use SQLAlchemy Core 2.0.44 plus Alembic 1.17.2 for metadata schema access and evolution. Avoid ORM-heavy domain modeling in the MVP; keep persistence explicit and close to the schema.

**Caching Strategy:**
Adopt content-hash-based incremental caching for:
- repository snapshot reuse
- parser outputs
- chunk generation
- embedding generation

Embedding cache keys must include provider identity, model version, and relevant chunk serialization version.

### Authentication & Security

**Authentication Method:**
No built-in end-user authentication in the MVP. The CLI operates as a local developer tool within the current OS user context.

**Authorization Pattern:**
Authorization is inherited from local filesystem access and explicit tool configuration. The application should not introduce a role model before MCP exists.

**Secrets & Sensitive Data Handling:**
- external provider credentials must come from environment variables or protected local configuration;
- secrets must never be written to source control or benchmark result files;
- repository contents remain local by default.

**Provider Security Strategy:**
External embedding providers are opt-in only. Runtime output and recorded metadata must make provider and model usage visible for every run.

**Diagnostic Safety:**
Diagnostic output should be redacted by default, with an explicit verbose/debug mode required before showing sensitive repository excerpts.

### API & Communication Patterns

**Public Interface Pattern:**
The MVP exposes no HTTP API. The public interface is the CLI only.

Recommended command groups:
- `repo`
- `index`
- `query`
- `eval`
- `compare`
- `config`

**Internal Communication Pattern:**
Use an in-process modular monolith with explicit service boundaries and ports for:
- repository snapshotting
- parsing
- chunking
- embedding providers
- lexical retrieval
- vector retrieval
- fusion strategies
- evaluation/reporting

This preserves replaceability without introducing distributed-systems overhead prematurely.

**Error Handling Standard:**
Adopt a domain exception taxonomy mapped to:
- stable exit codes
- concise human-readable console errors
- structured JSON error payloads in machine mode

**Output Contract:**
Every retrieval and benchmark command should support a stable JSON output mode for agent workflows, alongside a human-readable default console mode for developers.

**Rate Limiting / Throughput Control:**
No general API rate limiting is required for local CLI execution. Provider adapters must implement their own concurrency and retry controls when using external APIs.

### Frontend Architecture

Not applicable for the MVP. The system has no browser frontend, desktop UI, or separate interactive client surface.

Any future TUI, web UI, or richer MCP presentation layer should be treated as a later interface on top of the same core services.

### Infrastructure & Deployment

**Hosting Strategy:**
Local workstation execution only in the MVP. No always-on hosted environment is required.

**CI/CD Approach:**
Define a repository-native CI pipeline that enforces:
- lint/format checks
- unit tests
- retrieval smoke tests
- benchmark smoke execution

If the repository is hosted on GitHub, GitHub Actions is the default reference implementation; otherwise the same pipeline shape should be mirrored in the host-native CI system.

**Environment Configuration:**
Use layered configuration:
- project defaults in `pyproject.toml`
- user-local application config
- per-run CLI overrides
- environment variables for secrets and final overrides

**Monitoring and Logging:**
Use local structured JSONL logs plus human console output. Do not introduce external telemetry by default in the MVP.

**Scaling Strategy:**
Optimize for single-machine scale with bounded parallelism in indexing and evaluation workflows. Distributed indexing and multi-node execution are deferred.

### Decision Impact Analysis

**Implementation Sequence:**
1. Initialize the project with the selected uv starter and set the Python baseline.
2. Define configuration schemas, output DTOs, and core ports.
3. Implement metadata persistence and migrations.
4. Build snapshotting, parsing, and chunking pipelines.
5. Add lexical/vector adapters behind stable interfaces.
6. Implement CLI command groups and JSON output contracts.
7. Add benchmark execution and comparison workflows.
8. Add provider integrations, redaction controls, and diagnostics hardening.

**Cross-Component Dependencies:**
- The split persistence model requires explicit artifact manifesting and cleanup policies.
- JSON CLI contracts make DTO stability a core architectural concern.
- Deferring exact lexical/vector engines means adapter contracts must be designed before engine implementation.
- The local trust model simplifies MVP scope, but it makes provider transparency and redacted diagnostics mandatory from the start.

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:**
18 high-risk areas where AI agents could make incompatible choices without explicit project rules.

### Naming Patterns

**Database Naming Conventions:**
- Relational tables use lowercase plural `snake_case`: `repositories`, `snapshots`, `chunks`, `benchmark_runs`.
- Primary keys use `id`.
- Foreign keys use `<entity>_id`: `repository_id`, `snapshot_id`, `chunk_id`.
- Timestamp columns use `_at` suffix: `created_at`, `updated_at`, `indexed_at`.
- Boolean columns use positive predicate names: `is_active`, `is_cached`, `is_external_provider`.
- Index names use `idx_<table>_<column_list>` and unique constraints use `uq_<table>_<column_list>`.

**API Naming Conventions:**
The MVP has no HTTP API, so the equivalent consistency surface is the CLI and machine-readable JSON output.
- CLI command groups use short lowercase nouns: `repo`, `index`, `query`, `eval`, `compare`, `config`.
- CLI subcommands use kebab-case verbs or verb-noun forms: `build-index`, `run-query`, `compare-runs`.
- CLI flags use kebab-case: `--repo-path`, `--output-format`, `--embedding-provider`.
- JSON output fields use `snake_case` to align with Python code and persistence naming.
- Stable machine-readable identifiers always end in `_id`.

**Code Naming Conventions:**
- Python packages and modules use `snake_case`.
- Class names use `PascalCase`.
- Functions, methods, variables, and attributes use `snake_case`.
- Constants use `UPPER_SNAKE_CASE`.
- Protocols / ports end with `Port`: `EmbeddingProviderPort`, `ChunkRepositoryPort`.
- Adapters end with a concrete technology or role suffix: `SqliteRunRepository`, `FilesystemArtifactStore`, `OpenAiEmbeddingAdapter`.
- Command handler modules use `<domain>_commands.py` or `<domain>.py` within the CLI package, not mixed naming styles.

### Structure Patterns

**Project Organization:**
- Use a layered modular monolith under `src/codeman/`.
- Core business rules live in domain-oriented modules, not in CLI entrypoints or persistence adapters.
- Suggested top-level package layout:
  - `cli/`
  - `application/`
  - `domain/`
  - `infrastructure/`
  - `contracts/`
  - `config/`
- Repositories, index adapters, provider clients, and filesystem IO belong in `infrastructure/`.
- Orchestration services and use cases belong in `application/`.
- Pure domain models, policies, enums, and value objects belong in `domain/`.
- Shared cross-cutting DTOs for input/output contracts belong in `contracts/`.

**File Structure Patterns:**
- Tests live in top-level `tests/`, not co-located beside production modules.
- Test layout mirrors source layout by test type:
  - `tests/unit/`
  - `tests/integration/`
  - `tests/e2e/`
- Migration files live in a dedicated `migrations/` root managed by Alembic.
- Local sample configs live in `config/` or documented examples, never mixed into source packages as runtime state.
- Generated artifacts, local indexes, and benchmark outputs never live under `src/`; they belong in runtime-managed workspace directories.

### Format Patterns

**API Response Formats:**
For CLI JSON mode, all commands return one of two top-level shapes only:
- success: `{ "ok": true, "data": ..., "meta": ... }`
- failure: `{ "ok": false, "error": { "code": "...", "message": "...", "details": ... }, "meta": ... }`

Rules:
- `stdout` contains only the final JSON payload in machine-readable mode.
- human progress or diagnostics go to `stderr`, never mixed into JSON `stdout`.
- successful payloads do not include an `error` field.
- failed payloads do not include a `data` field unless explicitly documented for partial results.

**Data Exchange Formats:**
- JSON fields use `snake_case`.
- Date/time values use ISO 8601 UTC strings.
- Durations use explicit millisecond integer fields when numeric comparison matters: `query_latency_ms`.
- Null is preferred over placeholder strings such as `"N/A"` or `"unknown"`.
- Enum-like values use lowercase `snake_case`: `queued`, `running`, `completed`, `failed`.
- Collections always return arrays, even when they contain a single item.

### Communication Patterns

**Event System Patterns:**
The MVP does not require a distributed event bus. If internal domain events are introduced, they must follow these rules:
- event names use lowercase dotted naming: `snapshot.created`, `index.completed`, `benchmark.failed`
- payloads are explicit typed DTOs, not ad hoc dictionaries
- events are internal implementation signals, not a second public interface
- side effects triggered by events must remain idempotent where practical

**State Management Patterns:**
The project has no frontend state store, so “state management” applies to run lifecycle and pipeline status.
- Long-running workflows use explicit lifecycle states: `queued`, `running`, `completed`, `failed`
- State transitions are recorded by the application layer, not hidden inside adapters
- Mutable in-memory state must not be the source of truth for benchmark or query provenance
- Re-runs create new run records rather than mutating old result history

### Process Patterns

**Error Handling Patterns:**
- Domain and application layers raise typed exceptions with stable semantic meaning.
- CLI entrypoints are the boundary that maps exceptions to exit codes and user-facing output.
- Adapter failures should be wrapped into project-specific error types before crossing layer boundaries.
- User-safe messages and diagnostic details are separated deliberately.
- No silent exception swallowing.
- No returning `(success, value)` tuples from core services where exceptions better encode failure semantics.

**Loading State Patterns:**
- Human mode may show progress text or spinners, but JSON mode must remain clean and final-output only.
- Long operations report coarse consistent phases: `snapshot`, `parse`, `chunk`, `embed`, `index`, `evaluate`.
- Progress messages use present-tense verb phrases: `Building snapshot`, `Generating chunks`, `Running benchmark`.
- Partial progress belongs to `stderr`.
- Final status always comes from the formal result object, not from log parsing.

### Enforcement Guidelines

**All AI Agents MUST:**
- preserve the layered package boundaries and never put persistence or provider logic into CLI modules;
- use `snake_case` for modules, JSON fields, config keys, and persistence fields unless a third-party integration forces otherwise;
- keep machine-readable `stdout` clean by sending logs and progress to `stderr`;
- add or update tests in the mirrored `tests/` hierarchy for every behavior change;
- reuse existing DTOs, error codes, and run-state enums instead of inventing near-duplicates.

**Pattern Enforcement:**
- Ruff enforces formatting and import hygiene.
- Tests enforce behavioral consistency and stable command contracts.
- Architecture drift is reviewed by checking whether new code crosses layer boundaries or introduces duplicate contract shapes.
- Pattern exceptions must be documented in the architecture or ADR notes before adoption.

### Pattern Examples

**Good Examples:**
- Module: `src/codeman/application/query_runner.py`
- Class: `QueryRunner`
- Port: `VectorIndexPort`
- Adapter: `SqliteChunkRepository`
- JSON success: `{ "ok": true, "data": { "query_run_id": "..." }, "meta": { "query_latency_ms": 182 } }`
- JSON failure: `{ "ok": false, "error": { "code": "embedding_provider_unavailable", "message": "Embedding provider request failed" }, "meta": { "provider": "openai" } }`
- Test path: `tests/unit/application/test_query_runner.py`

**Anti-Patterns:**
- Mixing CamelCase and snake_case module names such as `QueryRunner.py`
- Printing progress lines to `stdout` before JSON output
- Returning raw provider exceptions directly to the CLI boundary
- Writing benchmark artifacts into `src/` or committing local runtime indexes into the repository
- Adding a second response format for “special cases” instead of extending the standard success/failure envelope

## Project Structure & Boundaries

### Complete Project Directory Structure

```text
codeman/
├── README.md
├── pyproject.toml
├── uv.lock
├── .python-version
├── .gitignore
├── .env.example
├── alembic.ini
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   ├── architecture/
│   │   ├── decisions.md
│   │   └── patterns.md
│   ├── benchmarks.md
│   └── cli-reference.md
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── src/
│   └── codeman/
│       ├── __init__.py
│       ├── __main__.py
│       ├── bootstrap.py
│       ├── runtime.py
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── app.py
│       │   ├── common.py
│       │   ├── repo.py
│       │   ├── index.py
│       │   ├── query.py
│       │   ├── eval.py
│       │   ├── compare.py
│       │   └── config.py
│       ├── config/
│       │   ├── __init__.py
│       │   ├── defaults.py
│       │   ├── models.py
│       │   ├── loader.py
│       │   └── paths.py
│       ├── contracts/
│       │   ├── __init__.py
│       │   ├── common.py
│       │   ├── errors.py
│       │   ├── repository.py
│       │   ├── retrieval.py
│       │   ├── evaluation.py
│       │   └── diagnostics.py
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── repository/
│       │   │   ├── __init__.py
│       │   │   ├── entities.py
│       │   │   ├── value_objects.py
│       │   │   └── policies.py
│       │   ├── chunking/
│       │   │   ├── __init__.py
│       │   │   ├── entities.py
│       │   │   ├── serializers.py
│       │   │   └── policies.py
│       │   ├── retrieval/
│       │   │   ├── __init__.py
│       │   │   ├── entities.py
│       │   │   ├── ranking.py
│       │   │   ├── fusion.py
│       │   │   └── explanations.py
│       │   ├── evaluation/
│       │   │   ├── __init__.py
│       │   │   ├── entities.py
│       │   │   ├── metrics.py
│       │   │   └── policies.py
│       │   ├── runs/
│       │   │   ├── __init__.py
│       │   │   ├── entities.py
│       │   │   └── enums.py
│       │   └── errors.py
│       ├── application/
│       │   ├── __init__.py
│       │   ├── ports/
│       │   │   ├── __init__.py
│       │   │   ├── snapshot_port.py
│       │   │   ├── parser_port.py
│       │   │   ├── chunker_port.py
│       │   │   ├── lexical_index_port.py
│       │   │   ├── vector_index_port.py
│       │   │   ├── embedding_provider_port.py
│       │   │   ├── artifact_store_port.py
│       │   │   ├── metadata_store_port.py
│       │   │   └── run_logger_port.py
│       │   ├── repo/
│       │   │   ├── register_repository.py
│       │   │   ├── create_snapshot.py
│       │   │   └── reindex_repository.py
│       │   ├── indexing/
│       │   │   ├── extract_source_files.py
│       │   │   ├── build_chunks.py
│       │   │   ├── build_embeddings.py
│       │   │   ├── build_lexical_index.py
│       │   │   └── build_vector_index.py
│       │   ├── query/
│       │   │   ├── run_lexical_query.py
│       │   │   ├── run_semantic_query.py
│       │   │   ├── run_hybrid_query.py
│       │   │   └── format_results.py
│       │   ├── evaluation/
│       │   │   ├── run_benchmark.py
│       │   │   ├── compare_runs.py
│       │   │   └── generate_report.py
│       │   └── diagnostics/
│       │       ├── record_run_manifest.py
│       │       ├── redact_output.py
│       │       └── collect_debug_bundle.py
│       ├── infrastructure/
│       │   ├── __init__.py
│       │   ├── persistence/
│       │   │   └── sqlite/
│       │   │       ├── __init__.py
│       │   │       ├── engine.py
│       │   │       ├── tables.py
│       │   │       ├── migrations.py
│       │   │       └── repositories/
│       │   │           ├── repository_repository.py
│       │   │           ├── snapshot_repository.py
│       │   │           ├── chunk_repository.py
│       │   │           ├── run_repository.py
│       │   │           └── benchmark_repository.py
│       │   ├── artifacts/
│       │   │   ├── __init__.py
│       │   │   ├── filesystem_artifact_store.py
│       │   │   └── manifest_writer.py
│       │   ├── snapshotting/
│       │   │   ├── __init__.py
│       │   │   ├── local_repository_scanner.py
│       │   │   ├── git_revision_resolver.py
│       │   │   └── snapshot_manifest_builder.py
│       │   ├── parsers/
│       │   │   ├── __init__.py
│       │   │   ├── parser_registry.py
│       │   │   ├── php_parser.py
│       │   │   ├── javascript_parser.py
│       │   │   ├── html_parser.py
│       │   │   └── twig_parser.py
│       │   ├── chunkers/
│       │   │   ├── __init__.py
│       │   │   ├── chunker_registry.py
│       │   │   ├── php_chunker.py
│       │   │   ├── javascript_chunker.py
│       │   │   ├── html_chunker.py
│       │   │   └── twig_chunker.py
│       │   ├── embeddings/
│       │   │   ├── __init__.py
│       │   │   ├── cache.py
│       │   │   ├── registry.py
│       │   │   └── serializers.py
│       │   ├── indexes/
│       │   │   ├── __init__.py
│       │   │   ├── lexical/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── builder.py
│       │   │   │   └── query_engine.py
│       │   │   └── vector/
│       │   │       ├── __init__.py
│       │   │       ├── builder.py
│       │   │       └── query_engine.py
│       │   ├── logging/
│       │   │   ├── __init__.py
│       │   │   ├── jsonl_run_logger.py
│       │   │   └── console_reporter.py
│       │   └── config/
│       │       ├── __init__.py
│       │       ├── file_config_loader.py
│       │       └── env_secret_loader.py
│       └── mcp/
│           └── README.md
├── tests/
│   ├── fixtures/
│   │   ├── repositories/
│   │   │   └── mixed_stack_fixture/
│   │   ├── queries/
│   │   │   └── golden_queries.json
│   │   └── benchmark_reports/
│   ├── support/
│   │   ├── factories.py
│   │   ├── builders.py
│   │   └── runtime_helpers.py
│   ├── unit/
│   │   ├── domain/
│   │   ├── application/
│   │   └── cli/
│   ├── integration/
│   │   ├── persistence/
│   │   ├── indexing/
│   │   ├── query/
│   │   └── evaluation/
│   └── e2e/
│       ├── test_cli_index.py
│       ├── test_cli_query.py
│       └── test_cli_eval.py
└── .codeman/
    ├── artifacts/
    ├── indexes/
    ├── cache/
    ├── logs/
    └── tmp/
```

### Architectural Boundaries

**API Boundaries:**
- The only MVP public interface is the CLI layer in `src/codeman/cli/`.
- CLI modules parse arguments, call application use cases, and format output; they do not contain business rules, persistence logic, or provider-specific code.
- The future MCP boundary is reserved in `src/codeman/mcp/` as a placeholder only and must reuse the same `application/` services and `contracts/` DTOs rather than introducing parallel logic.
- External provider communication is isolated under `src/codeman/infrastructure/embeddings/` and never called directly from CLI commands.

**Component Boundaries:**
- `domain/` contains pure domain concepts, ranking/fusion policies, invariants, and run-state rules.
- `application/` contains orchestration and use cases for snapshotting, indexing, querying, evaluating, and diagnostics.
- `infrastructure/` contains concrete adapters for SQLite, filesystem artifacts, parsers, chunkers, embedding providers, logging, and index backends.
- `contracts/` is a boundary-only layer for stable DTOs, CLI JSON envelopes, diagnostic payloads, and serializable adapter-facing shapes. It is not a general utility package.
- `config/` contains settings models and resolution logic, separate from runtime adapters.
- `bootstrap.py` is the single composition root that wires ports to infrastructure implementations for CLI and test execution.

**Service Boundaries:**
- Repository ingestion services live in `application/repo/` and call snapshotting adapters plus metadata/artifact ports.
- Parsing and chunking orchestration lives in `application/indexing/`, while language-specific implementations live in `infrastructure/parsers/` and `infrastructure/chunkers/`.
- Query orchestration lives in `application/query/`, while lexical/vector engines remain behind ports and concrete adapters.
- Evaluation workflows live in `application/evaluation/` and depend on query services plus metrics logic from `domain/evaluation/`.
- Diagnostics stay isolated in `application/diagnostics/` and `infrastructure/logging/`.
- Each application file represents one primary use case entrypoint, not a large mixed-responsibility service module.

**Data Boundaries:**
- SQLite metadata is the source of truth for repositories, snapshots, chunks, runs, and benchmark results.
- Filesystem artifacts store manifests, exported payloads, generated reports, and index build outputs.
- Index engine internals live under runtime-managed `.codeman/indexes/` and are never treated as hand-edited source files.
- Secrets and sensitive provider configuration enter through environment or protected local config, never through committed source files.
- Runtime paths are resolved through `runtime.py` and configuration, so tests and future interfaces can inject isolated workspaces instead of writing to a hardcoded global path.

### Requirements to Structure Mapping

**Feature/Epic Mapping:**
- Repository ingestion and content structuring:
  - `src/codeman/application/repo/`
  - `src/codeman/infrastructure/snapshotting/`
  - `src/codeman/infrastructure/parsers/`
  - `src/codeman/infrastructure/chunkers/`
  - `src/codeman/domain/repository/`
  - `src/codeman/domain/chunking/`
- Search and retrieval workflows:
  - `src/codeman/cli/query.py`
  - `src/codeman/application/query/`
  - `src/codeman/domain/retrieval/`
  - `src/codeman/infrastructure/indexes/`
  - `src/codeman/infrastructure/embeddings/`
- Retrieval configuration and experiment control:
  - `src/codeman/cli/config.py`
  - `src/codeman/config/`
  - `src/codeman/contracts/common.py`
  - `src/codeman/infrastructure/config/`
- Evaluation and benchmarking:
  - `src/codeman/cli/eval.py`
  - `src/codeman/cli/compare.py`
  - `src/codeman/application/evaluation/`
  - `src/codeman/domain/evaluation/`
  - `tests/fixtures/queries/`
- CLI operations and troubleshooting:
  - `src/codeman/cli/`
  - `src/codeman/application/diagnostics/`
  - `src/codeman/contracts/errors.py`
  - `src/codeman/infrastructure/logging/`
- Future MCP expansion:
  - `src/codeman/mcp/`
  - reuses `src/codeman/application/`, `src/codeman/contracts/`, and existing domain logic

**Cross-Cutting Concerns:**
- Configuration traceability:
  - `src/codeman/config/`
  - `src/codeman/contracts/`
  - `src/codeman/application/diagnostics/record_run_manifest.py`
- Security and provider transparency:
  - `src/codeman/infrastructure/config/env_secret_loader.py`
  - `src/codeman/infrastructure/embeddings/`
  - `src/codeman/application/diagnostics/redact_output.py`
- JSON CLI contract consistency:
  - `src/codeman/contracts/`
  - `src/codeman/cli/common.py`
- Persistence and reproducibility:
  - `src/codeman/infrastructure/persistence/sqlite/`
  - `src/codeman/infrastructure/artifacts/`
  - `.codeman/artifacts/`
- Test reuse and isolated runtime execution:
  - `tests/support/`
  - `tests/fixtures/`
  - `src/codeman/runtime.py`

### Integration Points

**Internal Communication:**
- CLI command modules call application use cases only.
- Application use cases depend on ports from `application/ports/`.
- Infrastructure adapters implement those ports and are wired in `bootstrap.py`.
- Domain rules are invoked by application services but do not depend on CLI or infrastructure packages.

**External Integrations:**
- Local filesystem and Git metadata through `infrastructure/snapshotting/`.
- Optional embedding providers through `infrastructure/embeddings/`.
- Future MCP transport through `src/codeman/mcp/`, using the same application services and contracts.

**Data Flow:**
- Repository path -> snapshot manifest -> parsed source units -> structured chunks -> embedding documents -> lexical/vector indexes -> fused retrieval results -> CLI contract DTOs -> human or JSON output.
- Benchmark flow reuses query services, then persists metrics and artifacts for before/after comparison.
- Runtime outputs go through resolved workspace paths so local runs, tests, and future integration surfaces can stay isolated.

### File Organization Patterns

**Configuration Files:**
- Root-level operational configuration lives in `pyproject.toml`, `alembic.ini`, `.env.example`, and CI workflow files.
- Runtime-resolved settings live in `src/codeman/config/`.
- Secrets never live in committed config files.

**Source Organization:**
- Business rules and policies stay in `domain/`.
- Use-case orchestration stays in `application/`.
- IO and technology-specific implementations stay in `infrastructure/`.
- Public contract schemas stay in `contracts/`.
- User-facing command surfaces stay in `cli/`.

**Test Organization:**
- `tests/unit/` covers domain policies, pure application logic, and contract formatting.
- `tests/integration/` covers SQLite persistence, filesystem artifact storage, parsing/chunking pipelines, and index adapter integration.
- `tests/e2e/` covers CLI flows for indexing, querying, and benchmarking.
- `tests/fixtures/` contains controlled mixed-stack repositories, golden queries, and reusable benchmark inputs.
- `tests/support/` contains reusable factories, builders, and helpers for isolated runtime setup.

**Asset Organization:**
- Runtime indexes, caches, logs, and generated artifacts live under `.codeman/` and are gitignored.
- Human documentation lives in `docs/`.
- Benchmark reports generated during execution go to `.codeman/artifacts/` and may optionally be exported elsewhere.

### Development Workflow Integration

**Development Server Structure:**
- There is no long-running development server in the MVP.
- Development flows run from the repository root through `uv run codeman ...`.
- `bootstrap.py` is the composition root for local CLI execution and test wiring.

**Build Process Structure:**
- Packaging and dependency resolution are driven from `pyproject.toml` and `uv.lock`.
- Schema evolution is driven from `migrations/` and `alembic.ini`.
- CI runs linting, tests, and smoke benchmarks from the repository root using the same CLI entrypoints as local development.

**Deployment Structure:**
- MVP deployment is local installation and execution only.
- The repo structure supports packaging as a CLI application now and leaves a clean insertion point for future MCP transport without reorganizing the core codebase.

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
The architecture is internally coherent. The selected starter foundation, Python 3.13 baseline, Typer CLI surface, Pydantic validation layer, SQLAlchemy Core + Alembic metadata persistence, and the modular monolith with ports-and-adapters boundaries all fit together without contradictions.

The local-first operating model is consistent with the decision to avoid a hosted MVP, avoid a public HTTP API, and defer MCP transport to Phase 2. The split persistence model is also compatible with the retrieval-platform goal: SQLite stores provenance and experiment metadata, while filesystem-managed artifacts and index directories handle heavy runtime outputs.

Deferred decisions such as the exact lexical index engine, vector index engine, and default embedding provider do not invalidate architectural readiness because the architecture already isolates them behind ports and adapter boundaries.

**Pattern Consistency:**
The implementation patterns support the architectural decisions well.
- `snake_case` naming aligns across Python modules, JSON contracts, and relational persistence.
- CLI-only public boundaries align with the JSON/stdout rules and structured error envelope.
- The rule that `contracts/` is boundary-only supports DTO stability and prevents cross-layer leakage.
- Error handling, progress reporting, and runtime-path rules are consistent with the CLI-first and reproducibility-focused design.

**Structure Alignment:**
The project structure supports the architecture directly.
- `cli/`, `application/`, `domain/`, and `infrastructure/` map cleanly to the selected modular monolith shape.
- `bootstrap.py` as a single composition root supports consistent port wiring.
- `runtime.py` and `.codeman/` support isolated workspace handling for local runs and tests.
- `tests/unit`, `tests/integration`, `tests/e2e`, `tests/support`, and `tests/fixtures` align with the chosen implementation and validation patterns.

### Requirements Coverage Validation ✅

**Epic/Feature Coverage:**
No epics were used, so coverage is validated against functional requirement categories from the PRD. Every major capability area has an architectural home:
- repository ingestion and structuring are covered by `application/repo/`, snapshotting adapters, parsers, and chunkers;
- retrieval workflows are covered by query orchestration, retrieval domain policies, and index/embedding adapters;
- experiment control is covered by configuration models, run manifests, metadata persistence, and diagnostics;
- evaluation is covered by benchmark use cases, metrics logic, and report generation;
- CLI operations and troubleshooting are covered by the command surface, diagnostics flow, structured logging, and consistent error contracts;
- future MCP reuse is covered by preserving application/service reuse and a reserved interface boundary.

**Functional Requirements Coverage:**
All 31 functional requirements are architecturally supported.
- FR1-FR6 are covered by repository registration, snapshotting, parsing, chunking, metadata persistence, and re-indexing flows.
- FR7-FR12 are covered by lexical, semantic, and hybrid query orchestration plus result formatting.
- FR13-FR17 are covered by layered configuration, experiment metadata, run manifests, and reusable config models.
- FR18-FR23 are covered by benchmark execution, metrics, comparison workflows, and benchmark/run persistence.
- FR24-FR28 are covered by the CLI surface, diagnostics, structured errors, and subsystem boundaries.
- FR29-FR31 are covered by the reserved MCP boundary and shared application/contracts layers.

**Non-Functional Requirements Coverage:**
The non-functional requirements are addressed architecturally.
- Performance is addressed by explicit latency tracking, incremental caching, and bounded local execution.
- Security and data handling are addressed through local-first defaults, opt-in provider use, secret isolation, and redacted diagnostics.
- Reliability and reproducibility are addressed through immutable run/snapshot records, run manifests, structured logging, and metadata capture.
- Maintainability and extensibility are addressed through ports-and-adapters boundaries, modular package layout, and deferred engine choices behind ports.
- Integration consistency is addressed by keeping CLI as the only MVP interface and reserving MCP for reuse of the same core services.

### Implementation Readiness Validation ✅

**Decision Completeness:**
The architecture is sufficiently complete for implementation handoff.
- Critical decisions are documented.
- Version-sensitive foundation technologies are specified.
- Deferred decisions are explicitly identified rather than left ambiguous.
- Security, persistence, configuration, output contracts, and diagnostics all have clear architectural direction.

**Structure Completeness:**
The project structure is concrete and implementation-ready.
- The repository tree is specific rather than generic.
- The main packages, test areas, migrations, documentation locations, and runtime artifact paths are defined.
- Composition and runtime boundaries are explicit.
- Future interface growth has a reserved location without polluting the MVP code path.

**Pattern Completeness:**
The implementation patterns are complete enough to guide multiple AI agents consistently.
- Naming conventions are explicit.
- Output and error formats are standardized.
- Layer boundaries are clearly stated.
- Test organization, runtime isolation, and anti-patterns are documented.

### Gap Analysis Results

**Critical Gaps:**
No critical architectural gaps were found. Nothing currently blocks MVP implementation from starting.

**Important Gaps:**
- The exact lexical index engine remains intentionally deferred and should be finalized before implementing the lexical adapter.
- The exact vector index engine remains intentionally deferred and should be finalized before implementing the semantic retrieval adapter.
- The default embedding provider profile remains intentionally deferred and should be finalized before implementing external-provider integration.
- Runtime cleanup and retention policy for `.codeman/artifacts`, `.codeman/cache`, and `.codeman/indexes` should be documented early in implementation to avoid drift in local behavior.

These are not blockers because the architecture already isolates them behind ports and runtime-path abstractions.

**Nice-to-Have Gaps:**
- A short ADR log for engine-selection decisions would help future comparison work.
- A documented benchmark fixture policy would help keep golden-query evaluation stable over time.
- A small contributor guide for boundary rules could reduce onboarding friction for future agents and humans.

### Validation Issues Addressed

No blocking issues required architectural redesign.

The main issues found during validation were clarification issues rather than design flaws:
- `contracts/` was tightened into a boundary-only layer to prevent it from becoming a utility dumping ground.
- `bootstrap.py` was clarified as the single composition root.
- runtime paths were made injectable through `runtime.py` instead of treated as a hardcoded global concern.
- `tests/support/` was added to keep shared helpers from fragmenting across the test tree.
- `mcp/` was preserved as a Phase 2 placeholder only, preventing premature interface sprawl.

### Architecture Completeness Checklist

**✅ Requirements Analysis**

- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**✅ Architectural Decisions**

- [x] Critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Performance considerations addressed

**✅ Implementation Patterns**

- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Communication patterns specified
- [x] Process patterns documented

**✅ Project Structure**

- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** High based on validation results

**Key Strengths:**
- Strong alignment between PRD goals and architectural boundaries
- Clear modularity for retrieval experimentation without premature distributed complexity
- Good implementation consistency rules for multi-agent development
- Explicit treatment of reproducibility, diagnostics, and provider transparency
- Concrete project structure with low ambiguity for implementation handoff

**Areas for Future Enhancement:**
- Final engine/provider selections via ADR-style follow-up decisions
- Broader benchmark fixture governance
- More explicit operational retention and cleanup policy for runtime artifacts
- Phase 2 MCP contract definition once MVP behavior stabilizes

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented
- Use implementation patterns consistently across all components
- Respect project structure and boundaries
- Refer to this document for all architectural questions

**First Implementation Priority:**
Initialize the project with `uv init --package codeman`, then establish the composition root, Typer CLI surface, configuration models, and persistence/contracts foundation before building retrieval adapters.
