from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from codeman.config.embedding_providers import EmbeddingProviderConfig, EmbeddingProvidersConfig
from codeman.config.indexing import IndexingConfig
from codeman.config.models import AppConfig, RuntimeConfig
from codeman.config.semantic_indexing import SemanticIndexingConfig


def test_runtime_config_ignores_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEMAN_WORKSPACE_ROOT", "/tmp/env-workspace")
    monkeypatch.setenv("CODEMAN_RUNTIME_ROOT_DIR", ".env-root")
    monkeypatch.setenv("CODEMAN_METADATA_DATABASE_NAME", "env.sqlite3")

    config = RuntimeConfig()

    assert config.workspace_root == Path.cwd().resolve()
    assert config.root_dir_name == ".codeman"
    assert config.metadata_database_name == "metadata.sqlite3"


def test_indexing_config_ignores_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEMAN_INDEXING_FINGERPRINT_SALT", "env-salt")

    config = IndexingConfig()

    assert config.fingerprint_salt == ""


def test_semantic_indexing_config_ignores_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEMAN_SEMANTIC_PROVIDER_ID", "local-hash")
    monkeypatch.setenv("CODEMAN_SEMANTIC_VECTOR_DIMENSION", "99")

    config = SemanticIndexingConfig()

    assert config.provider_id is None
    assert config.vector_dimension == 16


def test_semantic_indexing_config_validates_vector_dimension_on_construction() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SemanticIndexingConfig(vector_dimension="abc")

    assert "CODEMAN_SEMANTIC_VECTOR_DIMENSION" in str(exc_info.value)


def test_embedding_providers_config_ignores_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_MODEL_ID", "env-model")
    monkeypatch.setenv("CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_MODEL_VERSION", "env-version")

    config = EmbeddingProvidersConfig()

    assert config.local_hash.model_id == "hash-embedding"
    assert config.local_hash.model_version == "1"


def test_app_config_keeps_nested_source_agnostic_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEMAN_INDEXING_FINGERPRINT_SALT", "env-salt")
    monkeypatch.setenv("CODEMAN_SEMANTIC_PROVIDER_ID", "local-hash")

    config = AppConfig()

    assert config.project_name == "codeman"
    assert config.default_output_format == "text"
    assert config.indexing.fingerprint_salt == ""
    assert config.semantic_indexing.provider_id is None
    assert config.embedding_providers.local_hash.model_id == "hash-embedding"


def test_app_config_operator_payload_keeps_legacy_semantic_fields_additively(
    tmp_path: Path,
) -> None:
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    config = AppConfig(
        semantic_indexing=SemanticIndexingConfig(provider_id="local-hash"),
        embedding_providers=EmbeddingProvidersConfig(
            local_hash=EmbeddingProviderConfig(
                model_id="fixture-local",
                model_version="2026-03-14",
                local_model_path=local_model_path,
            ),
        ),
    )

    payload = config.to_operator_payload()

    assert payload["semantic_indexing"]["provider_id"] == "local-hash"
    assert payload["semantic_indexing"]["model_id"] == "fixture-local"
    assert payload["semantic_indexing"]["model_version"] == "2026-03-14"
    assert payload["semantic_indexing"]["local_model_path"] == str(local_model_path.resolve())
    assert payload["embedding_providers"]["local_hash"]["model_id"] == "fixture-local"
