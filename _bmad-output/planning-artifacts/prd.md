---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
inputDocuments:
  - inline://user-provided-project-idea-2026-03-13
  - inline://user-provided-tech-stack-python-uv-2026-03-13
workflowType: 'prd'
documentCounts:
  productBriefs: 0
  research: 0
  brainstorming: 0
  projectDocs: 0
  projectContext: 0
  inlineInputs: 2
classification:
  projectType: developer_tool
  domain: scientific
  complexity: medium
  projectContext: greenfield
  interfaces:
    - cli
    - mcp
---

# Product Requirements Document - codeman

**Author:** Vdubyna
**Date:** 2026-03-13

## Executive Summary

This project delivers an agent-oriented hybrid code retrieval system for mixed-stack web repositories built with PHP, JavaScript, HTML, and Twig. The product is designed for developers and agent workflows that need high-quality repository context for search, reasoning, navigation, and code modification tasks.

The MVP solves a specific problem: generic code search tools do not reliably serve agent workflows in heterogeneous repositories. Pure lexical search is strong for symbol-heavy lookup but weak on semantic intent. Pure vector search improves semantic recall but often loses structural precision, symbol fidelity, and explanation quality. File-level retrieval is too coarse, while naive chunking breaks the structural boundaries agents need to reason correctly.

The proposed product provides a modular retrieval pipeline that builds a normalized repository snapshot, parses source files through language-specific adapters, produces structurally meaningful chunks, indexes them through both lexical and vector subsystems, fuses ranked results in a hybrid retriever, and returns agent-friendly retrieval packages through a CLI-first interface. The MVP also includes an evaluation harness with golden queries and measurable retrieval metrics so the system can be improved through controlled experimentation instead of intuition. MCP is a planned Phase 2 interface layered onto the same retrieval core.

The product is intentionally architecture-first and optimization-ready. Each major subsystem has a narrow responsibility and can later be independently tuned, replaced, benchmarked, or mutated by automated experimentation loops. This makes the MVP useful as a working developer tool today and a foundation for future autosearch and automated retrieval optimization work.

### What Makes This Special

This is not a generic developer search utility. It is a retrieval platform designed around the actual needs of coding agents. Its core differentiator is the combination of AST-aware chunking, hybrid retrieval, agent-oriented output packaging, and evaluation-first development discipline.

The key insight is that agents need more than "relevant files." They need structurally coherent retrieval units, metadata-rich embedding documents, strong support for exact symbol search, semantic recall for natural-language intent, and ranked outputs that are easy to consume in reasoning loops. The product therefore treats chunking, embeddings, lexical retrieval, vector retrieval, and result fusion as explicit first-class modules rather than hiding them inside a monolithic indexing pipeline.

Users should prefer this product over grep-only, embeddings-only, or generic code search alternatives because it is optimized for mixed-language repositories and agent execution patterns. It aims to improve retrieval quality in measurable terms, not only subjective developer experience, and it is built to support future automated optimization rather than requiring manual redesign when experimentation becomes important.

## Project Classification

- **Project Type:** Developer Tool
- **Interfaces:** CLI (MVP), MCP (Phase 2)
- **Domain:** Scientific / evaluation-driven AI tooling
- **Complexity:** Medium
- **Project Context:** Greenfield
- **Implementation Stack:** Python with uv

## Success Criteria

### User Success

The primary MVP users are internal developers who need reliable repository context from mixed-stack codebases. Phase 2 extends the product to agent workflows through MCP. The product is successful for users when they can issue lexical, semantic, and hybrid queries against a local repository and consistently receive ranked, structurally meaningful chunks that are useful for navigation, reasoning, and implementation tasks.

User success means the system is not merely searchable, but operationally helpful. A successful retrieval session returns chunks that preserve code structure, include the metadata needed to understand relevance, and reduce the amount of manual repository exploration required before an agent or developer can act. The product should feel reliable on both symbol-heavy queries and natural-language intent queries.

The core user "aha" moment is when a developer or agent asks a code question about a heterogeneous PHP / JS / HTML / Twig repository and receives a compact, explainable retrieval package that is materially better than grep-only or embeddings-only results.

### Business Success

This product is an internal R&D platform, not a commercial product in the MVP phase. Business success is defined by whether it becomes the team's default environment for designing, comparing, and validating agent-oriented retrieval strategies in mixed-stack repositories.

At 3 months, success means:

- the team can run repeatable end-to-end retrieval experiments on a shared benchmark corpus;
- at least several chunking, embedding, or fusion variants have been compared using the same evaluation harness;
- benchmark results have informed at least one concrete engineering decision.

At 12 months, success means:

- the platform serves as the internal baseline for retrieval experimentation in this problem space;
- new retrieval strategies can be introduced without greenfield rewrites;
- retrieval quality discussions are driven primarily by benchmark evidence rather than anecdotal impressions.

### Technical Success

Technical success requires not only end-to-end functionality but also controlled extensibility. The MVP must index a local mixed-language repository, generate structurally meaningful retrieval chunks, support lexical retrieval, semantic retrieval, and hybrid fusion, and return agent-friendly outputs through the CLI.

The architecture is successful only if bounded subsystems remain independently replaceable. Changes to chunking, embedding providers, vector indexing, lexical ranking, or fusion logic should be implementable as localized module or configuration changes rather than cross-system rewrites.

Phase 2 interface growth, including MCP, must reuse the same core indexing and retrieval services so that interface expansion does not fragment system behavior. Evaluation must be built into the product lifecycle: benchmark execution, metric reporting, and regression comparison are first-class capabilities, not optional tooling.

### Measurable Outcomes

The MVP should achieve the following measurable outcomes:

- Index a representative local mixed-stack repository containing PHP, JavaScript, HTML, and Twig.
- Support lexical retrieval for exact-match and symbol-heavy queries.
- Support semantic retrieval through an explicit embedding pipeline with model metadata.
- Support hybrid retrieval that fuses lexical and vector results into a single ranked output.
- Return ranked chunks with metadata and retrieval explanations suitable for agent consumption.
- Execute a benchmark suite with golden queries and report Recall@K, MRR, NDCG@K, indexing time, and query latency in a reproducible format.
- Support before/after benchmark comparison across retrieval strategies.
- Allow a new chunking strategy, embedding provider, or retrieval fusion variant to be introduced by changing a bounded subsystem rather than redesigning the entire pipeline.

For the internal R&D context, success should also be measured by experiment velocity:

- the team can run and compare multiple retrieval configurations on the same corpus;
- regressions can be detected from benchmark reports rather than manual inspection;
- architecture changes preserve the ability to iterate quickly on retrieval quality.

## Product Scope

### MVP - Minimum Viable Product

The MVP includes:

- Repository snapshot creation for local repositories.
- Parser adapters for PHP, JavaScript, HTML, and Twig.
- AST-aware or structure-aware chunking for each supported language.
- A normalized chunk schema with metadata required for retrieval and embeddings.
- A chunk store for indexed retrieval units.
- A pluggable embedding pipeline with model version metadata.
- A lexical index for exact and identifier-heavy search.
- A vector index for semantic retrieval.
- A hybrid retriever that combines lexical and vector results.
- Agent-oriented output formatting for CLI consumption.
- An evaluation harness with sample golden queries and measurable retrieval metrics.
- CLI entrypoints for indexing, querying, and evaluation.

The MVP is successful when it delivers one complete end-to-end path from repository ingestion to benchmarked hybrid retrieval.

### Growth Features (Post-MVP)

Post-MVP growth should focus on improving retrieval quality, experiment velocity, and agent integration depth:

- Better language-specific chunkers and richer parser adapters.
- Additional embedding providers and model comparison workflows.
- More advanced hybrid fusion and reranking strategies.
- Better retrieval explanations and result packaging for agent reasoning loops.
- Expanded benchmark datasets and scenario-specific evaluation suites.
- Broader repository support beyond the initial mixed-stack target.
- Improved MCP capabilities for richer agent-tool interactions.

### Vision (Future)

The long-term vision is to evolve the product from a useful internal retrieval tool into a modular experimentation platform for automated retrieval optimization.

In that future state, the system supports autosearch and automated mutation loops that can propose, evaluate, and compare retrieval strategy changes across chunking, embeddings, ranking, and packaging layers. The platform becomes the internal foundation for evidence-driven improvement of agent context quality, with modular subsystems that can be independently tuned, benchmarked, and promoted into stronger default retrieval strategies.

## User Journeys

### Journey 1: Primary User - Success Path

Olena is an internal retrieval engineer working on agent tooling for mixed-stack repositories. She has a local repository with PHP, JavaScript, HTML, and Twig, and she needs a retrieval system that produces context an agent can actually use. Existing tools force her to combine grep, ad hoc scripts, and manual repository reading, which makes experiments slow and hard to compare.

She installs the tool through the Python + uv workflow, runs the indexing command from the CLI, and watches the system build a normalized repository snapshot, parse the supported languages, and generate retrieval chunks. Once indexing completes, she runs lexical, semantic, and hybrid queries against the same repository and inspects the returned ranked chunks with metadata and explanations.

The turning point comes when a hybrid query returns a compact retrieval package that clearly surfaces the most relevant symbols, templates, and related code fragments without forcing her to open many files manually. She can immediately see why the result ranked highly and how it differs from lexical-only and vector-only output.

By the end of the session, Olena has both a useful answer to her query and a reproducible baseline she can use in future experiments. Her new reality is that retrieval work becomes a controlled engineering activity instead of an improvised search exercise.

### Journey 2: Primary User - Edge Case and Recovery Path

Taras is running a new chunking experiment on the same mixed-stack repository. He expects improved retrieval quality, but after re-indexing and running the benchmark suite, the results regress on several golden queries. Some symbol-heavy queries perform worse, and latency rises unexpectedly.

Instead of guessing what went wrong, Taras uses the product's benchmark outputs, retrieval explanations, and subsystem boundaries to investigate. He compares before-and-after runs, inspects which chunks were produced by the new strategy, and checks whether the degradation came from chunking, embeddings, ranking, or result fusion.

The high-stress moment is not the regression itself, but whether the platform helps him localize the problem quickly. The product succeeds when Taras can trace the regression to a bounded subsystem, revert or replace the experimental strategy, and rerun the same benchmark without rebuilding the entire pipeline or abandoning comparability.

The journey resolves when Taras restores a stable baseline and documents a clear technical conclusion: the experiment failed for specific measurable reasons. The product has done its job because it turned a failed experiment into usable learning instead of wasted effort.

### Journey 3: Phase 2 Integration User - MCP Agent Workflow

This is a post-MVP journey. Mykola works on internal agent infrastructure. His goal is not to use the search system manually, but to make it available to coding agents through MCP so that agents can request context during reasoning and implementation workflows.

He configures the MCP interface, connects it to the same core indexing and retrieval services used by the CLI, and exposes retrieval operations to an agent runtime. He then tests real agent queries that ask for symbol definitions, related templates, feature entry points, and semantically relevant code regions across the mixed-stack repository.

The critical moment comes when the agent asks a non-trivial question and the MCP-backed retrieval service returns ranked, metadata-rich chunks that are compact enough for reasoning and explicit enough for trust. Mykola needs confidence that MCP is not a thin wrapper around a separate code path, but a stable interface on top of the same evaluated retrieval engine.

The journey is successful when MCP integration becomes a reliable building block for agent workflows rather than a custom one-off adapter. Mykola can now plug retrieval into agent systems with confidence that benchmarked behavior and production behavior remain aligned.

### Journey 4: Admin / Maintainer - Configuration and Experiment Setup

Iryna is responsible for maintaining the internal retrieval platform as a shared R&D asset. She does not spend most of her time searching repositories directly. Instead, she configures embedding providers, tracks model versions, manages index settings, and prepares benchmark corpora so the team can run comparable experiments.

When the team wants to test a new embedding model or retrieval fusion strategy, Iryna updates configuration, verifies that the model metadata is stored correctly, and ensures the benchmark harness produces reproducible reports. She must be able to introduce changes without breaking the indexing pipeline or creating ambiguity about which configuration produced which results.

Her highest-value moment is when a new experimental configuration can be introduced with a localized change and immediately evaluated against the shared benchmark suite. She needs operational clarity: which provider ran, which model version produced vectors, which benchmark run belongs to which experiment, and whether results are comparable.

The journey resolves when Iryna can support multiple experiments without turning the platform into configuration chaos. The product succeeds because maintainability and experiment traceability are built into the system design.

### Journey 5: Support / Troubleshooting User - Failure Investigation

Dmytro is the engineer called in when something goes wrong in the platform. An indexing run fails on a repository with unusual template structure, query latency spikes after a configuration change, or benchmark results suddenly become inconsistent across runs.

He approaches the system as an investigator. He needs clear failure surfaces, inspectable subsystem boundaries, and enough logging or diagnostic output to determine whether the problem lives in repository snapshotting, parsing, chunk generation, embeddings, indexing, retrieval fusion, or evaluation.

The most important moment is the handoff from symptom to diagnosis. If Dmytro only sees that "search got worse," the system fails him. If he can isolate the issue, reproduce it, and identify the affected subsystem without tearing apart the whole platform, the system proves operationally viable.

The journey ends when Dmytro restores reliability and leaves behind a benchmarked, documented explanation of the incident. The product succeeds because troubleshooting is structured, bounded, and evidence-driven rather than dependent on tribal knowledge.

### Journey Requirements Summary

These journeys reveal the need for the following capability areas:

- Local repository ingestion and normalized repository snapshot creation.
- Reliable parser adapters for PHP, JavaScript, HTML, and Twig.
- Structurally meaningful chunking with language-aware boundaries.
- Lexical, semantic, and hybrid retrieval paths exposed through shared core services.
- CLI workflows for indexing, querying, benchmarking, and experiment comparison.
- Phase 2 MCP workflows that reuse the same retrieval engine and output semantics as CLI.
- Metadata-rich retrieval outputs with ranking explanations for agent consumption.
- Benchmark harness support for reproducible runs, before/after comparisons, and regression detection.
- Configuration management for embedding providers, model versions, and retrieval strategies.
- Diagnostic and troubleshooting support that makes failures attributable to bounded subsystems.

## Domain-Specific Requirements

### Compliance & Regulatory

No formal industry-specific compliance regime is required for the MVP. However, the product must support internal engineering governance for reproducibility, traceability, and safe handling of proprietary source code.

The system should preserve experiment traceability by recording configuration inputs relevant to retrieval quality, including chunking strategy, embedding provider, embedding model version, index configuration, and benchmark context. If external embedding providers are used, the platform must make it explicit when repository code or metadata leaves the local environment.

### Technical Constraints

The product operates in an evaluation-driven AI tooling domain, so reproducibility is a first-order requirement rather than a convenience feature. Benchmark runs must be repeatable, comparable, and attributable to specific retrieval configurations.

The system must support mixed-language parsing across PHP, JavaScript, HTML, and Twig without collapsing all retrieval into naive file-level units. It must preserve structural fidelity where possible and degrade gracefully where parser coverage is weaker.

Model and provider variability must be treated as a controlled constraint. Embedding outputs, query behavior, and retrieval quality may change across providers and model versions, so the platform must store model metadata and make experiment boundaries explicit.

Latency and indexing cost matter, but correctness and evaluability matter more for the MVP. The system should therefore optimize first for trustworthy retrieval behavior, bounded modularity, and measurable quality, while still exposing indexing time and query latency as tracked metrics.

### Integration Requirements

The product must integrate cleanly with local developer workflows through the CLI in the MVP and add MCP in Phase 2 for agent workflows. Both interfaces must rely on the same core retrieval services to preserve consistency between manual experimentation and agent execution.

The system must support local repository indexing as a primary use case. It should also support benchmark dataset execution and comparison workflows as first-class operations, not one-off scripts.

If external embedding providers are configured, the integration model must make provider boundaries visible so users understand operational, privacy, and cost implications.

### Risk Mitigations

The primary domain risk is false confidence: a retrieval strategy may appear useful anecdotally while underperforming on benchmarked tasks. This risk is mitigated through golden-query evaluation, reproducible reporting, and before/after comparisons across retrieval strategies.

A second risk is architectural drift, where experimentation becomes harder over time because subsystems are no longer independently swappable. This risk is mitigated through strict module boundaries and shared core services for indexing and retrieval.

A third risk is hidden provider or model variance. Changes in embedding provider, model version, or indexing configuration can distort conclusions if not tracked explicitly. This risk is mitigated by configuration traceability and experiment metadata capture.

A fourth risk is unsafe handling of proprietary repository contents when using external services. This risk is mitigated by making provider usage explicit and keeping local-first workflows viable for the MVP.

## Innovation & Novel Patterns

### Detected Innovation Areas

The product introduces a new operating model for code retrieval in mixed-stack repositories. Instead of treating code search as a standalone developer utility, it frames retrieval as an agent-facing infrastructure layer that must serve reasoning loops, implementation workflows, and controlled experimentation.

The first innovation area is the combination of AST-aware chunking, hybrid retrieval, and agent-oriented retrieval packaging within one modular system. Each of these ideas exists independently in the broader tooling ecosystem, but this product combines them into a retrieval architecture explicitly designed for coding agents operating on heterogeneous repositories.

The second innovation area is evaluation-first retrieval engineering. In this product, chunking, embeddings, lexical indexing, vector retrieval, and fusion are not hidden implementation details. They are explicit experimental surfaces that can be measured, compared, and improved through benchmark-driven iteration.

The third innovation area is interface convergence over time. CLI is the MVP delivery surface, and MCP is planned for Phase 2, but both are designed as access layers for the same core indexing and retrieval engine. This creates a stronger foundation for both human experimentation and later agent execution.

### Market Context & Competitive Landscape

Most existing approaches fall into one of several patterns: lexical-first tools optimized for exact symbol search, semantic search systems optimized for embedding recall, or generic code intelligence tools that are not designed around agent reasoning workflows.

Lexical tools remain useful for identifiers and exact matches, but they do not reliably surface semantically relevant context across mixed-language repositories. Embedding-only approaches improve semantic retrieval but often lose symbol fidelity, structural coherence, and explainability. Generic code search tools also tend to treat retrieval as a user-facing lookup task rather than an agent-facing context assembly problem.

This product differentiates itself by targeting the gap between these approaches: it is optimized for structurally coherent, explainable, benchmarked retrieval that can be used directly through the CLI in the MVP and later consumed by agents through MCP.

### Validation Approach

The innovative aspects of the product should be validated through controlled comparison rather than subjective impressions.

Validation should focus on the following questions:

- Does AST-aware and structure-aware chunking outperform naive chunking on the target benchmark set?
- Does hybrid retrieval outperform lexical-only and vector-only baselines on mixed-stack repositories?
- Do agent-oriented retrieval packages improve downstream usefulness compared with raw ranked matches?
- Does the modular architecture reduce the cost of introducing and evaluating new retrieval strategies?

Validation should rely on reproducible benchmark runs with golden queries, standard retrieval metrics such as Recall@K, MRR, and NDCG@K, and explicit before/after comparisons across retrieval strategies. Innovation is only real if it produces measurable improvement or materially improves experimental velocity.

### Risk Mitigation

The main innovation risk is false novelty: the product may be framed as a new paradigm while delivering only marginal gains over simpler retrieval pipelines. This risk should be mitigated by benchmarking against strong lexical-only, vector-only, and naive chunking baselines.

A second risk is over-architecting for future optimization before the MVP proves useful. This risk should be mitigated by enforcing MVP-first scope and requiring one complete end-to-end working retrieval path before expanding the experimentation surface.

A third risk is fragmented product behavior across interfaces. If CLI and MCP evolve differently, the innovation claim weakens because the system stops being a unified retrieval core. This risk should be mitigated by shared services and common evaluation paths.

A fourth risk is complexity without adoption inside the team. If the product becomes too hard to configure, benchmark, or extend, its value as an internal R&D platform declines. This risk should be mitigated through bounded module design, explicit configuration metadata, and reproducible evaluation workflows.

## Developer Tool Specific Requirements

### Project-Type Overview

This product is a Python-based internal developer tool designed for agent-oriented code retrieval experiments on mixed-stack repositories. In the MVP phase, it is intentionally CLI-first and does not require a separate IDE integration layer or a public Python library API.

The tool is optimized for internal R&D usage rather than public package adoption. Its purpose is to provide a stable, scriptable, benchmarkable environment for indexing repositories, running retrieval workflows, and comparing retrieval strategies over time.

### Technical Architecture Considerations

The architecture should preserve a strict separation between the CLI entrypoints and the retrieval core. The CLI is the operational surface, but indexing, chunking, embeddings, lexical retrieval, vector retrieval, hybrid fusion, and evaluation must live in reusable internal modules rather than being embedded directly in command handlers.

Because this is a developer tool, operational clarity matters as much as functionality. Commands should be deterministic, scriptable, and suitable for repeated experimental workflows. The system should prioritize inspectability, reproducibility, and bounded extensibility over UX polish or broad interface coverage in the MVP.

MCP and IDE integration are not part of the MVP project-type surface. If introduced later, they should be layered on top of the same internal retrieval services rather than creating parallel execution paths.

### Language Matrix

The implementation language for the product is Python.

The supported repository analysis targets for the MVP are:

- PHP
- JavaScript
- HTML
- Twig

The language matrix should make a clear distinction between:

- the language used to implement the tool;
- the languages that can be parsed and indexed;
- the retrieval artifacts exposed by the system regardless of source language.

Support quality may vary across indexed languages based on parser maturity, but the product must provide a coherent retrieval workflow across the full mixed-stack target set.

### Installation Methods

The MVP should support uv as the single official installation, dependency management, and execution workflow.

The project should be operable through a uv-based setup for:

- environment initialization;
- dependency installation;
- CLI execution;
- development workflows;
- test and benchmark execution.

Alternative package manager or installation flows are out of scope for the MVP.

### API Surface

The MVP exposes a CLI-only interface.

The CLI surface should cover the core operational workflows:

- repository indexing;
- lexical search;
- semantic search;
- hybrid retrieval;
- benchmark execution;
- experiment comparison or evaluation reporting.

Phase 2 introduces MCP as an additional interface layer built on top of the same internal retrieval services.

The MVP does not require:

- a public Python SDK or library API;
- IDE integration;
- MCP in the initial delivery.

Internal module boundaries should still be designed so that future interfaces can be added without restructuring the retrieval core.

### Documentation Requirements

The MVP requires focused developer documentation sufficient for internal adoption and repeatable experimentation.

Required documentation should include:

- project overview and purpose;
- uv-based setup and execution instructions;
- CLI command reference for indexing, querying, and evaluation;
- configuration guidance for embedding providers and model metadata;
- benchmark workflow documentation;
- architecture notes describing module boundaries and future extension points.

Documentation should prioritize operational clarity over marketing or onboarding polish.

### Code Examples & Sample Assets

The MVP does not require a standalone sample repository, tutorial example pack, or separate MCP configuration examples.

Minimal operational examples may still appear in documentation to clarify command usage, but example assets should not become a parallel deliverable. Any benchmark fixture or golden-query corpus that exists should be the smallest internal dataset necessary to support evaluation requirements, not a polished public sample package.

### Migration Guide

A migration guide is not required for the MVP because this is a greenfield internal tool with no prior supported interface or legacy user base.

### Implementation Considerations

Implementation choices should reinforce the tool's role as an internal experimentation platform:

- commands should be easy to script and rerun;
- configurations should be explicit and traceable;
- benchmark outputs should be reproducible;
- subsystem boundaries should support future interface expansion without redesign;
- CLI behavior should remain consistent across indexing, retrieval, and evaluation workflows.

The product should optimize for reliability of experimentation, ease of comparison, and maintainability of the retrieval core rather than breadth of distribution or end-user ecosystem integration.

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Problem-solving platform MVP for internal R&D.

The MVP is not intended to maximize interface breadth or ecosystem reach. Its purpose is to establish a trustworthy end-to-end retrieval baseline for mixed-stack repositories and create a repeatable environment for evaluating retrieval strategies.

The MVP should prove three things:

- the system can index and search mixed-stack repositories in a structurally meaningful way;
- hybrid retrieval provides practical value over simpler baselines;
- the architecture supports controlled experimentation without requiring repeated redesign.

**Resource Requirements:** 1 primary engineer can build the MVP if the scope remains strict, with optional part-time support for benchmark design or retrieval evaluation. A more realistic delivery shape is 1 retrieval/platform engineer plus light product or research support for benchmark curation and result review.

### MVP Feature Set (Phase 1)

**Core User Journeys Supported:**

- Primary user success path: index a local repository, run retrieval workflows, inspect ranked results.
- Primary user edge-case path: compare strategies, detect regressions, and recover from failed experiments.
- Admin/maintainer path: configure providers, run evaluations, and manage reproducible experiments.
- Limited troubleshooting path: inspect failures and identify the subsystem responsible.

**Must-Have Capabilities:**

- Repository snapshot creation for local repositories.
- Parser adapters for PHP, JavaScript, HTML, and Twig.
- Structure-aware chunking with a normalized chunk schema.
- Chunk storage and retrieval metadata management.
- Embedding pipeline with provider abstraction and model version tracking.
- Lexical retrieval.
- Vector retrieval.
- Hybrid retrieval fusion.
- CLI commands for indexing, searching, and evaluation.
- Benchmark harness with golden queries and reproducible metric reporting.
- Internal architecture notes for future extension.

**Explicitly Out of MVP:**

- MCP interface.
- IDE integration.
- Public Python SDK.
- Multi-repo distributed indexing.
- Full relation graph or graph database.
- Automated mutation or autosearch engine.
- Advanced reranking and broad language expansion beyond the initial set.

### Post-MVP Features

**Phase 2 (Post-MVP):**

- MCP interface built on the same retrieval core.
- Improved retrieval packaging for agent workflows.
- Additional embedding providers and comparison workflows.
- Better hybrid fusion and reranking strategies.
- Expanded benchmark datasets and regression suites.
- More robust diagnostics and experiment management.

**Phase 3 (Expansion):**

- Automated retrieval optimization loops.
- Mutation-driven experimentation across chunking, embeddings, and ranking.
- Broader repository and language support.
- More advanced evaluation scenarios tied to downstream agent task performance.
- Platform-level orchestration for large-scale retrieval experimentation.

### Risk Mitigation Strategy

**Technical Risks:**  
The biggest technical risks are parser quality variance, low retrieval quality despite architectural effort, and overbuilding abstractions before the MVP proves useful. Mitigation: deliver one end-to-end CLI workflow first, benchmark against simple baselines, and keep module boundaries strict but minimal.

**Market Risks:**  
The main product risk is solving an interesting technical problem without producing a tool the internal team actually uses. Mitigation: optimize the MVP around real retrieval tasks, benchmark evidence, and repeatable experiments rather than architectural elegance alone.

**Resource Risks:**  
The main resource risk is trying to deliver too many interfaces and extension points too early. Mitigation: keep Phase 1 CLI-only, defer MCP to Phase 2, avoid sample asset overhead, and constrain the first release to the smallest useful experiment platform.

## Functional Requirements

### Repository Ingestion & Content Structuring

- FR1: Internal engineers can register a local repository for indexing and retrieval workflows.
- FR2: Internal engineers can create a normalized repository snapshot from a local repository.
- FR3: Internal engineers can extract retrievable content from supported repository file types.
- FR4: Internal engineers can generate structurally meaningful retrieval units from indexed repository content.
- FR5: Internal engineers can access metadata associated with retrievable units, including source context and identity information.
- FR6: Internal engineers can re-index a repository after source or configuration changes.

### Search & Retrieval Workflows

- FR7: Internal engineers can run lexical retrieval queries against indexed repository content.
- FR8: Internal engineers can run semantic retrieval queries against indexed repository content.
- FR9: Internal engineers can run hybrid retrieval queries that combine multiple retrieval strategies.
- FR10: Internal engineers can receive ranked retrieval results for a given query.
- FR11: Internal engineers can inspect retrieval outputs that are suitable for reasoning, navigation, and implementation workflows.
- FR12: Internal engineers can compare retrieval results across different query modes for the same repository question.

### Retrieval Configuration & Experiment Control

- FR13: Maintainers can configure retrieval-related components used by the system.
- FR14: Maintainers can configure embedding-related settings independently from other indexing settings.
- FR15: Maintainers can configure retrieval strategies and experiment variants without redefining the entire system.
- FR16: Maintainers can identify which configuration was used for a specific indexing or retrieval run.
- FR17: Maintainers can reuse previously defined retrieval configurations in later experiments.

### Evaluation & Benchmarking

- FR18: Internal engineers can execute benchmark runs against indexed repositories.
- FR19: Internal engineers can evaluate retrieval behavior using golden-query test cases.
- FR20: Internal engineers can review benchmark outputs for a retrieval configuration.
- FR21: Internal engineers can compare benchmark results across retrieval strategies.
- FR22: Internal engineers can identify retrieval regressions between experiment runs.
- FR23: Internal engineers can associate benchmark results with the retrieval configuration that produced them.

### CLI Operations & Troubleshooting

- FR24: Internal engineers can execute core indexing, retrieval, and evaluation workflows through the CLI.
- FR25: Internal engineers can use the CLI in repeated experimental workflows without requiring manual system reconfiguration each time.
- FR26: Maintainers can diagnose failed indexing runs.
- FR27: Maintainers can diagnose failed retrieval or evaluation runs.
- FR28: Maintainers can identify which subsystem is most likely responsible for a failed or degraded run.

### Future Interface Expansion

- FR29: Phase 2 users can access retrieval workflows through an MCP interface.
- FR30: Phase 2 users can receive retrieval outputs through MCP that are consistent with the core retrieval behavior established by the CLI.
- FR31: Future interfaces can reuse the same retrieval capabilities without redefining core indexing and retrieval behavior.

## Non-Functional Requirements

### Performance

- NFR1: On the reference benchmark repository used by the team, lexical retrieval queries executed through the CLI shall return ranked results within 2 seconds under the baseline development environment.
- NFR2: On the reference benchmark repository used by the team, semantic and hybrid retrieval queries executed through the CLI shall return ranked results within 5 seconds under the baseline development environment.
- NFR3: The system shall record indexing time and query latency for every benchmarked run so performance can be compared across configurations.
- NFR4: Performance reporting shall be consistent enough to support before/after comparison across retrieval strategies on the same corpus and environment.

### Security & Data Handling

- NFR5: Repository contents and derived retrieval artifacts shall remain local by default.
- NFR6: The system shall not send repository code, chunk content, embeddings, or query content to external providers unless an external provider is explicitly configured for that workflow.
- NFR7: When an external embedding provider is used, the system shall make that provider usage visible to the operator in configuration or runtime output.
- NFR8: Secrets required for provider access shall not be hard-coded in source control and shall be supplied through environment variables, secure configuration, or equivalent protected mechanisms.
- NFR9: Diagnostic output shall avoid exposing full repository contents by default, except where an explicit debug mode is enabled.

### Reliability & Reproducibility

- NFR10: Given the same repository revision, configuration, and benchmark dataset, repeated benchmark runs shall be reproducible and attributable to the same experiment context.
- NFR11: Every indexing, query, and benchmark run shall capture sufficient metadata to identify the repository input, retrieval configuration, embedding provider, model version, and execution timestamp.
- NFR12: CLI workflows shall produce clear success and failure outcomes, including non-zero exit behavior for failed operational runs.
- NFR13: Failures in indexing, retrieval, and evaluation workflows shall return actionable diagnostic information that helps identify the affected subsystem.
- NFR14: Benchmark outputs shall support regression detection across retrieval strategies and experiment runs.

### Maintainability & Extensibility

- NFR15: The system shall preserve bounded module responsibilities for repository snapshotting, parsing, chunking, embeddings, lexical retrieval, vector retrieval, fusion, output formatting, and evaluation.
- NFR16: Introducing a new chunking strategy, embedding provider, or retrieval fusion variant shall require localized changes rather than cross-system rewrites.
- NFR17: CLI command handlers shall rely on shared internal services so retrieval logic is not duplicated across operational entrypoints.
- NFR18: Architecture and configuration boundaries shall be documented clearly enough that internal engineers can extend the system without reverse-engineering core workflows.

### Integration & Interface Consistency

- NFR19: The MVP shall provide a stable CLI interface for indexing, retrieval, and evaluation workflows.
- NFR20: CLI behavior shall remain scriptable and deterministic enough to support repeated internal experimentation workflows.
- NFR21: Phase 2 MCP integration shall reuse the same core retrieval services and retrieval semantics established by the CLI baseline.
- NFR22: Future interfaces shall not require redefining indexing, retrieval, or evaluation behavior already implemented in the core platform.
