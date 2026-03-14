# CLI Reference

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
uv run codeman index reindex <repository-id>
uv run codeman index reindex <repository-id> --output-format json
```
