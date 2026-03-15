"""Canonical retrieval-strategy profile models and helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codeman.config.embedding_providers import LOCAL_HASH_PROVIDER_ID
from codeman.config.indexing import IndexingConfig
from codeman.config.models import AppConfig
from codeman.config.semantic_indexing import SemanticIndexingConfig


class RetrievalStrategyProfileProviderConfig(BaseModel):
    """Non-secret provider settings that materially affect retrieval behavior."""

    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(default="hash-embedding")
    model_version: str = Field(default="1")
    local_model_path: Path | None = Field(default=None)

    @field_validator("local_model_path", mode="before")
    @classmethod
    def _resolve_local_model_path(cls, value: Path | str | None) -> Path | None:
        if value in (None, ""):
            return None
        return Path(value).expanduser().resolve()


class RetrievalStrategyProfileEmbeddingProvidersConfig(BaseModel):
    """Selected provider settings retained in the canonical profile payload."""

    model_config = ConfigDict(extra="forbid")

    local_hash: RetrievalStrategyProfileProviderConfig | None = None

    def get_provider_config(
        self, provider_id: str | None
    ) -> RetrievalStrategyProfileProviderConfig | None:
        """Return the stored provider block for the selected provider id."""

        if provider_id in (None, ""):
            return None
        if provider_id != LOCAL_HASH_PROVIDER_ID:
            return None
        return self.local_hash


class RetrievalStrategyProfilePayload(BaseModel):
    """Canonical, secret-safe retrieval-profile payload."""

    model_config = ConfigDict(extra="forbid")

    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
    semantic_indexing: SemanticIndexingConfig = Field(default_factory=SemanticIndexingConfig)
    embedding_providers: RetrievalStrategyProfileEmbeddingProvidersConfig = Field(
        default_factory=RetrievalStrategyProfileEmbeddingProvidersConfig
    )

    def to_loader_payload(self) -> dict[str, Any]:
        """Return the payload in a shape suitable for config-layer merging."""

        return self.model_dump(mode="json")


def normalize_retrieval_profile_selector(value: str | None, *, field_name: str) -> str:
    """Trim and validate operator-supplied profile names and selectors."""

    if value is None:
        raise ValueError(f"Retrieval strategy profile {field_name} must not be blank.")

    normalized_value = value.strip()
    if not normalized_value:
        raise ValueError(f"Retrieval strategy profile {field_name} must not be blank.")

    return normalized_value


def build_retrieval_strategy_profile_payload(config: AppConfig) -> RetrievalStrategyProfilePayload:
    """Extract the current retrieval-affecting configuration into the canonical payload."""

    provider_id = config.semantic_indexing.provider_id
    embedding_providers = RetrievalStrategyProfileEmbeddingProvidersConfig()
    if provider_id not in (None, ""):
        selected_provider = config.embedding_providers.get_provider_config(provider_id)
        if selected_provider is None or provider_id != LOCAL_HASH_PROVIDER_ID:
            raise ValueError(
                "Retrieval strategy profiles currently support only implemented provider ids."
            )
        embedding_providers = RetrievalStrategyProfileEmbeddingProvidersConfig(
            local_hash=RetrievalStrategyProfileProviderConfig(
                model_id=selected_provider.model_id,
                model_version=selected_provider.model_version,
                local_model_path=selected_provider.local_model_path,
            )
        )

    return RetrievalStrategyProfilePayload(
        indexing=IndexingConfig.model_validate(config.indexing.model_dump(mode="json")),
        semantic_indexing=SemanticIndexingConfig.model_validate(
            config.semantic_indexing.model_dump(mode="json")
        ),
        embedding_providers=embedding_providers,
    )


def build_retrieval_strategy_profile_canonical_json(
    payload: RetrievalStrategyProfilePayload,
) -> str:
    """Serialize the profile payload deterministically for hashing and persistence."""

    return json.dumps(
        payload.to_loader_payload(),
        separators=(",", ":"),
        sort_keys=True,
    )


def build_retrieval_strategy_profile_id(payload: RetrievalStrategyProfilePayload) -> str:
    """Derive the stable profile identifier from the canonical payload."""

    canonical_json = build_retrieval_strategy_profile_canonical_json(payload)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


__all__ = [
    "RetrievalStrategyProfileEmbeddingProvidersConfig",
    "RetrievalStrategyProfilePayload",
    "RetrievalStrategyProfileProviderConfig",
    "build_retrieval_strategy_profile_canonical_json",
    "build_retrieval_strategy_profile_id",
    "build_retrieval_strategy_profile_payload",
    "normalize_retrieval_profile_selector",
]
