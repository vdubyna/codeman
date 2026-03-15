# CLI Reference

This document owns supported CLI syntax and output contracts.

- For agent implementation rules, see [`project-context.md`](project-context.md).
- For benchmark and evaluation policy, see [`benchmarks.md`](benchmarks.md).
- For architecture intent and extension boundaries, see [`architecture/decisions.md`](architecture/decisions.md) and [`architecture/patterns.md`](architecture/patterns.md).

## Repository Commands

```bash
uv run codeman repo register /path/to/local/repository
uv run codeman repo register /path/to/local/repository --output-format json
```

```bash
uv run codeman repo snapshot <repository-id>
uv run codeman repo snapshot <repository-id> --output-format json
```

## Index Commands

```bash
uv run codeman index extract-sources <snapshot-id>
uv run codeman index extract-sources <snapshot-id> --output-format json
```

```bash
uv run codeman index build-chunks <snapshot-id>
uv run codeman index build-chunks <snapshot-id> --output-format json
```

`index build-chunks` first validates that the live repository still matches the stored snapshot.
Parser cache reuse is keyed by source content identity plus parser policy identity, and reusable
chunk drafts are keyed by source content identity plus the current indexing fingerprint. Cache hits
never mutate prior snapshot artifacts: reused chunk material is always re-materialized into the
active snapshot namespace, and diagnostics report parser/chunk cache reuse vs regeneration counts.
Cached fallback drafts are reused only when the preferred structural path is still unavailable for
the current run; if structural parsing recovers, the file is rebuilt structurally and the fallback
cache entry is replaced.

```bash
uv run codeman index build-lexical <snapshot-id>
uv run codeman index build-lexical <snapshot-id> --output-format json
```

`index build-lexical` reuses the chunk baseline already stored on the snapshot. If the current
effective indexing configuration no longer matches the chunk-generation fingerprint, the command
fails with a stable baseline-missing error and asks you to rerun `index build-chunks` for the
current configuration instead of attributing the lexical build to overrides that never executed.

```bash
uv run codeman index build-semantic <snapshot-id>
uv run codeman index build-semantic <snapshot-id> --output-format json
```

`index build-semantic` is local-first and requires an explicit local embedding configuration.
Keep semantic workflow selection under `semantic_indexing` and provider-owned settings under
`embedding_providers.local_hash`.
Reusable embedding cache entries live under `.codeman/cache/` and are keyed by the current
semantic fingerprint plus snapshot-independent normalized chunk identity. That identity includes
chunk strategy, span metadata, source content identity, and chunk serialization version, so
provider/model/version drift, vector-dimension changes, semantic fingerprint drift, or chunk
content/serialization drift all force regeneration instead of stale reuse.

Project defaults may include non-secret provider metadata:

```toml
[tool.codeman.semantic_indexing]
provider_id = "local-hash"
vector_engine = "sqlite-exact"
vector_dimension = 16
fingerprint_salt = ""

[tool.codeman.embedding_providers.local_hash]
model_id = "hash-embedding"
model_version = "1"
```

Protected local config may include machine-local provider settings:

```toml
[embedding_providers.local_hash]
local_model_path = "/path/to/local/model"
api_key = "local-only-secret"
```

Legacy file-based compatibility remains supported for the current `local-hash` workflow. Existing
project or local TOML files may still use `semantic_indexing.model_id`,
`semantic_indexing.model_version`, and `semantic_indexing.local_model_path`; `codeman` maps those
values into `embedding_providers.local_hash` during config resolution. The separated
`embedding_providers.*` tables are still the canonical shape for new config.

Environment overrides keep the same deterministic precedence as the rest of the config system.
Current supported inputs are:

- `CODEMAN_SEMANTIC_PROVIDER_ID`
- `CODEMAN_SEMANTIC_VECTOR_ENGINE`
- `CODEMAN_SEMANTIC_VECTOR_DIMENSION`
- `CODEMAN_SEMANTIC_FINGERPRINT_SALT`
- `CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_MODEL_ID`
- `CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_MODEL_VERSION`
- `CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_LOCAL_MODEL_PATH`
- `CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_API_KEY`

Compatibility aliases remain supported for the current `local-hash` workflow:

- `CODEMAN_SEMANTIC_MODEL_ID`
- `CODEMAN_SEMANTIC_MODEL_VERSION`
- `CODEMAN_SEMANTIC_LOCAL_MODEL_PATH`

If an environment variable is explicitly present with an empty value for a provider-owned field,
that empty value clears the lower-precedence local/provider setting for the current invocation.

Secret-bearing provider values such as `api_key` are rejected in committed project defaults.
They must come from a protected local config file or environment variables. `config show` omits
raw secret values and reports only whether those fields are configured.

Text output includes:
- Repository, snapshot, and semantic build identifiers.
- Provider and model attribution, including whether the provider stayed local.
- Semantic configuration fingerprint, embedding dimension, embedding artifact path, and vector index path.
- Embedding cache reuse vs regeneration counts for the current build.

JSON output keeps the standard success envelope on `stdout` and returns:
- `repository`
- `snapshot`
- `build`
- `provider`
- `diagnostics`

For `index build-chunks`, `index build-semantic`, and `index reindex`, `diagnostics.cache_summary`
contains machine-readable reuse/regeneration counters. The same cache summary is also stored in
`config provenance show <run-id>` under `workflow_context.cache_summary`. Reindex provenance also
persists `workflow_context.source_files_*` and `workflow_context.chunks_*` counters so no-op and
baseline-clone runs stay truthful about what was reused versus rebuilt.

Successful indexing workflows now also expose a stable `run_id` in `data` for:
- `index build-chunks`
- `index build-lexical`
- `index build-semantic`
- `index reindex`

Text mode prints the same `run_id` on `stdout` alongside the workflow summary. Progress/status
lines remain on `stderr`, so machine-readable JSON `stdout` stays clean.

```bash
uv run codeman index reindex <repository-id>
uv run codeman index reindex <repository-id> --output-format json
```

`index reindex` preserves the existing immutable-baseline behavior for unchanged files: canonical
chunk payloads are cloned forward from the latest eligible snapshot when source content and the
current indexing fingerprint still match. When files must be rebuilt, parser/chunk cache reuse is
allowed only when the current content and indexing identity still match; otherwise the affected
artifacts are regenerated and diagnostics report that regeneration explicitly. `config provenance
show <run-id>` keeps both cache counters and source/chunk reuse counters for the reindex run,
including no-op executions that only cloned baseline work forward logically.

## Query Commands

```bash
uv run codeman query lexical <repository-id> "HomeController"
uv run codeman query lexical <repository-id> "HomeController" --output-format json
uv run codeman query lexical <repository-id> --query="--output-format" --output-format json
```

`query lexical` returns a shared agent-friendly retrieval package for the current repository-scoped lexical build that matches the current effective indexing configuration.
By default, the package is intentionally capped to the top 20 ranked hits so broad queries stay compact and agent-usable.

If no lexical build exists for the latest eligible snapshot and current effective indexing
configuration, `query lexical` fails with a stable baseline-missing error instead of silently
reusing an older or differently configured lexical baseline.

Text output includes:
- Retrieval mode plus repository, snapshot, build, query, and latency metadata.
- One ranked block per result with stable `chunk_id`, relative path, span metadata, language/strategy, score, compact preview text, and a short lexical explanation.
- When a query matches more than the package cap, text output reports the returned count versus the total count and marks the result as truncated.

JSON output keeps the standard success envelope on `stdout` and exposes a single retrieval package shape:

```json
{
  "ok": true,
  "data": {
    "retrieval_mode": "lexical",
    "query": {
      "text": "HomeController"
    },
    "repository": {
      "repository_id": "repo-123",
      "repository_name": "registered-repo"
    },
    "snapshot": {
      "snapshot_id": "snapshot-123",
      "revision_identity": "revision-abc",
      "revision_source": "filesystem_fingerprint"
    },
    "build": {
      "build_id": "build-123",
      "lexical_engine": "sqlite-fts5",
      "tokenizer_spec": "unicode61 remove_diacritics 0 tokenchars '_'",
      "indexed_fields": ["content", "relative_path"]
    },
    "results": [
      {
        "chunk_id": "chunk-123",
        "relative_path": "src/Controller/HomeController.php",
        "language": "php",
        "strategy": "php_structure",
        "rank": 1,
        "score": -1.2345,
        "start_line": 4,
        "end_line": 10,
        "start_byte": 32,
        "end_byte": 180,
        "content_preview": "final class HomeController { public function __invoke(): string { return 'home'; } }",
        "explanation": "Matched lexical terms in path [src/Controller/HomeController.php]."
      }
    ],
    "diagnostics": {
      "match_count": 1,
      "query_latency_ms": 3,
      "total_match_count": 1,
      "truncated": false
    }
  },
  "meta": {
    "command": "query.lexical",
    "output_format": "json"
  }
}
```

## Evaluation Commands

```bash
uv run codeman eval benchmark <repository-id> /path/to/golden_queries.json
uv run codeman eval benchmark <repository-id> /path/to/golden_queries.json --retrieval-mode lexical
uv run codeman eval benchmark <repository-id> /path/to/golden_queries.json --retrieval-mode semantic --output-format json
uv run codeman eval benchmark <repository-id> /path/to/golden_queries.json --retrieval-mode hybrid --max-results 10
```

`eval benchmark` executes one authored benchmark dataset against exactly one retrieval mode for the
current effective repository configuration. It reuses the existing lexical, semantic, or hybrid
query workflows instead of inventing a separate retrieval path, and it records one benchmark-level
run id that is reused for:

- the SQLite `benchmark_runs` lifecycle row
- the generated artifact under `.codeman/artifacts/benchmarks/<run-id>/run.json`
- the configuration provenance row exposed through `config provenance show <run-id>`

Supported options:

- `--retrieval-mode {lexical|semantic|hybrid}` selects exactly one retrieval mode per benchmark run
- `--max-results <1-100>` limits the ranked retrieval results retained for each benchmark case

Progress behavior:

- progress and phase lines are written only to `stderr`
- JSON mode keeps `stdout` as one final success or failure envelope with no interleaved commentary
- stable phase lines currently include dataset loading, baseline resolution, case execution, artifact writing, and provenance recording

Text output includes:

- run id, repository id, snapshot id, retrieval mode, and build id
- dataset id, dataset version, and dataset fingerprint
- case counts, truthful run status, timestamps, and benchmark artifact path

JSON output keeps the standard success envelope on `stdout` and returns:

- `run`
- `repository`
- `snapshot`
- `build`
- `dataset`

Failure semantics:

- invalid benchmark command input fails with `error.code = "input_validation_failed"` and exit code `2`; JSON mode still returns the standard failure envelope on `stdout`
- benchmark dataset path, JSON, and schema failures reuse the stable dataset loader error codes from Story 4.1
- missing selected retrieval baselines fail with `error.code = "benchmark_retrieval_baseline_missing"`
- retrieval-path failures after execution starts fail with `error.code = "benchmark_retrieval_mode_unavailable"`
- repository-not-registered failures keep the shared `repository_not_registered` contract

The benchmark summary is intentionally compact in Story 4.2. Raw per-case evidence lives in the
generated benchmark artifact; metrics, reports, run-to-run comparisons, and regression detection
remain separate later stories.

## Config Commands

All commands resolve configuration with the same deterministic precedence:

1. project defaults from `[tool.codeman]` in `pyproject.toml`
2. optional user-local TOML config
3. optional selected retrieval profile from `--profile <name-or-id>`
4. explicit CLI overrides
5. environment variables as final overrides

The current root-level CLI overrides are intentionally narrow and apply to any command when passed
before the command group:

```bash
uv run codeman --config-path /path/to/config.toml --workspace-root /tmp/codeman-workspace config show
uv run codeman --runtime-root-dir .codeman-dev --metadata-database-name metadata.dev.sqlite3 repo register /path/to/local/repository
uv run codeman --profile fixture-profile config show
uv run codeman --profile fixture-profile index build-semantic <snapshot-id>
```

`CODEMAN_CONFIG_PATH` is the environment equivalent of `--config-path` and is treated as an explicit
local-config override for the current invocation.

`--profile <name-or-id>` resolves one saved retrieval-strategy profile from the current workspace
runtime metadata store before explicit CLI and environment overrides are applied. Profile selection
is limited to retrieval-related settings only: it does not change workspace root selection, runtime
database paths, config file lookup, or repository registration behavior.

The default optional user-local config path is `~/.config/codeman/config.toml` on systems without
`XDG_CONFIG_HOME`, or `$XDG_CONFIG_HOME/codeman/config.toml` when that variable is set. A missing
implicit local config file is non-fatal. An explicit `--config-path` or `CODEMAN_CONFIG_PATH` must
point to a readable TOML file.

```bash
uv run codeman config show
uv run codeman config show --output-format json
uv run codeman --config-path /path/to/config.toml --workspace-root /tmp/workspace config show --output-format json
```

`config show` returns the effective resolved configuration for the current invocation.

Text output includes:
- Source precedence and the resolved project/defaults and local-config paths.
- The currently selected retrieval profile, when `--profile` is supplied.
- Explicit reuse metadata showing whether the invocation is `ad_hoc`, an exact `profile_reuse`, or a `modified_profile_reuse`.
- The selected base profile identity, when applicable, plus the effective `configuration_id` for the current invocation.
- Effective runtime values such as workspace root, runtime root directory, and metadata database name.
- Effective indexing and semantic-indexing settings, plus secret-safe provider-owned settings under `embedding_providers`.
- Secret-bearing provider fields are omitted from text and JSON output; instead, `config show` reports whether a field such as `api_key` is configured.

JSON output keeps the standard success envelope on `stdout` and returns:
- `project_name`
- `default_output_format`
- `runtime`
- `indexing`
- `semantic_indexing` including additive compatibility fields `model_id`, `model_version`, and `local_model_path`
- `embedding_providers`
- `metadata`, including `selected_profile` and additive `configuration_reuse` lineage metadata

When a selected profile is reused unchanged, `metadata.configuration_reuse.reuse_kind` is
`profile_reuse` and its `base_profile_id` matches the effective `configuration_id`. When CLI or
environment overrides change that selected profile for the current invocation, the same metadata
reports `modified_profile_reuse` while preserving the original base profile identity.

`config provenance show <run-id>` exposes the same reuse-lineage semantics for persisted successful
runs. Text and JSON output distinguish the effective `configuration_id` that actually executed from
the optional base profile identity (`base_profile_id`, `base_profile_name`) and the explicit
`reuse_kind`.

Invalid or conflicting configuration fails before the underlying workflow starts. That includes
malformed `[tool.codeman]` defaults in `pyproject.toml`, malformed local TOML config, missing
explicit config paths, and invalid resolved field values. JSON mode returns a standard failure
envelope with `error.code = "configuration_invalid"` and exit code `18`; text mode prints the
validation message on `stderr`.

Saved retrieval-strategy profiles are managed under the nested `config profile` command group:

```bash
uv run codeman config profile save fixture-profile
uv run codeman config profile list
uv run codeman config profile show fixture-profile
uv run codeman config profile show <profile-id>
uv run codeman config profile list --output-format json
```

`config profile save <name>` captures the current retrieval-affecting configuration in a secret-safe
canonical payload:
- `semantic_indexing`
- the selected provider's non-secret `embedding_providers.<provider>` block
- `indexing` fields that already affect retrieval artifacts or baseline matching

Saved profiles receive a stable `profile_id` derived from canonical sorted JSON content. The human
readable `name` is stored separately and must be unique. Re-saving the same `name` with identical
content is idempotent. Re-saving the same `name` with different content fails with
`configuration_profile_name_conflict` instead of silently overwriting the existing record.

`config profile show <name-or-id>` resolves by exact name or exact stable id. If a selector matches
multiple saved profiles, the command fails with `configuration_profile_ambiguous` instead of
guessing. A missing selector fails with `configuration_profile_not_found`.

Profile text and JSON output distinguish profiles by:
- `name`
- `profile_id`
- selected provider and model/version
- vector engine and vector dimension
- non-secret salts and local model path values that materially affect retrieval behavior

Secrets such as provider `api_key` values are never written into saved profile payloads, never
printed in `config profile` output, and never promoted into project defaults.

Stored run configuration provenance is exposed under the nested `config provenance` command group:

```bash
uv run codeman config provenance show <run-id>
uv run codeman config provenance show <run-id> --output-format json
```

Successful indexing and retrieval workflows persist a secret-safe provenance record keyed by
`run_id`. The stored record includes:
- `workflow_type`
- `repository_id`
- `snapshot_id` when the workflow has one
- a stable `configuration_id` derived from canonical effective retrieval config JSON
- explicit reuse lineage: `reuse_kind`, optional `base_profile_id`, and optional `base_profile_name`
- workflow-specific fingerprints such as `indexing_config_fingerprint` and `semantic_config_fingerprint`
- non-secret provider/model metadata when relevant
- secret-safe `effective_config`
- workflow-specific context such as component build ids or compared modes

The provenance store intentionally omits:
- raw provider secrets such as `api_key`
- raw query text
- runtime workspace path overrides
- future eval/judge-only fields that are not implemented in the current codebase

Missing run ids fail with `configuration_provenance_not_found`. Read-only provenance lookups do
not create runtime metadata in an otherwise clean workspace.

```bash
uv run codeman query semantic <repository-id> "controller home route"
uv run codeman query semantic <repository-id> "controller home route" --output-format json
uv run codeman query semantic <repository-id> --query="--query" --output-format json
```

`query semantic` returns the same shared retrieval package shape used by lexical retrieval, but it resolves
the current semantic baseline for the repository and current semantic configuration fingerprint first.
If the latest snapshot or semantic configuration has drifted since the last semantic build, the command fails
with `semantic_build_baseline_missing` instead of silently querying stale vector artifacts.
If the persisted vector artifact no longer matches its recorded metadata, the command fails with
`semantic_artifact_corrupt` instead of returning a misleading empty result set.

Text output includes:
- `run_id` for the persisted semantic-query provenance row
- Retrieval mode plus repository, snapshot, build, query, latency, provider, model, vector engine, and semantic configuration fingerprint metadata.
- One ranked block per result with stable `chunk_id`, relative path, span metadata, language/strategy, score, compact preview text, and a truthful semantic explanation.
- The same top-20 cap and truncated-count reporting used by `query lexical`.

`query semantic` uses the same separated provider configuration layout and environment aliases as
`index build-semantic`. The currently supported provider remains `local-hash`; `codeman` will not
auto-enable an external provider from config alone.

JSON output keeps the standard success envelope on `stdout` and exposes the same retrieval package fields, with
semantic build metadata under `data.build` plus `data.run_id`:

```json
{
  "ok": true,
  "data": {
    "retrieval_mode": "semantic",
    "query": {
      "text": "controller home route"
    },
    "repository": {
      "repository_id": "repo-123",
      "repository_name": "registered-repo"
    },
    "snapshot": {
      "snapshot_id": "snapshot-123",
      "revision_identity": "revision-abc",
      "revision_source": "filesystem_fingerprint"
    },
    "build": {
      "build_id": "semantic-build-123",
      "provider_id": "local-hash",
      "model_id": "fixture-local",
      "model_version": "2026-03-14",
      "vector_engine": "sqlite-exact",
      "semantic_config_fingerprint": "semantic-fingerprint-123"
    },
    "results": [
      {
        "chunk_id": "chunk-123",
        "relative_path": "src/Controller/HomeController.php",
        "language": "php",
        "strategy": "php_structure",
        "rank": 1,
        "score": 0.875,
        "start_line": 4,
        "end_line": 10,
        "start_byte": 32,
        "end_byte": 180,
        "content_preview": "final class HomeController { public function __invoke(): string { return 'home'; } }",
        "explanation": "Ranked by embedding similarity against the persisted semantic index."
      }
    ],
    "diagnostics": {
      "match_count": 1,
      "query_latency_ms": 7,
      "total_match_count": 8,
      "truncated": true
    }
  },
  "meta": {
    "command": "query.semantic",
    "output_format": "json"
  }
}
```

```bash
uv run codeman query hybrid <repository-id> "controller home route"
uv run codeman query hybrid <repository-id> "controller home route" --output-format json
uv run codeman query hybrid <repository-id> --query="--query" --output-format json
```

`query hybrid` composes the current repository-scoped lexical and semantic query paths, requests a larger
internal candidate window for fusion, and then returns the standard top-20 retrieval package after
deterministic Reciprocal Rank Fusion (RRF).
If either component baseline is unavailable for the latest repository snapshot and current effective
configuration, the command fails with `hybrid_component_baseline_missing` instead of pretending it
ran full hybrid fusion.
If the lexical and semantic component paths resolve different repository snapshots, the command fails with
`hybrid_snapshot_mismatch` instead of fusing mixed-state evidence.

Text output includes:
- `run_id` for the persisted hybrid-query provenance row
- Retrieval mode plus repository, snapshot, synthetic hybrid build id, query, and latency metadata.
- Fusion metadata: fusion strategy, rank constant, rank window size, lexical build id, lexical indexing fingerprint, semantic build id, and semantic provider/model attribution.
- Per-component diagnostics for lexical and semantic retrieval, including latency, component match counts, and how many final fused results each component contributed.
- One ranked block per result with stable `chunk_id`, relative path, span metadata, language/strategy, fused score, compact preview text, and a truthful explanation stating whether lexical evidence, semantic evidence, or both contributed to the final rank.

JSON output keeps the standard success envelope on `stdout` and exposes the shared retrieval package shape, with
hybrid fusion and component provenance nested under `data.build`, `data.run_id` for later
inspection, and per-component diagnostics nested under `data.diagnostics`:

```json
{
  "ok": true,
  "data": {
    "retrieval_mode": "hybrid",
    "query": {
      "text": "controller home route"
    },
    "repository": {
      "repository_id": "repo-123",
      "repository_name": "registered-repo"
    },
    "snapshot": {
      "snapshot_id": "snapshot-123",
      "revision_identity": "revision-abc",
      "revision_source": "filesystem_fingerprint"
    },
    "build": {
      "build_id": "hybrid-123abc456def",
      "fusion_strategy": "rrf",
      "rank_constant": 60,
      "rank_window_size": 50,
      "lexical_build": {
        "build_id": "lexical-build-123",
        "indexing_config_fingerprint": "indexing-fingerprint-123",
        "lexical_engine": "sqlite-fts5",
        "tokenizer_spec": "unicode61 remove_diacritics 0 tokenchars '_'",
        "indexed_fields": ["content", "relative_path"]
      },
      "semantic_build": {
        "build_id": "semantic-build-123",
        "provider_id": "local-hash",
        "model_id": "fixture-local",
        "model_version": "2026-03-14",
        "vector_engine": "sqlite-exact",
        "semantic_config_fingerprint": "semantic-fingerprint-123"
      }
    },
    "results": [
      {
        "chunk_id": "chunk-123",
        "relative_path": "src/Controller/HomeController.php",
        "language": "php",
        "strategy": "php_structure",
        "rank": 1,
        "score": 0.0323,
        "start_line": 4,
        "end_line": 10,
        "start_byte": 32,
        "end_byte": 180,
        "content_preview": "final class HomeController { public function __invoke(): string { return 'home'; } }",
        "explanation": "Fused hybrid rank from lexical and semantic evidence for this persisted chunk."
      }
    ],
    "diagnostics": {
      "match_count": 1,
      "query_latency_ms": 9,
      "total_match_count": 4,
      "truncated": true,
      "fusion_strategy": "rrf",
      "rank_constant": 60,
      "rank_window_size": 50,
      "total_match_count_is_lower_bound": false,
      "degraded": false,
      "degraded_reason": null,
      "lexical": {
        "match_count": 2,
        "query_latency_ms": 4,
        "total_match_count": 2,
        "truncated": false,
        "contributed_result_count": 1
      },
      "semantic": {
        "match_count": 3,
        "query_latency_ms": 5,
        "total_match_count": 6,
        "truncated": true,
        "contributed_result_count": 1
      }
    }
  },
  "meta": {
    "command": "query.hybrid",
    "output_format": "json"
  }
}
```

When `data.diagnostics.total_match_count_is_lower_bound` is `true`, the reported hybrid
`total_match_count` is a truthful lower bound rather than an exact union size because at least one
component retriever was truncated before fusion.

## Compare Commands

```bash
uv run codeman compare query-modes <repository-id> "controller home route"
uv run codeman compare query-modes <repository-id> "controller home route" --output-format json
uv run codeman compare query-modes <repository-id> --query="--query" --output-format json
```

`compare query-modes` executes lexical retrieval, semantic retrieval, and one hybrid fusion workflow
for the same repository query, then returns a single attributable comparison package.
The command is still local-first and artifact-only: it reuses the current persisted lexical and semantic
baselines for the repository instead of rescanning source files or rereading mutated working-tree content.
If either required component baseline is unavailable for the latest repository snapshot and current
effective configuration, the command fails with `compare_retrieval_mode_baseline_missing`.
If one compared mode is unavailable because of artifact corruption, provider initialization failure, or
another underlying retrieval-path problem, the command fails with `compare_retrieval_mode_unavailable`.
If lexical and semantic comparison inputs resolve different repository snapshots, the command fails with
`compare_retrieval_mode_snapshot_mismatch` instead of presenting a misleading side-by-side comparison.

Text output includes:
- `run_id` for the persisted comparison provenance row
- Shared repository, snapshot, query, latency, and compared-mode metadata for the full comparison run.
- One summary line per mode using the same returned-count and truncation semantics as the standalone
  query commands.
- A compact rank-alignment section keyed by `chunk_id`, showing lexical, semantic, and hybrid ranks plus
  rank deltas when hybrid also contains the chunk.
- Clearly labeled `Lexical Results`, `Semantic Results`, and `Hybrid Results` blocks that preserve the
  standard ranked retrieval item shape.

JSON output keeps the standard success envelope on `stdout` and exposes a stable comparison package
with additive `data.run_id` for provenance inspection:

```json
{
  "ok": true,
  "data": {
    "query": {
      "text": "controller home route"
    },
    "repository": {
      "repository_id": "repo-123",
      "repository_name": "registered-repo"
    },
    "snapshot": {
      "snapshot_id": "snapshot-123",
      "revision_identity": "revision-abc",
      "revision_source": "filesystem_fingerprint"
    },
    "entries": [
      {
        "retrieval_mode": "lexical",
        "build": {
          "build_id": "lexical-build-123",
          "lexical_engine": "sqlite-fts5",
          "tokenizer_spec": "unicode61 remove_diacritics 0 tokenchars '_'",
          "indexed_fields": ["content", "relative_path"]
        },
        "diagnostics": {
          "match_count": 2,
          "query_latency_ms": 4,
          "total_match_count": 2,
          "truncated": false
        },
        "results": [
          {
            "chunk_id": "chunk-shared",
            "relative_path": "src/Controller/HomeController.php",
            "language": "php",
            "strategy": "php_structure",
            "rank": 1,
            "score": -1.0,
            "start_line": 4,
            "end_line": 10,
            "start_byte": 32,
            "end_byte": 180,
            "content_preview": "final class HomeController { public function __invoke(): string { return 'home'; } }",
            "explanation": "Matched lexical terms in path src/Controller/[HomeController].php."
          }
        ]
      },
      {
        "retrieval_mode": "semantic",
        "build": {
          "build_id": "semantic-build-123",
          "provider_id": "local-hash",
          "model_id": "fixture-local",
          "model_version": "2026-03-14",
          "vector_engine": "sqlite-exact",
          "semantic_config_fingerprint": "semantic-fingerprint-123"
        },
        "diagnostics": {
          "match_count": 2,
          "query_latency_ms": 7,
          "total_match_count": 5,
          "truncated": false
        },
        "results": [
          {
            "chunk_id": "chunk-shared",
            "relative_path": "src/Controller/HomeController.php",
            "language": "php",
            "strategy": "php_structure",
            "rank": 1,
            "score": 0.92,
            "start_line": 4,
            "end_line": 10,
            "start_byte": 32,
            "end_byte": 180,
            "content_preview": "final class HomeController { public function __invoke(): string { return 'home'; } }",
            "explanation": "Ranked by embedding similarity against the persisted semantic index."
          }
        ]
      },
      {
        "retrieval_mode": "hybrid",
        "build": {
          "build_id": "hybrid-123abc456def",
          "fusion_strategy": "rrf",
          "rank_constant": 60,
          "rank_window_size": 50,
          "lexical_build": {
            "build_id": "lexical-build-123",
            "lexical_engine": "sqlite-fts5",
            "tokenizer_spec": "unicode61 remove_diacritics 0 tokenchars '_'",
            "indexed_fields": ["content", "relative_path"]
          },
          "semantic_build": {
            "build_id": "semantic-build-123",
            "provider_id": "local-hash",
            "model_id": "fixture-local",
            "model_version": "2026-03-14",
            "vector_engine": "sqlite-exact",
            "semantic_config_fingerprint": "semantic-fingerprint-123"
          }
        },
        "diagnostics": {
          "match_count": 2,
          "query_latency_ms": 9,
          "total_match_count": 4,
          "truncated": true,
          "fusion_strategy": "rrf",
          "rank_constant": 60,
          "rank_window_size": 50,
          "total_match_count_is_lower_bound": false,
          "degraded": false,
          "degraded_reason": null,
          "lexical": {
            "match_count": 2,
            "query_latency_ms": 4,
            "total_match_count": 2,
            "truncated": false,
            "contributed_result_count": 2
          },
          "semantic": {
            "match_count": 2,
            "query_latency_ms": 7,
            "total_match_count": 5,
            "truncated": false,
            "contributed_result_count": 1
          }
        },
        "results": [
          {
            "chunk_id": "chunk-shared",
            "relative_path": "src/Controller/HomeController.php",
            "language": "php",
            "strategy": "php_structure",
            "rank": 1,
            "score": 0.0328,
            "start_line": 4,
            "end_line": 10,
            "start_byte": 32,
            "end_byte": 180,
            "content_preview": "final class HomeController { public function __invoke(): string { return 'home'; } }",
            "explanation": "Fused hybrid rank from lexical and semantic evidence for this persisted chunk."
          }
        ]
      }
    ],
    "alignment": [
      {
        "chunk_id": "chunk-shared",
        "relative_path": "src/Controller/HomeController.php",
        "language": "php",
        "strategy": "php_structure",
        "lexical_rank": 1,
        "semantic_rank": 1,
        "hybrid_rank": 1,
        "lexical_score": -1.0,
        "semantic_score": 0.92,
        "hybrid_score": 0.0328
      }
    ],
    "diagnostics": {
      "compared_modes": ["lexical", "semantic", "hybrid"],
      "alignment_count": 1,
      "overlap_count": 1,
      "query_latency_ms": 11
    }
  },
  "meta": {
    "command": "compare.query_modes",
    "output_format": "json"
  }
}
```
