from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from codeman.config.embedding_providers import EmbeddingProviderConfig, EmbeddingProvidersConfig
from codeman.config.semantic_indexing import (
    SemanticIndexingConfig,
    build_semantic_indexing_fingerprint,
)


def test_semantic_indexing_fingerprint_is_stable_for_same_config(tmp_path: Path) -> None:
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    config = SemanticIndexingConfig(
        provider_id="local-hash",
        vector_engine="sqlite-exact",
        vector_dimension=8,
    )
    providers = EmbeddingProvidersConfig(
        local_hash=EmbeddingProviderConfig(
            model_id="fixture-local",
            model_version="1",
            local_model_path=local_model_path,
        ),
    )

    assert build_semantic_indexing_fingerprint(
        config,
        providers,
    ) == build_semantic_indexing_fingerprint(
        config,
        providers,
    )


def test_semantic_indexing_fingerprint_changes_when_model_path_changes(tmp_path: Path) -> None:
    first_local_model_path = tmp_path / "local-model-a"
    second_local_model_path = tmp_path / "local-model-b"
    first_local_model_path.mkdir()
    second_local_model_path.mkdir()
    first_config = SemanticIndexingConfig(
        provider_id="local-hash",
        vector_engine="sqlite-exact",
        vector_dimension=8,
    )
    second_config = SemanticIndexingConfig(
        provider_id="local-hash",
        vector_engine="sqlite-exact",
        vector_dimension=8,
    )
    first_providers = EmbeddingProvidersConfig(
        local_hash=EmbeddingProviderConfig(
            model_id="fixture-local",
            model_version="1",
            local_model_path=first_local_model_path,
        ),
    )
    second_providers = EmbeddingProvidersConfig(
        local_hash=EmbeddingProviderConfig(
            model_id="fixture-local",
            model_version="1",
            local_model_path=second_local_model_path,
        ),
    )

    assert build_semantic_indexing_fingerprint(
        second_config,
        second_providers,
    ) != build_semantic_indexing_fingerprint(
        first_config,
        first_providers,
    )


def test_semantic_indexing_normalizes_valid_string_vector_dimension() -> None:
    config = SemanticIndexingConfig(vector_dimension="8")

    assert config.resolved_vector_dimension() == 8


def test_semantic_indexing_rejects_invalid_vector_dimension() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SemanticIndexingConfig(vector_dimension="abc")

    assert "CODEMAN_SEMANTIC_VECTOR_DIMENSION" in str(exc_info.value)


def test_semantic_indexing_fingerprint_ignores_provider_settings_when_provider_not_selected(
    tmp_path: Path,
) -> None:
    first_local_model_path = tmp_path / "local-model-a"
    second_local_model_path = tmp_path / "local-model-b"
    first_local_model_path.mkdir()
    second_local_model_path.mkdir()
    config = SemanticIndexingConfig(provider_id=None, vector_dimension=8)
    first_providers = EmbeddingProvidersConfig(
        local_hash=EmbeddingProviderConfig(
            model_id="fixture-a",
            model_version="1",
            local_model_path=first_local_model_path,
        ),
    )
    second_providers = EmbeddingProvidersConfig(
        local_hash=EmbeddingProviderConfig(
            model_id="fixture-b",
            model_version="2",
            local_model_path=second_local_model_path,
        ),
    )

    assert build_semantic_indexing_fingerprint(
        config,
        first_providers,
    ) == build_semantic_indexing_fingerprint(
        config,
        second_providers,
    )
