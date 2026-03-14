"""Narrow semantic-indexing configuration and fingerprint helpers."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SEMANTIC_INDEX_FINGERPRINT_SCHEMA_VERSION = "1"
SEMANTIC_PROVIDER_POLICY_VERSIONS = {
    "local-hash": "local-hash-v1",
}
SEMANTIC_VECTOR_ENGINE_POLICY_VERSIONS = {
    "sqlite-exact": "sqlite-exact-v1",
}


def _optional_path_from_env(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    return Path(value).expanduser().resolve()


class SemanticIndexingConfig(BaseModel):
    """Minimal semantic-indexing configuration for local-first attribution."""

    model_config = ConfigDict(extra="forbid")

    provider_id: str | None = Field(
        default_factory=lambda: os.environ.get("CODEMAN_SEMANTIC_PROVIDER_ID"),
    )
    model_id: str = Field(
        default_factory=lambda: os.environ.get("CODEMAN_SEMANTIC_MODEL_ID", "hash-embedding"),
    )
    model_version: str = Field(
        default_factory=lambda: os.environ.get("CODEMAN_SEMANTIC_MODEL_VERSION", "1"),
    )
    local_model_path: Path | None = Field(
        default_factory=lambda: _optional_path_from_env("CODEMAN_SEMANTIC_LOCAL_MODEL_PATH"),
    )
    vector_engine: str = Field(
        default_factory=lambda: os.environ.get("CODEMAN_SEMANTIC_VECTOR_ENGINE", "sqlite-exact"),
    )
    vector_dimension: int | str = Field(
        default_factory=lambda: os.environ.get("CODEMAN_SEMANTIC_VECTOR_DIMENSION", "16"),
    )
    fingerprint_salt: str = Field(
        default_factory=lambda: os.environ.get("CODEMAN_SEMANTIC_FINGERPRINT_SALT", ""),
    )

    def resolved_vector_dimension(self) -> int:
        """Return the configured embedding dimension as a validated integer."""

        raw_value = self.vector_dimension
        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Invalid CODEMAN_SEMANTIC_VECTOR_DIMENSION; expected a positive integer."
            ) from exc

        if value <= 0:
            raise ValueError(
                "Invalid CODEMAN_SEMANTIC_VECTOR_DIMENSION; expected a positive integer."
            )

        return value


def build_semantic_indexing_descriptor(config: SemanticIndexingConfig) -> dict[str, Any]:
    """Return the normalized fingerprint payload for the current semantic policy."""

    vector_dimension = config.resolved_vector_dimension()
    return {
        "schema_version": SEMANTIC_INDEX_FINGERPRINT_SCHEMA_VERSION,
        "provider": {
            "provider_id": config.provider_id,
            "provider_policy_version": SEMANTIC_PROVIDER_POLICY_VERSIONS.get(
                config.provider_id,
            ),
            "model_id": config.model_id,
            "model_version": config.model_version,
            "local_model_path": (
                str(config.local_model_path) if config.local_model_path is not None else None
            ),
        },
        "vector_index": {
            "vector_engine": config.vector_engine,
            "vector_engine_policy_version": SEMANTIC_VECTOR_ENGINE_POLICY_VERSIONS.get(
                config.vector_engine,
            ),
            "vector_dimension": vector_dimension,
        },
        "cli_knobs": {
            "fingerprint_salt": config.fingerprint_salt,
        },
    }


def build_semantic_indexing_fingerprint(config: SemanticIndexingConfig) -> str:
    """Build a deterministic fingerprint for the current semantic-indexing policy."""

    descriptor = build_semantic_indexing_descriptor(config)
    encoded = json.dumps(
        descriptor,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
