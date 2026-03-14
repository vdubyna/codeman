"""Narrow semantic-indexing configuration and fingerprint helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

SEMANTIC_INDEX_FINGERPRINT_SCHEMA_VERSION = "1"
SEMANTIC_PROVIDER_POLICY_VERSIONS = {
    "local-hash": "local-hash-v1",
}
SEMANTIC_VECTOR_ENGINE_POLICY_VERSIONS = {
    "sqlite-exact": "sqlite-exact-v1",
}

class SemanticIndexingConfig(BaseModel):
    """Minimal semantic-indexing configuration for local-first attribution."""

    model_config = ConfigDict(extra="forbid")

    provider_id: str | None = Field(default=None)
    model_id: str = Field(default="hash-embedding")
    model_version: str = Field(default="1")
    local_model_path: Path | None = Field(default=None)
    vector_engine: str = Field(default="sqlite-exact")
    vector_dimension: int = Field(default=16)
    fingerprint_salt: str = Field(default="")

    @field_validator("provider_id", mode="before")
    @classmethod
    def _normalize_provider_id(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        return value

    @field_validator("local_model_path", mode="before")
    @classmethod
    def _resolve_local_model_path(cls, value: Path | str | None) -> Path | None:
        if value in (None, ""):
            return None
        return Path(value).expanduser().resolve()

    @field_validator("vector_dimension", mode="before")
    @classmethod
    def _validate_vector_dimension(cls, value: int | str) -> int:
        message = "Invalid CODEMAN_SEMANTIC_VECTOR_DIMENSION; expected a positive integer."
        try:
            resolved_value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(message) from exc

        if resolved_value <= 0:
            raise ValueError(message)

        return resolved_value

    def resolved_vector_dimension(self) -> int:
        """Return the configured embedding dimension as a validated integer."""

        return self.vector_dimension


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
