from __future__ import annotations

from pathlib import Path

from codeman.config.semantic_indexing import (
    SemanticIndexingConfig,
    build_semantic_indexing_fingerprint,
)


def test_semantic_indexing_fingerprint_is_stable_for_same_config(tmp_path: Path) -> None:
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    config = SemanticIndexingConfig(
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="1",
        local_model_path=local_model_path,
        vector_engine="sqlite-exact",
        vector_dimension=8,
    )

    assert build_semantic_indexing_fingerprint(config) == build_semantic_indexing_fingerprint(
        config
    )


def test_semantic_indexing_fingerprint_changes_when_model_path_changes(tmp_path: Path) -> None:
    first_local_model_path = tmp_path / "local-model-a"
    second_local_model_path = tmp_path / "local-model-b"
    first_local_model_path.mkdir()
    second_local_model_path.mkdir()
    first_config = SemanticIndexingConfig(
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="1",
        local_model_path=first_local_model_path,
        vector_engine="sqlite-exact",
        vector_dimension=8,
    )
    second_config = SemanticIndexingConfig(
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="1",
        local_model_path=second_local_model_path,
        vector_engine="sqlite-exact",
        vector_dimension=8,
    )

    assert build_semantic_indexing_fingerprint(first_config) != build_semantic_indexing_fingerprint(
        second_config,
    )


def test_semantic_indexing_reports_invalid_vector_dimension_without_crashing() -> None:
    config = SemanticIndexingConfig(vector_dimension="abc")

    try:
        config.resolved_vector_dimension()
    except ValueError as exc:
        assert "CODEMAN_SEMANTIC_VECTOR_DIMENSION" in str(exc)
    else:
        raise AssertionError("Expected invalid vector dimension to raise ValueError.")
