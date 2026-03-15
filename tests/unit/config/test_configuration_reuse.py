from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codeman.config.configuration_reuse import build_configuration_reuse_lineage
from codeman.config.embedding_providers import EmbeddingProviderConfig, EmbeddingProvidersConfig
from codeman.config.models import AppConfig
from codeman.config.provenance import build_effective_config_provenance_payload
from codeman.config.retrieval_profiles import (
    build_retrieval_strategy_profile_id,
    build_retrieval_strategy_profile_payload,
)
from codeman.config.semantic_indexing import SemanticIndexingConfig
from codeman.contracts.configuration import RetrievalStrategyProfileRecord


def build_selected_profile(
    *,
    name: str,
    config: AppConfig,
) -> RetrievalStrategyProfileRecord:
    payload = build_retrieval_strategy_profile_payload(config)
    provider = payload.embedding_providers.local_hash
    return RetrievalStrategyProfileRecord(
        name=name,
        profile_id=build_retrieval_strategy_profile_id(payload),
        payload=payload,
        provider_id=payload.semantic_indexing.provider_id,
        model_id=provider.model_id if provider is not None else None,
        model_version=provider.model_version if provider is not None else None,
        vector_engine=payload.semantic_indexing.vector_engine,
        vector_dimension=payload.semantic_indexing.resolved_vector_dimension(),
        created_at=datetime.now(UTC),
    )


def test_configuration_reuse_is_ad_hoc_without_selected_profile(tmp_path: Path) -> None:
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    config = AppConfig(
        semantic_indexing=SemanticIndexingConfig(provider_id="local-hash"),
        embedding_providers=EmbeddingProvidersConfig(
            local_hash=EmbeddingProviderConfig(local_model_path=local_model_path)
        ),
    )

    lineage = build_configuration_reuse_lineage(
        selected_profile=None,
        effective_config=build_effective_config_provenance_payload(config),
    )

    assert lineage.reuse_kind == "ad_hoc"
    assert lineage.base_profile_id is None
    assert lineage.base_profile_name is None
    assert lineage.effective_configuration_id


def test_configuration_reuse_detects_exact_profile_replay(tmp_path: Path) -> None:
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    config = AppConfig(
        semantic_indexing=SemanticIndexingConfig(
            provider_id="local-hash",
            vector_dimension=32,
        ),
        embedding_providers=EmbeddingProvidersConfig(
            local_hash=EmbeddingProviderConfig(local_model_path=local_model_path)
        ),
    )
    selected_profile = build_selected_profile(name="fixture-profile", config=config)

    lineage = build_configuration_reuse_lineage(
        selected_profile=selected_profile,
        effective_config=build_effective_config_provenance_payload(config),
    )

    assert lineage.reuse_kind == "profile_reuse"
    assert lineage.base_profile_id == selected_profile.profile_id
    assert lineage.base_profile_name == "fixture-profile"
    assert lineage.effective_configuration_id == selected_profile.profile_id


def test_configuration_reuse_detects_modified_profile_replay_without_leaking_secrets(
    tmp_path: Path,
) -> None:
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    selected_profile_config = AppConfig(
        semantic_indexing=SemanticIndexingConfig(provider_id="local-hash"),
        embedding_providers=EmbeddingProvidersConfig(
            local_hash=EmbeddingProviderConfig(
                local_model_path=local_model_path,
                api_key="super-secret",
            )
        ),
    )
    effective_config = AppConfig(
        semantic_indexing=SemanticIndexingConfig(
            provider_id="local-hash",
            vector_dimension=48,
        ),
        embedding_providers=EmbeddingProvidersConfig(
            local_hash=EmbeddingProviderConfig(
                local_model_path=local_model_path,
                api_key="super-secret",
            )
        ),
    )
    selected_profile = build_selected_profile(
        name="fixture-profile",
        config=selected_profile_config,
    )

    lineage = build_configuration_reuse_lineage(
        selected_profile=selected_profile,
        effective_config=build_effective_config_provenance_payload(effective_config),
    )

    assert lineage.reuse_kind == "modified_profile_reuse"
    assert lineage.base_profile_id == selected_profile.profile_id
    assert lineage.base_profile_name == "fixture-profile"
    assert lineage.effective_configuration_id != selected_profile.profile_id
    assert "super-secret" not in lineage.model_dump_json()
