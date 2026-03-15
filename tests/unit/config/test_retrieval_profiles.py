from __future__ import annotations

from pathlib import Path

from codeman.config.embedding_providers import EmbeddingProviderConfig, EmbeddingProvidersConfig
from codeman.config.models import AppConfig
from codeman.config.retrieval_profiles import (
    RetrievalStrategyProfilePayload,
    build_retrieval_strategy_profile_canonical_json,
    build_retrieval_strategy_profile_id,
    build_retrieval_strategy_profile_payload,
)
from codeman.config.semantic_indexing import SemanticIndexingConfig


def test_retrieval_strategy_profile_payload_omits_provider_secrets(tmp_path: Path) -> None:
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    config = AppConfig(
        semantic_indexing=SemanticIndexingConfig(provider_id="local-hash"),
        embedding_providers=EmbeddingProvidersConfig(
            local_hash=EmbeddingProviderConfig(
                model_id="fixture-local",
                model_version="2026-03-14",
                local_model_path=local_model_path,
                api_key="super-secret",
            )
        ),
    )

    payload = build_retrieval_strategy_profile_payload(config)
    serialized = payload.model_dump(mode="json")

    assert serialized["semantic_indexing"]["provider_id"] == "local-hash"
    assert serialized["embedding_providers"]["local_hash"]["model_id"] == "fixture-local"
    assert serialized["embedding_providers"]["local_hash"]["local_model_path"] == str(
        local_model_path.resolve()
    )
    assert "api_key" not in serialized["embedding_providers"]["local_hash"]
    assert "super-secret" not in repr(serialized)


def test_retrieval_strategy_profile_canonical_json_is_deterministic() -> None:
    first_payload = RetrievalStrategyProfilePayload.model_validate(
        {
            "semantic_indexing": {
                "provider_id": "local-hash",
                "vector_dimension": 32,
                "vector_engine": "sqlite-exact",
                "fingerprint_salt": "semantic-salt",
            },
            "embedding_providers": {
                "local_hash": {
                    "model_version": "2026-03-14",
                    "model_id": "fixture-local",
                    "local_model_path": "/tmp/model",
                }
            },
            "indexing": {"fingerprint_salt": "indexing-salt"},
        }
    )
    second_payload = RetrievalStrategyProfilePayload.model_validate(
        {
            "indexing": {"fingerprint_salt": "indexing-salt"},
            "embedding_providers": {
                "local_hash": {
                    "local_model_path": "/tmp/model",
                    "model_id": "fixture-local",
                    "model_version": "2026-03-14",
                }
            },
            "semantic_indexing": {
                "fingerprint_salt": "semantic-salt",
                "vector_engine": "sqlite-exact",
                "provider_id": "local-hash",
                "vector_dimension": 32,
            },
        }
    )

    assert build_retrieval_strategy_profile_canonical_json(
        first_payload
    ) == build_retrieval_strategy_profile_canonical_json(second_payload)
    assert build_retrieval_strategy_profile_id(
        first_payload
    ) == build_retrieval_strategy_profile_id(second_payload)


def test_retrieval_strategy_profile_id_changes_when_retrieval_settings_change(
    tmp_path: Path,
) -> None:
    first_model_path = tmp_path / "model-a"
    second_model_path = tmp_path / "model-b"
    first_model_path.mkdir()
    second_model_path.mkdir()
    first_config = AppConfig(
        semantic_indexing=SemanticIndexingConfig(
            provider_id="local-hash",
            vector_dimension=16,
        ),
        embedding_providers=EmbeddingProvidersConfig(
            local_hash=EmbeddingProviderConfig(
                model_id="fixture-local",
                model_version="2026-03-14",
                local_model_path=first_model_path,
            )
        ),
    )
    second_config = AppConfig(
        semantic_indexing=SemanticIndexingConfig(
            provider_id="local-hash",
            vector_dimension=16,
        ),
        embedding_providers=EmbeddingProvidersConfig(
            local_hash=EmbeddingProviderConfig(
                model_id="fixture-local",
                model_version="2026-03-14",
                local_model_path=second_model_path,
            )
        ),
    )

    assert build_retrieval_strategy_profile_id(
        build_retrieval_strategy_profile_payload(first_config)
    ) != build_retrieval_strategy_profile_id(
        build_retrieval_strategy_profile_payload(second_config)
    )
