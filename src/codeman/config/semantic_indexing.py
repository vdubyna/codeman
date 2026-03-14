"""Narrow semantic-indexing configuration and fingerprint helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codeman.config.embedding_providers import EmbeddingProvidersConfig

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
    vector_engine: str = Field(default="sqlite-exact")
    vector_dimension: int = Field(default=16)
    fingerprint_salt: str = Field(default="")

    @field_validator("provider_id", mode="before")
    @classmethod
    def _normalize_provider_id(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        return value

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


def build_semantic_indexing_descriptor(
    config: SemanticIndexingConfig,
    embedding_providers: EmbeddingProvidersConfig,
) -> dict[str, Any]:
    """Return the normalized fingerprint payload for the current semantic policy."""

    vector_dimension = config.resolved_vector_dimension()
    selected_provider = embedding_providers.get_provider_config(config.provider_id)
    return {
        "schema_version": SEMANTIC_INDEX_FINGERPRINT_SCHEMA_VERSION,
        "provider": {
            "provider_id": config.provider_id,
            "provider_policy_version": SEMANTIC_PROVIDER_POLICY_VERSIONS.get(
                config.provider_id,
            ),
            "model_id": selected_provider.model_id if selected_provider is not None else None,
            "model_version": (
                selected_provider.model_version if selected_provider is not None else None
            ),
            "local_model_path": (
                str(selected_provider.local_model_path)
                if selected_provider is not None and selected_provider.local_model_path is not None
                else None
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


def build_semantic_indexing_fingerprint(
    config: SemanticIndexingConfig,
    embedding_providers: EmbeddingProvidersConfig,
) -> str:
    """Build a deterministic fingerprint for the current semantic-indexing policy."""

    descriptor = build_semantic_indexing_descriptor(config, embedding_providers)
    encoded = json.dumps(
        descriptor,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
