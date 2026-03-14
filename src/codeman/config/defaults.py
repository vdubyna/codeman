"""Project-default configuration loading."""

from __future__ import annotations

import tomllib
from copy import deepcopy
from pathlib import Path
from typing import Any

from codeman.config.paths import resolve_project_pyproject_path

IN_CODE_DEFAULTS: dict[str, Any] = {
    "project_name": "codeman",
    "default_output_format": "text",
    "runtime": {
        "root_dir_name": ".codeman",
        "metadata_database_name": "metadata.sqlite3",
    },
    "indexing": {
        "fingerprint_salt": "",
    },
    "semantic_indexing": {
        "provider_id": None,
        "model_id": "hash-embedding",
        "model_version": "1",
        "local_model_path": None,
        "vector_engine": "sqlite-exact",
        "vector_dimension": 16,
        "fingerprint_salt": "",
    },
}


def _merge_nested_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _merge_nested_dicts(merged[key], value)
            continue
        merged[key] = value
    return merged


def load_project_defaults(pyproject_path: Path | None = None) -> dict[str, Any]:
    """Load project defaults from ``pyproject.toml`` with stable in-code fallbacks."""

    resolved_pyproject_path = pyproject_path or resolve_project_pyproject_path()
    if not resolved_pyproject_path.exists():
        return deepcopy(IN_CODE_DEFAULTS)

    with resolved_pyproject_path.open("rb") as file_handle:
        document = tomllib.load(file_handle)

    codeman_defaults = document.get("tool", {}).get("codeman")
    if not isinstance(codeman_defaults, dict):
        return deepcopy(IN_CODE_DEFAULTS)

    return _merge_nested_dicts(IN_CODE_DEFAULTS, codeman_defaults)


__all__ = ["IN_CODE_DEFAULTS", "load_project_defaults"]
