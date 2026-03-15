# Benchmarks and Evaluation

This document owns human-facing benchmark and evaluation policy for `codeman`.

- Command syntax belongs in [`cli-reference.md`](cli-reference.md).
- Agent implementation rules belong in [`project-context.md`](project-context.md).
- Product rationale and future scope belong in [`../_bmad-output/planning-artifacts/prd.md`](../_bmad-output/planning-artifacts/prd.md).

## Current Status

- The current implementation provides retrieval and indexing foundations plus reserved `eval` and `compare` CLI groups.
- The current implementation now includes strict benchmark dataset contracts plus a JSON-only dataset loader for authored golden-query inputs.
- The current implementation now includes `eval benchmark`, which executes one authored dataset against exactly one indexed retrieval mode and records a truthful benchmark run lifecycle.
- Benchmark execution persists a compact SQLite run row plus a raw artifact under `.codeman/artifacts/benchmarks/<run-id>/run.json`, reuses one shared run id for configuration provenance, and now stores additive metric outputs under `.codeman/artifacts/benchmarks/<run-id>/metrics.json`.
- The current implementation now calculates and stores benchmark metrics automatically for successful benchmark runs, including `Recall@K`, `MRR`, `NDCG@K`, query latency summaries, and truthful indexing-duration summaries where available.
- The current implementation now includes `eval report`, which renders a deterministic Markdown review artifact under `.codeman/artifacts/benchmarks/<run-id>/report.md` from the persisted run row, raw artifact, metrics artifact, and run provenance.
- The current implementation now includes `compare benchmark-runs`, which compares persisted benchmark runs side by side, reports per-metric winners or ties, and surfaces explicit comparability notes when context differs.
- Regression detection, provider-backed judge workflows, and model-comparison workflows remain future work for Story 4.6 and beyond.
- Documentation in this file should stay honest about what exists now versus what is still planned.

## Implemented Benchmark Dataset Schema

- Authored benchmark datasets are JSON documents loaded from explicit filesystem paths outside `.codeman/`.
- Each dataset currently requires `schema_version`, `dataset_id`, `dataset_version`, and a non-empty `cases` list.
- Each case currently requires `query_id`, `query_text`, `source_kind`, and at least one relevance judgment.
- `source_kind` is intentionally narrow for now: `human_authored` and `synthetic_reviewed`.
- Relevance judgments use one canonical shape: `relative_path`, optional `language`, optional 1-based `start_line` and `end_line`, plus integer `relevance_grade`.
- Benchmark truth must anchor to normalized repository-relative POSIX paths. Snapshot-scoped identifiers such as chunk ids or snapshot ids are not benchmark truth.
- The current schema validates duplicate `query_id` values, blank query text, empty judgments, invalid path anchors, invalid line spans, and invalid relevance grades before any future benchmark execution begins.
- The loader derives deterministic summary metadata including case counts, judgment counts, and a canonical dataset fingerprint. That fingerprint is additive metadata, not a substitute for the human-managed `dataset_version`.
- The seeded fixture lives at `tests/fixtures/queries/mixed_stack_fixture_golden_queries.json` and remains intentionally small and human-authored.

## Benchmark Baseline Policy

- Benchmark datasets may contain both human-authored queries and synthetic candidate queries.
- Synthetic data must be reviewed, versioned, and explicitly promoted before it becomes a benchmark baseline.
- LLM-as-a-judge output is an auxiliary evaluation signal, not the sole source of truth.
- Benchmark comparisons should stay reproducible across runs by preserving dataset versions, configuration identity, and runtime metadata.

## Implemented Benchmark Execution Surface

- `eval benchmark <repository-id> <dataset-path>` is the canonical execution command for benchmark runs.
- Each benchmark run executes exactly one retrieval mode: `lexical`, `semantic`, or `hybrid`.
- Preflight validation stays explicit: dataset load and validation run first, then baseline resolution for the selected retrieval mode, and only then is a `benchmark_runs` row created.
- The benchmark row moves truthfully through `running -> succeeded` or `running -> failed`.
- Dataset validation failures happen before execution starts and therefore do not create misleading completed benchmark rows.
- Raw benchmark artifacts snapshot the normalized dataset inputs actually used for the run, including dataset id/version/fingerprint, authored judgments, ranked retrieval outputs, and query diagnostics.
- Successful benchmark runs now also persist one additive metrics artifact that keeps:
  - the explicit evaluated cutoff `k`
  - aggregate `Recall@K`, `MRR`, and graded `NDCG@K`
  - per-case metric details derived from the persisted raw ranking window
  - query latency summary fields
  - lexical and/or semantic build durations where those values were explicitly recorded on build metadata
- `run.json` remains the raw execution evidence. Metrics are additive metadata and do not replace the meaning of the raw artifact.
- If explicit build duration was unavailable on the relevant build record, the metrics layer leaves the indexing-duration field null instead of synthesizing a fake value.
- `eval report <run-id>` now renders a concise review artifact from that persisted evidence. The
  report includes benchmark identity, build/config provenance, aggregate metrics, and a compact
  per-case appendix without duplicating the entire raw benchmark payload.
- `compare benchmark-runs --run-id ...` now compares only persisted benchmark evidence:
  - the benchmark lifecycle row
  - `run.json`
  - `metrics.json`
  - stored configuration provenance
- Benchmark comparison preserves the requested run order, fails explicitly on cross-repository or
  incomplete/corrupt evidence, and marks contextual mismatches instead of implying a clean
  apples-to-apples comparison when snapshot, dataset, evaluated cutoff, or case count differ.
- The comparison command is read-only: it does not create a separate comparison provenance row,
  because the compared benchmark runs already carry the truthful configuration provenance that the
  side-by-side output surfaces directly.

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
