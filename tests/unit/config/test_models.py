from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

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
    monkeypatch.setenv("CODEMAN_SEMANTIC_MODEL_ID", "env-model")
    monkeypatch.setenv("CODEMAN_SEMANTIC_MODEL_VERSION", "env-version")
    monkeypatch.setenv("CODEMAN_SEMANTIC_VECTOR_DIMENSION", "99")

    config = SemanticIndexingConfig()

    assert config.provider_id is None
    assert config.model_id == "hash-embedding"
    assert config.model_version == "1"
    assert config.vector_dimension == 16


def test_semantic_indexing_config_validates_vector_dimension_on_construction() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SemanticIndexingConfig(vector_dimension="abc")

    assert "CODEMAN_SEMANTIC_VECTOR_DIMENSION" in str(exc_info.value)


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
