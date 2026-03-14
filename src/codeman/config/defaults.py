"""Project-default configuration loading."""

from __future__ import annotations

import tomllib
from copy import deepcopy
from pathlib import Path
from typing import Any

from codeman.config.paths import resolve_project_pyproject_path

LEGACY_SEMANTIC_PROVIDER_FIELD_NAMES = (
    "model_id",
    "model_version",
    "local_model_path",
)

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
        "vector_engine": "sqlite-exact",
        "vector_dimension": 16,
        "fingerprint_salt": "",
    },
    "embedding_providers": {
        "local_hash": {
            "model_id": "hash-embedding",
            "model_version": "1",
            "local_model_path": None,
            "api_key": None,
        },
    },
}


def _migrate_legacy_semantic_provider_fields(payload: dict[str, Any]) -> dict[str, Any]:
    semantic_payload = payload.get("semantic_indexing")
    if not isinstance(semantic_payload, dict):
        return payload

    legacy_provider_payload = {
        field_name: semantic_payload[field_name]
        for field_name in LEGACY_SEMANTIC_PROVIDER_FIELD_NAMES
        if field_name in semantic_payload
    }
    if not legacy_provider_payload:
        return payload

    normalized_payload = deepcopy(payload)
    normalized_semantic_payload = normalized_payload.get("semantic_indexing", {})
    for field_name in legacy_provider_payload:
        normalized_semantic_payload.pop(field_name, None)

    embedding_providers_payload = normalized_payload.setdefault("embedding_providers", {})
    local_hash_payload = embedding_providers_payload.setdefault("local_hash", {})
    for field_name, value in legacy_provider_payload.items():
        local_hash_payload.setdefault(field_name, value)
    return normalized_payload


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

    return _merge_nested_dicts(
        IN_CODE_DEFAULTS,
        _migrate_legacy_semantic_provider_fields(codeman_defaults),
    )


__all__ = ["IN_CODE_DEFAULTS", "load_project_defaults"]
