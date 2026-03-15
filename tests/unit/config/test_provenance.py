from __future__ import annotations

from pathlib import Path

from codeman.config.embedding_providers import EmbeddingProviderConfig, EmbeddingProvidersConfig
from codeman.config.models import AppConfig
from codeman.config.provenance import (
    build_effective_config_provenance_canonical_json,
    build_effective_config_provenance_id,
    build_effective_config_provenance_payload,
)
from codeman.config.retrieval_profiles import (
    build_retrieval_strategy_profile_canonical_json,
    build_retrieval_strategy_profile_id,
    build_retrieval_strategy_profile_payload,
)
from codeman.config.semantic_indexing import SemanticIndexingConfig


def test_effective_config_provenance_payload_reuses_secret_safe_profile_payload(
    tmp_path: Path,
) -> None:
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    config = AppConfig(
        semantic_indexing=SemanticIndexingConfig(
            provider_id="local-hash",
            vector_dimension=32,
            fingerprint_salt="semantic-salt",
        ),
        embedding_providers=EmbeddingProvidersConfig(
            local_hash=EmbeddingProviderConfig(
                model_id="fixture-local",
                model_version="2026-03-15",
                local_model_path=local_model_path,
                api_key="super-secret",
            )
        ),
    )

    provenance_payload = build_effective_config_provenance_payload(config)
    profile_payload = build_retrieval_strategy_profile_payload(config)

    assert provenance_payload == profile_payload
    assert provenance_payload.embedding_providers.local_hash is not None
    assert provenance_payload.embedding_providers.local_hash.model_id == "fixture-local"
    assert (
        "api_key"
        not in provenance_payload.model_dump(mode="json")["embedding_providers"]["local_hash"]
    )


def test_effective_config_provenance_id_matches_profile_id_for_same_effective_config() -> None:
    provenance_payload = build_effective_config_provenance_payload(
        AppConfig(
            semantic_indexing=SemanticIndexingConfig(
                provider_id="local-hash",
                vector_dimension=24,
                fingerprint_salt="semantic-salt",
            ),
        )
    )
    profile_payload = build_retrieval_strategy_profile_payload(
        AppConfig(
            semantic_indexing=SemanticIndexingConfig(
                provider_id="local-hash",
                vector_dimension=24,
                fingerprint_salt="semantic-salt",
            ),
        )
    )

    assert build_effective_config_provenance_canonical_json(
        provenance_payload
    ) == build_retrieval_strategy_profile_canonical_json(profile_payload)
    assert build_effective_config_provenance_id(
        provenance_payload
    ) == build_retrieval_strategy_profile_id(profile_payload)


def test_effective_config_provenance_payload_keeps_unknown_provider_ids_without_failing() -> None:
    payload = build_effective_config_provenance_payload(
        AppConfig(
            semantic_indexing=SemanticIndexingConfig(
                provider_id="openai",
                vector_dimension=24,
                fingerprint_salt="semantic-salt",
            ),
        )
    )

    assert payload.semantic_indexing.provider_id == "openai"
    assert payload.embedding_providers.local_hash is None
    assert build_effective_config_provenance_id(payload)
