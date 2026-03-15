from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from codeman.config.embedding_providers import EmbeddingProviderConfig, EmbeddingProvidersConfig
from codeman.config.models import AppConfig
from codeman.config.retrieval_profiles import (
    build_retrieval_strategy_profile_id,
    build_retrieval_strategy_profile_payload,
)
from codeman.config.semantic_indexing import SemanticIndexingConfig
from codeman.contracts.configuration import RetrievalStrategyProfileRecord
from codeman.infrastructure.persistence.sqlite.engine import create_sqlite_engine
from codeman.infrastructure.persistence.sqlite.repositories.retrieval_profile_repository import (
    SqliteRetrievalStrategyProfileStore,
)


def _build_profile_record(tmp_path: Path, *, name: str) -> RetrievalStrategyProfileRecord:
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir(exist_ok=True)
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
    return RetrievalStrategyProfileRecord(
        name=name,
        profile_id=build_retrieval_strategy_profile_id(payload),
        payload=payload,
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="2026-03-14",
        vector_engine="sqlite-exact",
        vector_dimension=16,
        created_at=datetime.now(UTC),
    )


def test_sqlite_retrieval_profile_store_persists_and_lists_profiles(tmp_path: Path) -> None:
    database_path = tmp_path / ".codeman" / "metadata.sqlite3"
    store = SqliteRetrievalStrategyProfileStore(
        engine=create_sqlite_engine(database_path),
        database_path=database_path,
    )
    first_record = _build_profile_record(tmp_path, name="alpha")
    second_record = _build_profile_record(tmp_path, name="beta")

    store.initialize()
    store.create_profile(first_record)
    store.create_profile(second_record)

    loaded_by_name = store.get_by_name("alpha")
    loaded_by_id = store.list_by_profile_id(first_record.profile_id)
    listed_profiles = store.list_profiles()

    assert loaded_by_name is not None
    assert loaded_by_name.profile_id == first_record.profile_id
    assert [profile.name for profile in loaded_by_id] == ["alpha", "beta"]
    assert [profile.name for profile in listed_profiles] == ["alpha", "beta"]


def test_sqlite_retrieval_profile_store_does_not_persist_provider_secrets(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / ".codeman" / "metadata.sqlite3"
    store = SqliteRetrievalStrategyProfileStore(
        engine=create_sqlite_engine(database_path),
        database_path=database_path,
    )
    record = _build_profile_record(tmp_path, name="fixture-profile")

    store.initialize()
    store.create_profile(record)

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "select payload_json from retrieval_strategy_profiles where name = ?",
            (record.name,),
        ).fetchone()

    assert row is not None
    assert "api_key" not in row[0]
    assert "super-secret" not in row[0]


def test_sqlite_retrieval_profile_store_read_only_lookups_do_not_create_runtime_metadata(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / ".codeman" / "metadata.sqlite3"
    store = SqliteRetrievalStrategyProfileStore(
        engine=create_sqlite_engine(database_path),
        database_path=database_path,
    )

    assert store.get_by_name("missing-profile") is None
    assert store.list_by_profile_id("missing-profile") == []
    assert store.list_profiles() == []
    assert not database_path.parent.exists()
    assert not database_path.exists()


def test_sqlite_retrieval_profile_store_treats_missing_profile_table_as_empty(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / ".codeman" / "metadata.sqlite3"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path):
        pass

    store = SqliteRetrievalStrategyProfileStore(
        engine=create_sqlite_engine(database_path),
        database_path=database_path,
    )

    assert store.get_by_name("missing-profile") is None
    assert store.list_by_profile_id("missing-profile") == []
    assert store.list_profiles() == []
