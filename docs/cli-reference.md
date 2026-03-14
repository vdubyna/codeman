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

```bash
uv run codeman index build-lexical <snapshot-id>
uv run codeman index build-lexical <snapshot-id> --output-format json
```

```bash
uv run codeman index build-semantic <snapshot-id>
uv run codeman index build-semantic <snapshot-id> --output-format json
```

`index build-semantic` is local-first and requires an explicit local embedding configuration.
Set `CODEMAN_SEMANTIC_PROVIDER_ID=local-hash` and `CODEMAN_SEMANTIC_LOCAL_MODEL_PATH=/path/to/local/model`
before running the command. `codeman` will not auto-enable OpenAI or another external provider when
semantic indexing is requested without explicit opt-in.

Text output includes:
- Repository, snapshot, and semantic build identifiers.
- Provider and model attribution, including whether the provider stayed local.
- Semantic configuration fingerprint, embedding dimension, embedding artifact path, and vector index path.

JSON output keeps the standard success envelope on `stdout` and returns:
- `repository`
- `snapshot`
- `build`
- `provider`
- `diagnostics`

```bash
uv run codeman index reindex <repository-id>
uv run codeman index reindex <repository-id> --output-format json
```

## Query Commands

```bash
uv run codeman query lexical <repository-id> "HomeController"
uv run codeman query lexical <repository-id> "HomeController" --output-format json
uv run codeman query lexical <repository-id> --query="--output-format" --output-format json
```

`query lexical` returns a shared agent-friendly retrieval package for the current repository-scoped lexical build.
By default, the package is intentionally capped to the top 20 ranked hits so broad queries stay compact and agent-usable.

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
- Retrieval mode plus repository, snapshot, build, query, latency, provider, model, vector engine, and semantic configuration fingerprint metadata.
- One ranked block per result with stable `chunk_id`, relative path, span metadata, language/strategy, score, compact preview text, and a truthful semantic explanation.
- The same top-20 cap and truncated-count reporting used by `query lexical`.

JSON output keeps the standard success envelope on `stdout` and exposes the same retrieval package fields, with
semantic build metadata under `data.build`:

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
