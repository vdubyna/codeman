"""Secret-safe effective-configuration provenance helpers."""

from __future__ import annotations

from codeman.config.embedding_providers import LOCAL_HASH_PROVIDER_ID
from codeman.config.indexing import IndexingConfig
from codeman.config.models import AppConfig
from codeman.config.retrieval_profiles import (
    RetrievalStrategyProfileEmbeddingProvidersConfig,
    RetrievalStrategyProfilePayload,
    RetrievalStrategyProfileProviderConfig,
    build_retrieval_strategy_profile_canonical_json,
    build_retrieval_strategy_profile_id,
)
from codeman.config.semantic_indexing import SemanticIndexingConfig


def build_effective_config_provenance_payload(
    config: AppConfig,
) -> RetrievalStrategyProfilePayload:
    """Return the canonical effective retrieval payload for run provenance.

    Provenance must stay truthful for lexical-only workflows even when semantic config points at a
    provider that is not yet implemented for saved profile reuse. In that case we preserve the
    selected provider id in `semantic_indexing` and omit any provider-specific block we cannot
    serialize secret-safely today.
    """

    provider_id = config.semantic_indexing.provider_id
    selected_provider = config.embedding_providers.get_provider_config(provider_id)
    embedding_providers = RetrievalStrategyProfileEmbeddingProvidersConfig()
    if provider_id == LOCAL_HASH_PROVIDER_ID and selected_provider is not None:
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


def build_effective_config_provenance_canonical_json(
    payload: RetrievalStrategyProfilePayload,
) -> str:
    """Serialize effective config provenance deterministically for storage and hashing."""

    return build_retrieval_strategy_profile_canonical_json(payload)


def build_effective_config_provenance_id(
    payload: RetrievalStrategyProfilePayload,
) -> str:
    """Derive the stable effective configuration identifier."""

    return build_retrieval_strategy_profile_id(payload)


__all__ = [
    "build_effective_config_provenance_canonical_json",
    "build_effective_config_provenance_id",
    "build_effective_config_provenance_payload",
]
