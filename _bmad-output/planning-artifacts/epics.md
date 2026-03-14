---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - /Users/vdubyna/Workspace/AI__AGENTS/codeman/_bmad-output/planning-artifacts/prd.md
  - /Users/vdubyna/Workspace/AI__AGENTS/codeman/_bmad-output/planning-artifacts/architecture.md
---

# codeman - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for codeman, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Internal engineers can register a local repository for indexing and retrieval workflows.
FR2: Internal engineers can create a normalized repository snapshot from a local repository.
FR3: Internal engineers can extract retrievable content from supported repository file types.
FR4: Internal engineers can generate structurally meaningful retrieval units from indexed repository content.
FR5: Internal engineers can access metadata associated with retrievable units, including source context and identity information.
FR6: Internal engineers can re-index a repository after source or configuration changes.
FR7: Internal engineers can run lexical retrieval queries against indexed repository content.
FR8: Internal engineers can run semantic retrieval queries against indexed repository content.
FR9: Internal engineers can run hybrid retrieval queries that combine multiple retrieval strategies.
FR10: Internal engineers can receive ranked retrieval results for a given query.
FR11: Internal engineers can inspect retrieval outputs that are suitable for reasoning, navigation, and implementation workflows.
FR12: Internal engineers can compare retrieval results across different query modes for the same repository question.
FR13: Maintainers can configure retrieval-related components used by the system.
FR14: Maintainers can configure embedding-related settings independently from other indexing settings.
FR15: Maintainers can configure retrieval strategies and experiment variants without redefining the entire system.
FR16: Maintainers can identify which configuration was used for a specific indexing or retrieval run.
FR17: Maintainers can reuse previously defined retrieval configurations in later experiments.
FR18: Internal engineers can execute benchmark runs against indexed repositories.
FR19: Internal engineers can evaluate retrieval behavior using golden-query test cases.
FR20: Internal engineers can review benchmark outputs for a retrieval configuration.
FR21: Internal engineers can compare benchmark results across retrieval strategies.
FR22: Internal engineers can identify retrieval regressions between experiment runs.
FR23: Internal engineers can associate benchmark results with the retrieval configuration that produced them.
FR24: Internal engineers can execute core indexing, retrieval, and evaluation workflows through the CLI.
FR25: Internal engineers can use the CLI in repeated experimental workflows without requiring manual system reconfiguration each time.
FR26: Maintainers can diagnose failed indexing runs.
FR27: Maintainers can diagnose failed retrieval or evaluation runs.
FR28: Maintainers can identify which subsystem is most likely responsible for a failed or degraded run.
FR29: Phase 2 users can access retrieval workflows through an MCP interface.
FR30: Phase 2 users can receive retrieval outputs through MCP that are consistent with the core retrieval behavior established by the CLI.
FR31: Future interfaces can reuse the same retrieval capabilities without redefining core indexing and retrieval behavior.

### NonFunctional Requirements

NFR1: On the reference benchmark repository used by the team, lexical retrieval queries executed through the CLI shall return ranked results within 2 seconds under the baseline development environment.
NFR2: On the reference benchmark repository used by the team, semantic and hybrid retrieval queries executed through the CLI shall return ranked results within 5 seconds under the baseline development environment.
NFR3: The system shall record indexing time and query latency for every benchmarked run so performance can be compared across configurations.
NFR4: Performance reporting shall be consistent enough to support before/after comparison across retrieval strategies on the same corpus and environment.
NFR5: Repository contents and derived retrieval artifacts shall remain local by default.
NFR6: The system shall not send repository code, chunk content, embeddings, or query content to external providers unless an external provider is explicitly configured for that workflow.
NFR7: When an external embedding provider is used, the system shall make that provider usage visible to the operator in configuration or runtime output.
NFR8: Secrets required for provider access shall not be hard-coded in source control and shall be supplied through environment variables, secure configuration, or equivalent protected mechanisms.
NFR9: Diagnostic output shall avoid exposing full repository contents by default, except where an explicit debug mode is enabled.
NFR10: Given the same repository revision, configuration, and benchmark dataset, repeated benchmark runs shall be reproducible and attributable to the same experiment context.
NFR11: Every indexing, query, and benchmark run shall capture sufficient metadata to identify the repository input, retrieval configuration, embedding provider, model version, and execution timestamp.
NFR12: CLI workflows shall produce clear success and failure outcomes, including non-zero exit behavior for failed operational runs.
NFR13: Failures in indexing, retrieval, and evaluation workflows shall return actionable diagnostic information that helps identify the affected subsystem.
NFR14: Benchmark outputs shall support regression detection across retrieval strategies and experiment runs.
NFR15: The system shall preserve bounded module responsibilities for repository snapshotting, parsing, chunking, embeddings, lexical retrieval, vector retrieval, fusion, output formatting, and evaluation.
NFR16: Introducing a new chunking strategy, embedding provider, or retrieval fusion variant shall require localized changes rather than cross-system rewrites.
NFR17: CLI command handlers shall rely on shared internal services so retrieval logic is not duplicated across operational entrypoints.
NFR18: Architecture and configuration boundaries shall be documented clearly enough that internal engineers can extend the system without reverse-engineering core workflows.
NFR19: The MVP shall provide a stable CLI interface for indexing, retrieval, and evaluation workflows.
NFR20: CLI behavior shall remain scriptable and deterministic enough to support repeated internal experimentation workflows.
NFR21: Phase 2 MCP integration shall reuse the same core retrieval services and retrieval semantics established by the CLI baseline.
NFR22: Future interfaces shall not require redefining indexing, retrieval, or evaluation behavior already implemented in the core platform.

### Additional Requirements

- Epic 1 Story 1 must initialize the project with `uv init --package codeman` as the selected starter template.
- The runtime baseline must be Python 3.13.x with uv as the official workflow for environment setup, dependency management, execution, testing, and benchmarking.
- The MVP must be implemented as a modular monolith with explicit ports-and-adapters boundaries separating CLI, application, domain, contracts, config, and infrastructure layers.
- The CLI contract must use Typer 0.20.0 with a multi-command structure and support both human-readable output and machine-readable JSON output.
- The persistence model must be split across a SQLite-compatible relational metadata store, a filesystem artifact store, and adapter-owned local index directories.
- Core first-class entities must include Repository, Snapshot, SourceFile, Chunk, EmbeddingDocument, IndexBuild, QueryRun, BenchmarkRun, and ExperimentConfig.
- Pydantic 2.12.5 must validate CLI inputs, configuration models, provider configuration, adapter contracts, and serialized output DTOs.
- SQLAlchemy Core 2.0.44 plus Alembic 1.17.2 must be used for metadata persistence access and schema evolution.
- Incremental caching must be content-hash-based for snapshots, parser outputs, chunk generation, and embeddings, with embedding cache keys including provider identity, model version, and chunk serialization version.
- The MVP must remain local-first, with no built-in user authentication, no HTTP API, and no distributed runtime components.
- Recommended CLI command groups are `repo`, `index`, `query`, `eval`, `compare`, and `config`.
- Machine-readable CLI responses must use only two top-level JSON envelopes: success `{ "ok": true, "data": ..., "meta": ... }` and failure `{ "ok": false, "error": { ... }, "meta": ... }`.
- In JSON mode, `stdout` must contain only the final JSON payload; progress, logs, and diagnostics must go to `stderr`.
- Long-running operations must report consistent phases such as `snapshot`, `parse`, `chunk`, `embed`, `index`, and `evaluate`.
- Domain and application errors must be mapped to stable exit codes, user-safe console messages, and structured JSON error payloads.
- Structured run manifests and JSONL logging must be implemented for provenance, diagnostics, and regression investigation.
- Configuration must be layered across `pyproject.toml` defaults, user-local application config, per-run CLI overrides, and environment variables for secrets and final overrides.
- External embedding providers must be opt-in only, and runtime output plus recorded metadata must make provider identity and model usage visible for every run.
- Secrets must never be committed to source control or written into benchmark result files.
- Diagnostic output must be redacted by default and require explicit verbose or debug mode before revealing sensitive repository excerpts.
- Runtime-managed directories for artifacts, indexes, cache, logs, and temp files must live under `.codeman/` and stay outside `src/`.
- `bootstrap.py` must act as the single composition root that wires ports to infrastructure implementations.
- Runtime paths must be resolved through `runtime.py` and configuration so tests and future interfaces can use isolated workspaces.
- Tests must live under `tests/unit/`, `tests/integration/`, and `tests/e2e/`, with reusable fixtures and support helpers separated from production code.
- A repository-native CI pipeline must enforce lint and format checks, unit tests, retrieval smoke tests, and benchmark smoke execution.
- Ruff and pytest are required early foundation additions to support consistency and validation.
- The exact lexical index engine, vector index engine, and default embedding provider are intentionally deferred, so stable adapter ports must be defined before concrete engine selection.
- The future MCP interface must be reserved under `src/codeman/mcp/` and reuse the same application services and contract DTOs rather than creating a parallel execution path.
- The directory structure and package layout defined in the architecture document must be treated as the implementation baseline for stories and acceptance criteria.

### UX Design Requirements

No separate UX design document was provided for this workflow. No UX-specific implementation requirements were extracted at this step.

### FR Coverage Map

FR1: Epic 1 - register a local repository
FR2: Epic 1 - create a normalized repository snapshot
FR3: Epic 1 - extract retrievable content from supported files
FR4: Epic 1 - generate structured retrieval units
FR5: Epic 1 - expose retrieval metadata and source identity
FR6: Epic 1 - re-index after source or config changes
FR7: Epic 2 - run lexical retrieval
FR8: Epic 2 - run semantic retrieval
FR9: Epic 2 - run hybrid retrieval
FR10: Epic 2 - return ranked retrieval results
FR11: Epic 2 - provide agent-usable retrieval outputs
FR12: Epic 2 - compare query modes for the same question
FR13: Epic 3 - configure retrieval components
FR14: Epic 3 - configure embedding settings independently
FR15: Epic 3 - define retrieval strategies and experiment variants
FR16: Epic 3 - identify configuration used by a run
FR17: Epic 3 - reuse prior configurations
FR18: Epic 4 - execute benchmark runs
FR19: Epic 4 - evaluate with golden-query cases
FR20: Epic 4 - review benchmark outputs
FR21: Epic 4 - compare benchmark results across strategies
FR22: Epic 4 - detect regressions
FR23: Epic 4 - associate results with the generating configuration
FR24: Epic 5 - execute core workflows through the CLI
FR25: Epic 5 - support repeated CLI experimentation without manual reconfiguration
FR26: Epic 5 - diagnose failed indexing runs
FR27: Epic 5 - diagnose failed retrieval or evaluation runs
FR28: Epic 5 - identify the likely failing subsystem
FR29: Epic 5 - expose retrieval workflows through MCP in Phase 2
FR30: Epic 5 - keep MCP retrieval outputs consistent with CLI behavior
FR31: Epic 5 - let future interfaces reuse the same core retrieval capabilities

## Epic List

### Epic 1: Onboard a Repository and Build a Structured Index
Internal engineers can initialize codeman, register a local repository, create normalized snapshots, generate structure-aware retrieval units, and re-index safely after source or configuration changes.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6

### Epic 2: Retrieve Useful Repository Context
Internal engineers can run lexical, semantic, and hybrid retrieval and receive ranked, metadata-rich results that are useful for reasoning, navigation, and implementation work.
**FRs covered:** FR7, FR8, FR9, FR10, FR11, FR12

### Epic 3: Configure and Reuse Retrieval Strategies
Maintainers can define retrieval and embedding configurations, reuse them across experiments, and know exactly which configuration produced a given indexing or retrieval run.
**FRs covered:** FR13, FR14, FR15, FR16, FR17

### Epic 4: Benchmark Retrieval Quality and Compare Strategies
Internal engineers can execute golden-query benchmarks, inspect reports, compare retrieval strategies, and identify regressions with reproducible evidence.
**FRs covered:** FR18, FR19, FR20, FR21, FR22, FR23

### Epic 5: Operate, Diagnose, and Prepare for Extension
Internal engineers can run the platform reliably through the CLI, diagnose failures down to the likely subsystem, and keep the retrieval core ready for future MCP and interface reuse without splitting behavior.
**FRs covered:** FR24, FR25, FR26, FR27, FR28, FR29, FR30, FR31

## Epic 1: Onboard a Repository and Build a Structured Index

Internal engineers can initialize codeman, register a local repository, create normalized snapshots, generate structure-aware retrieval units, and re-index safely after source or configuration changes.

### Story 1.1: Set Up Initial Project from Starter Template

As an internal engineer,
I want a working codeman package and CLI skeleton,
So that I can run and extend the platform consistently from day one.

**Requirements:** FR24

**Acceptance Criteria:**

**Given** a clean project workspace
**When** the foundation story is implemented
**Then** the project is initialized with `uv init --package codeman`, Python `3.13.x`, `src/codeman/` package layout, and a Typer-based CLI entrypoint
**And** `uv run codeman --help` succeeds

**Given** the same initialized workspace
**When** a developer inspects the baseline structure
**Then** `bootstrap.py`, `runtime.py`, config models, contracts skeletons, and test/lint foundations for `pytest` and `Ruff` are present in the expected architecture locations
**And** the layout matches the approved architecture baseline closely enough for future stories to build on it without restructuring

### Story 1.2: Register a Local Repository

As an internal engineer,
I want to register a local repository as an indexing target,
So that codeman can track it and prepare runtime storage for retrieval workflows.

**Requirements:** FR1

**Acceptance Criteria:**

**Given** a valid local repository path
**When** I run the repository registration command
**Then** codeman stores repository identity and path metadata in the metadata store
**And** creates the required runtime directories under `.codeman/`

**Given** an invalid or unreadable repository path
**When** I attempt registration
**Then** the command fails with a stable non-zero exit outcome and user-safe diagnostic output
**And** no partial repository record is persisted

### Story 1.3: Create a Normalized Repository Snapshot

As an internal engineer,
I want to create an immutable snapshot of a registered repository,
So that indexing and later evaluation runs are attributable to a specific repository state.

**Requirements:** FR2

**Acceptance Criteria:**

**Given** a registered repository
**When** I run snapshot creation
**Then** codeman records a snapshot entry with repository identity, timestamp, and revision identity
**And** writes a normalized snapshot manifest artifact to local storage

**Given** a repository without resolvable Git metadata
**When** snapshot creation runs
**Then** codeman still creates a usable snapshot using a deterministic fallback identity strategy
**And** marks the revision source clearly in stored metadata

### Story 1.4: Extract Supported Source Files into a Source Inventory

As an internal engineer,
I want codeman to identify supported source files from a snapshot,
So that only relevant PHP, JavaScript, HTML, and Twig content enters retrieval indexing.

**Requirements:** FR3, FR5

**Acceptance Criteria:**

**Given** a completed snapshot
**When** source extraction runs
**Then** codeman identifies supported files, classifies them by target language, and stores source file metadata for downstream indexing
**And** preserves enough path and identity information to trace later chunks back to their origin

**Given** unsupported, ignored, or binary files in the snapshot
**When** extraction runs
**Then** those files are skipped safely
**And** diagnostics summarize the exclusion without exposing unnecessary file contents

### Story 1.5: Generate Structure-Aware Retrieval Chunks

As an internal engineer,
I want codeman to generate structured retrieval units from supported files,
So that later search operates on coherent chunks instead of coarse whole-file blobs.

**Requirements:** FR4, FR5

**Acceptance Criteria:**

**Given** extracted supported source files
**When** chunk generation runs
**Then** codeman produces chunk records with stable identifiers, source references, language metadata, and location/span metadata
**And** persists both metadata records and local chunk payload artifacts

**Given** parser coverage is incomplete for a supported language file
**When** chunk generation cannot use the preferred structural strategy
**Then** codeman degrades gracefully to a safe fallback chunking path
**And** records diagnostic context without failing the entire run unnecessarily

### Story 1.6: Re-index After Source or Configuration Changes

As an internal engineer,
I want to re-index after source or configuration changes,
So that the repository stays current without blindly rebuilding everything every time.

**Requirements:** FR6

**Acceptance Criteria:**

**Given** an already indexed repository
**When** source files or indexing configuration change
**Then** codeman can run a re-index flow that detects what changed and creates a new attributable run outcome
**And** reuses prior artifacts where change detection allows it

**Given** a re-index run completes
**When** I inspect the result metadata
**Then** I can see which repository state and configuration produced the new output
**And** whether work was rebuilt or reused from cache

## Epic 2: Retrieve Useful Repository Context

Internal engineers can run lexical, semantic, and hybrid retrieval and receive ranked, metadata-rich results that are useful for reasoning, navigation, and implementation work.

### Story 2.1: Build Lexical Index Artifacts

As an internal engineer,
I want codeman to build a lexical index from generated retrieval chunks,
So that lexical queries can run quickly and consistently against the indexed repository.

**Requirements:** FR7

**Acceptance Criteria:**

**Given** a repository with generated retrieval chunks
**When** lexical indexing is run
**Then** codeman builds and stores a lexical index from chunk content and relevant metadata
**And** records enough index metadata to attribute the lexical index to a specific repository state and run context

**Given** lexical index artifacts already exist for an older chunk set or repository state
**When** lexical indexing is run again
**Then** codeman refreshes or rebuilds the lexical index as needed for the current state
**And** does not execute lexical queries against stale index artifacts

### Story 2.2: Run Lexical Retrieval Against Indexed Chunks

As an internal engineer,
I want to run lexical queries against indexed repository chunks,
So that I can find exact symbols, identifiers, and text matches in the repository quickly.

**Requirements:** FR7, FR10

**Acceptance Criteria:**

**Given** a repository with generated retrieval chunks
**When** I run a lexical query through the CLI
**Then** codeman searches a lexical index built from chunk content and metadata
**And** returns ranked matches for the query

**Given** the same lexical query in machine-readable mode
**When** the command completes successfully
**Then** `stdout` contains only the standard JSON success envelope
**And** progress or diagnostics are written to `stderr`

### Story 2.3: Present Agent-Friendly Ranked Retrieval Results

As an internal engineer,
I want retrieval results to include useful metadata and explanations,
So that I can understand relevance and use the output directly in reasoning and implementation workflows.

**Requirements:** FR10, FR11

**Acceptance Criteria:**

**Given** a successful retrieval run
**When** results are returned in human or JSON mode
**Then** each result includes stable chunk identity, source file reference, language metadata, and rank-related information
**And** the output format is consistent across retrieval modes

**Given** a ranked result set
**When** I inspect the retrieval package
**Then** I can see enough explanation or scoring context to understand why a result appeared near the top
**And** the package is compact enough to support agent consumption without opening the full repository manually

### Story 2.4: Build Semantic Retrieval Index Artifacts

As an internal engineer,
I want codeman to generate embedding-ready retrieval artifacts and a vector index,
So that I can run semantic queries over the same repository corpus.

**Requirements:** FR8

**Acceptance Criteria:**

**Given** a repository with structured chunks
**When** semantic indexing is run
**Then** codeman creates embedding documents from chunk data, records provider and model metadata, and builds a vector index for querying
**And** stores enough run metadata to attribute the index to a specific configuration

**Given** no external embedding provider is configured
**When** semantic indexing requires provider-backed embeddings
**Then** codeman fails with a clear, user-safe diagnostic or uses an explicitly configured local path
**And** does not silently send repository data to an external service

### Story 2.5: Run Semantic Retrieval Queries

As an internal engineer,
I want to run semantic queries against the indexed repository,
So that I can retrieve relevant code context even when my query does not exactly match symbols or file text.

**Requirements:** FR8, FR10

**Acceptance Criteria:**

**Given** a repository with completed semantic indexing artifacts
**When** I run a semantic query through the CLI
**Then** codeman returns ranked semantic matches from the vector index
**And** each result remains traceable to the original chunk and source file

**Given** a semantic query run completes
**When** I inspect the recorded run metadata
**Then** I can identify the embedding provider, model version, and query latency associated with that result set
**And** the output remains consistent with the shared retrieval result contract

### Story 2.6: Run Hybrid Retrieval with Fused Ranking

As an internal engineer,
I want to run hybrid retrieval that combines lexical and semantic signals,
So that I can get stronger results than either method alone for mixed repository questions.

**Requirements:** FR9, FR10

**Acceptance Criteria:**

**Given** both lexical and semantic retrieval capabilities are available
**When** I run a hybrid query
**Then** codeman combines results from both retrieval strategies into one ranked output
**And** the fusion process produces a stable final ordering for the same query and configuration context

**Given** one retrieval path is unavailable or degraded
**When** a hybrid query is attempted
**Then** codeman returns a clear failure or degradation message according to the configured behavior
**And** does not pretend the result came from full hybrid fusion if it did not

### Story 2.7: Compare Retrieval Modes for the Same Question

As an internal engineer,
I want to compare lexical, semantic, and hybrid results for the same repository question,
So that I can judge which retrieval mode is most useful for a given task.

**Requirements:** FR12

**Acceptance Criteria:**

**Given** the same repository question can be executed across multiple retrieval modes
**When** I request a comparison workflow
**Then** codeman returns mode-specific result sets in a comparable structure
**And** makes it clear which results came from lexical, semantic, and hybrid retrieval respectively

**Given** a retrieval mode comparison is complete
**When** I review the output
**Then** I can inspect differences in ranking and relevance between modes without manually reconstructing the runs
**And** the comparison output remains attributable to the same repository state and configuration context

## Epic 3: Configure and Reuse Retrieval Strategies

Maintainers can define retrieval and embedding configurations, reuse them across experiments, and know exactly which configuration produced a given indexing or retrieval run.

### Story 3.1: Define the Layered Configuration Model

As a maintainer,
I want codeman to resolve configuration from defaults, local config, CLI overrides, and environment secrets,
So that retrieval experiments can be run consistently without hard-coded settings.

**Requirements:** FR13

**Acceptance Criteria:**

**Given** project defaults, optional local config, CLI flags, and environment variables
**When** codeman resolves runtime configuration
**Then** it applies a deterministic precedence order across those layers
**And** produces a validated runtime configuration object

**Given** an invalid or conflicting configuration
**When** configuration resolution runs
**Then** codeman fails with a clear validation error and stable non-zero exit behavior
**And** does not start the indexing or query workflow with partial settings

### Story 3.2: Configure Embedding Providers Independently

As a maintainer,
I want embedding provider settings to be managed separately from other indexing settings,
So that I can change provider behavior without redefining the whole system.

**Requirements:** FR14

**Acceptance Criteria:**

**Given** a retrieval configuration that includes embedding settings
**When** I change provider-specific options
**Then** codeman validates them through a dedicated embedding configuration model
**And** keeps unrelated retrieval settings unchanged

**Given** provider credentials are required
**When** codeman loads embedding configuration
**Then** secrets are resolved from environment or protected local config only
**And** secret values are not written to source control, logs, or benchmark reports

### Story 3.3: Create Reusable Retrieval Strategy Profiles

As a maintainer,
I want to define named retrieval strategy profiles,
So that I can rerun the same chunking, embedding, and fusion setup across multiple experiments.

**Requirements:** FR15

**Acceptance Criteria:**

**Given** a valid set of retrieval-related settings
**When** I save it as a named profile
**Then** codeman stores the profile in a reusable form with stable identity and validated fields
**And** the profile can be selected in later indexing or query runs

**Given** multiple saved strategy profiles
**When** I inspect or select one
**Then** I can distinguish them by meaningful identifiers and configuration content
**And** codeman prevents ambiguous or silently overwritten profile selection

### Story 3.4: Record Configuration Provenance for Every Run

As a maintainer,
I want each indexing and retrieval run to record the exact configuration used,
So that I can attribute outputs and benchmark results to a precise experiment context.

**Requirements:** FR16

**Acceptance Criteria:**

**Given** an indexing, query, or benchmark run completes
**When** run metadata is stored
**Then** codeman records the resolved configuration identity, repository state, timestamp, and relevant provider/model metadata
**And** the stored metadata is sufficient to distinguish runs that used different settings

**Given** I review a past run
**When** I inspect its manifest or metadata record
**Then** I can tell which configuration produced it without reconstructing settings from logs
**And** the provenance record is stable enough for before/after experiment comparison

### Story 3.5: Reuse Prior Configurations in Later Experiments

As a maintainer,
I want to rerun workflows using previously defined configurations,
So that experiments are repeatable and easier to compare over time.

**Requirements:** FR17

**Acceptance Criteria:**

**Given** a previously saved configuration profile
**When** I launch a new indexing, query, or evaluation workflow with that profile
**Then** codeman uses the saved configuration as the basis for the run
**And** records that the workflow reused an existing configuration identity

**Given** I override part of a reused configuration at runtime
**When** the run starts
**Then** codeman records both the base profile identity and the effective resolved configuration
**And** makes it clear that the run is a modified reuse rather than an untouched replay

### Story 3.6: Key Caches to Configuration and Content Identity

As a maintainer,
I want cache reuse to depend on repository content and configuration identity,
So that codeman never reuses stale parser, chunk, or embedding artifacts incorrectly.

**Requirements:** FR15, FR16, FR17

**Acceptance Criteria:**

**Given** parser, chunk, or embedding artifacts already exist
**When** codeman checks whether they can be reused
**Then** cache decisions are based on content hashes and relevant configuration identity
**And** embedding cache keys include provider identity, model version, and chunk serialization version

**Given** a cache entry no longer matches the active repository or configuration context
**When** codeman evaluates reuse
**Then** it rebuilds the affected artifacts instead of reusing stale outputs
**And** the run metadata indicates whether artifacts were reused or regenerated

## Epic 4: Benchmark Retrieval Quality and Compare Strategies

Internal engineers can execute golden-query benchmarks, inspect reports, compare retrieval strategies, and identify regressions with reproducible evidence.

### Story 4.1: Define the Golden-Query Benchmark Dataset

As an internal engineer,
I want codeman to use a structured golden-query benchmark dataset,
So that retrieval quality can be evaluated against repeatable expected scenarios.

**Requirements:** FR19

**Acceptance Criteria:**

**Given** a benchmark dataset definition
**When** codeman loads it for evaluation
**Then** each test case includes a stable query identity, query text, and expected relevance targets or judgments
**And** the dataset format is validated before benchmark execution begins

**Given** an invalid or incomplete benchmark dataset
**When** I start a benchmark run
**Then** codeman fails with a clear validation error
**And** does not produce misleading partial benchmark results

### Story 4.2: Execute a Benchmark Run Against an Indexed Repository

As an internal engineer,
I want to execute a benchmark run from the CLI,
So that I can evaluate retrieval behavior for a specific repository state and configuration.

**Requirements:** FR18, FR23

**Acceptance Criteria:**

**Given** an indexed repository and a valid benchmark dataset
**When** I run the benchmark command
**Then** codeman executes the benchmark cases against the selected retrieval mode or strategy
**And** records a benchmark run with repository, configuration, and timestamp metadata

**Given** a benchmark run is in progress
**When** progress is reported
**Then** codeman uses consistent run phases and preserves clean JSON `stdout` in machine mode
**And** records a clear success or failure outcome at completion

### Story 4.3: Calculate and Store Retrieval Quality Metrics

As an internal engineer,
I want codeman to calculate standard retrieval metrics for benchmark runs,
So that strategy quality can be compared using evidence instead of intuition.

**Requirements:** FR20, FR23

**Acceptance Criteria:**

**Given** a completed benchmark run
**When** codeman calculates evaluation results
**Then** it produces at least Recall@K, MRR, and NDCG@K for the run
**And** stores the metric outputs in a structured, attributable format

**Given** the same benchmark run
**When** performance data is recorded
**Then** codeman also captures indexing time where applicable and query latency metrics for comparison
**And** the metric record is tied to the same benchmark and configuration identity

### Story 4.4: Generate Benchmark Reports for Review

As an internal engineer,
I want benchmark results to be presented in a reviewable report format,
So that I can inspect strategy quality without manually assembling the evidence.

**Requirements:** FR20

**Acceptance Criteria:**

**Given** a completed benchmark run with computed metrics
**When** I request a report
**Then** codeman generates a local benchmark report artifact and a CLI-readable summary
**And** the report includes benchmark identity, retrieval mode, key metrics, and configuration provenance

**Given** benchmark results are viewed in machine-readable mode
**When** the report summary is returned
**Then** it follows the standard JSON envelope contract
**And** does not mix human commentary into `stdout`

### Story 4.5: Compare Benchmark Runs Across Retrieval Strategies

As an internal engineer,
I want to compare benchmark runs side by side,
So that I can understand how one retrieval strategy performs relative to another.

**Requirements:** FR21

**Acceptance Criteria:**

**Given** two or more completed benchmark runs
**When** I run a comparison workflow
**Then** codeman produces a structured comparison of key metrics and configuration identities
**And** makes it clear which run performed better for each reported measure

**Given** compared runs were produced under different repository states or benchmark datasets
**When** I inspect the comparison output
**Then** codeman highlights those comparability differences explicitly
**And** does not imply a clean apples-to-apples comparison when the context differs

### Story 4.6: Detect and Surface Retrieval Regressions

As an internal engineer,
I want codeman to surface regressions between benchmark runs,
So that quality drops are visible immediately during experimentation.

**Requirements:** FR22

**Acceptance Criteria:**

**Given** a current benchmark run and a prior comparable baseline
**When** the current run underperforms on tracked metrics
**Then** codeman flags the regression in comparison output or reporting artifacts
**And** identifies which metrics regressed and by how much

**Given** no valid comparable baseline exists
**When** regression detection is requested
**Then** codeman reports that regression status is unavailable or inconclusive
**And** explains which contextual mismatch prevents reliable comparison

## Epic 5: Operate, Diagnose, and Prepare for Extension

Internal engineers can run the platform reliably through the CLI, diagnose failures down to the likely subsystem, and keep the retrieval core ready for future MCP and interface reuse without splitting behavior.

### Story 5.1: Standardize the Core CLI Workflow Surface

As an internal engineer,
I want a stable CLI command surface for core workflows,
So that I can run indexing, retrieval, evaluation, and comparison consistently in repeated experiments.

**Requirements:** FR24, FR25

**Acceptance Criteria:**

**Given** the codeman CLI is installed
**When** I inspect or use the command surface
**Then** the core groups `repo`, `index`, `query`, `eval`, `compare`, and `config` are available with stable command naming
**And** help output describes the supported workflows consistently

**Given** I run the same supported command repeatedly with the same inputs
**When** the environment and repository state have not changed materially
**Then** the CLI behaves deterministically enough for repeatable experimentation
**And** does not require manual reconfiguration outside the documented configuration layers

### Story 5.2: Map Failures to Stable Error Contracts and Exit Codes

As a maintainer,
I want codeman failures to use stable error types and exit behavior,
So that automation and operators can react reliably when workflows fail.

**Requirements:** FR26, FR27

**Acceptance Criteria:**

**Given** a failure occurs in indexing, retrieval, or evaluation
**When** the CLI handles the error
**Then** codeman maps the failure to a stable project-level error code and non-zero exit outcome
**And** returns a user-safe message in human mode and structured error payload in JSON mode

**Given** an adapter or provider raises a low-level exception
**When** that error crosses the application boundary
**Then** codeman wraps it in a project-specific error type before presenting it to the CLI
**And** does not leak raw internal exceptions as the public contract

### Story 5.3: Produce Structured Run Logs and Manifests

As a maintainer,
I want codeman to emit structured logs and run manifests,
So that I can trace what happened during indexing, retrieval, and benchmark workflows.

**Requirements:** FR25, FR26, FR27

**Acceptance Criteria:**

**Given** a core workflow runs
**When** codeman records execution details
**Then** it writes structured JSONL logs and run manifest artifacts to local runtime storage
**And** the records include run identity, workflow type, outcome, and phase-level context

**Given** I inspect a past run artifact
**When** I review its manifest or logs
**Then** I can correlate it to the repository state and configuration that produced it
**And** use it for troubleshooting or experiment provenance

### Story 5.4: Surface Subsystem-Oriented Diagnostics Safely

As a maintainer,
I want failure diagnostics to point to the most likely subsystem,
So that I can investigate problems quickly without exposing sensitive repository content by default.

**Requirements:** FR26, FR27, FR28

**Acceptance Criteria:**

**Given** an indexing, retrieval, or evaluation workflow fails or degrades
**When** codeman reports diagnostics
**Then** it identifies the likely affected subsystem such as snapshotting, parsing, chunking, embeddings, indexing, fusion, or evaluation
**And** provides actionable next-step context for investigation

**Given** diagnostics are shown in the default mode
**When** repository-sensitive context would otherwise be exposed
**Then** codeman redacts or suppresses that content by default
**And** only reveals more detailed excerpts in an explicit debug or verbose mode

### Story 5.5: Support Repeated Experimental Workflows Without Drift

As an internal engineer,
I want repeated CLI workflows to remain operationally consistent over time,
So that experiment velocity does not degrade as I rerun indexing, querying, and evaluation.

**Requirements:** FR25

**Acceptance Criteria:**

**Given** multiple indexing, query, and evaluation runs are executed over time
**When** I use the same documented workflow shape
**Then** codeman preserves consistent operational behavior, output contracts, and runtime path conventions
**And** avoids ad hoc per-command behavior that forces manual workaround steps

**Given** runtime artifacts accumulate under `.codeman/`
**When** I continue using the platform for repeated experiments
**Then** codeman maintains predictable artifact organization and run traceability
**And** does not require undocumented cleanup knowledge to keep core workflows usable

### Story 5.6: Prepare a Shared Retrieval Core for Future MCP Reuse

As a Phase 2 platform engineer,
I want future MCP-facing workflows to reuse the same retrieval core and contracts,
So that new interfaces can be added without redefining indexing and retrieval behavior.

**Requirements:** FR29, FR30, FR31

**Acceptance Criteria:**

**Given** the MVP is implemented as a CLI-first platform
**When** interface boundaries are reviewed
**Then** retrieval, evaluation, and result-formatting logic live in shared application and contract layers rather than inside CLI-only modules
**And** a reserved MCP boundary can call the same services without duplicating behavior

**Given** future MCP integration work begins
**When** engineers inspect the codebase and story outputs
**Then** they can identify the intended extension point for MCP reuse clearly
**And** the MVP architecture does not require a parallel retrieval path to support Phase 2
