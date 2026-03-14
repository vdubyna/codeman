# Benchmarks and Evaluation

This document owns human-facing benchmark and evaluation policy for `codeman`.

- Command syntax belongs in [`cli-reference.md`](cli-reference.md).
- Agent implementation rules belong in [`project-context.md`](project-context.md).
- Product rationale and future scope belong in [`../_bmad-output/planning-artifacts/prd.md`](../_bmad-output/planning-artifacts/prd.md).

## Current Status

- The current implementation provides retrieval and indexing foundations plus reserved `eval` and `compare` CLI groups.
- Full benchmark orchestration, provider-backed judge runs, and model-comparison workflows are planned but not fully implemented in the current codebase.
- Documentation in this file should stay honest about what exists now versus what is still planned.

## Benchmark Baseline Policy

- Benchmark datasets may contain both human-authored queries and synthetic candidate queries.
- Synthetic data must be reviewed, versioned, and explicitly promoted before it becomes a benchmark baseline.
- LLM-as-a-judge output is an auxiliary evaluation signal, not the sole source of truth.
- Benchmark comparisons should stay reproducible across runs by preserving dataset versions, configuration identity, and runtime metadata.

## Required Evaluation Metadata

Every benchmark or judge run should capture, at minimum:

- repository and snapshot identity
- revision identity and revision source
- indexing configuration fingerprint
- dataset version
- provider name when external providers are used
- model name or version
- grader version for judge workflows
- timestamp
- evaluation configuration relevant to the run

## Privacy and Provider Boundaries

- Local-only development must remain viable without OpenAI or another external provider.
- Any workflow that sends repository content, chunks, embeddings, or query content to an external provider must be explicit and opt-in.
- Provider usage should be visible in runtime output and persisted in experiment metadata.
- Secrets should come from environment variables or protected local configuration, never source control.
- Cost-aware workflows should surface enough metadata for later attribution and comparison.

## What Belongs Here

- benchmark terminology
- dataset and baseline rules
- evaluation metadata expectations
- privacy and reproducibility requirements
- human-facing explanation of planned evaluation workflows

## What Does Not Belong Here

- exact CLI command syntax already documented in `cli-reference.md`
- general coding rules already documented in `project-context.md`
- full architecture rationale already captured in planning artifacts and architecture docs
