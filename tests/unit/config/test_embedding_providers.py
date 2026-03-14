from __future__ import annotations

from pathlib import Path

from codeman.config.embedding_providers import (
    LOCAL_HASH_PROVIDER_ID,
    EmbeddingProviderConfig,
    EmbeddingProvidersConfig,
)


def test_embedding_provider_config_resolves_local_model_path(tmp_path: Path) -> None:
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()

    config = EmbeddingProviderConfig(
        model_id="fixture-local",
        model_version="2026-03-14",
        local_model_path=local_model_path,
    )

    assert config.local_model_path == local_model_path.resolve()


def test_embedding_providers_config_resolves_selected_provider() -> None:
    providers = EmbeddingProvidersConfig(
        local_hash=EmbeddingProviderConfig(
            model_id="fixture-local",
            model_version="2026-03-14",
        ),
    )

    selected = providers.get_provider_config(LOCAL_HASH_PROVIDER_ID)

    assert selected is not None
    assert selected.model_id == "fixture-local"
    assert providers.get_provider_config(None) is None
    assert providers.get_provider_config("missing-provider") is None


def test_embedding_providers_operator_payload_omits_raw_secret_values() -> None:
    providers = EmbeddingProvidersConfig(
        local_hash=EmbeddingProviderConfig(
            model_id="fixture-local",
            model_version="2026-03-14",
            api_key="super-secret",
        ),
    )

    payload = providers.to_operator_payload()

    assert payload["local_hash"]["model_id"] == "fixture-local"
    assert payload["local_hash"]["api_key_configured"] is True
    assert "api_key" not in payload["local_hash"]
    assert "super-secret" not in repr(payload)
