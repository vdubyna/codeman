from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from codeman.application.provenance.record_run_provenance import (
    RecordRunConfigurationProvenanceUseCase,
)
from codeman.config.embedding_providers import EmbeddingProviderConfig, EmbeddingProvidersConfig
from codeman.config.models import AppConfig
from codeman.config.retrieval_profiles import (
    build_retrieval_strategy_profile_id,
    build_retrieval_strategy_profile_payload,
)
from codeman.config.semantic_indexing import SemanticIndexingConfig
from codeman.contracts.configuration import (
    RecordRunConfigurationProvenanceRequest,
    RetrievalStrategyProfileRecord,
    RunConfigurationProvenanceRecord,
    RunProvenanceWorkflowContext,
)


@dataclass
class StubRunProvenanceStore:
    created_records: list[RunConfigurationProvenanceRecord] = field(default_factory=list)
    initialized: bool = False

    def initialize(self) -> None:
        self.initialized = True

    def create_record(
        self, record: RunConfigurationProvenanceRecord
    ) -> RunConfigurationProvenanceRecord:
        self.created_records.append(record)
        return record

    def get_by_run_id(self, run_id: str) -> RunConfigurationProvenanceRecord | None:
        for record in self.created_records:
            if record.run_id == run_id:
                return record
        return None

    def list_by_repository_id(self, repository_id: str) -> list[RunConfigurationProvenanceRecord]:
        return [record for record in self.created_records if record.repository_id == repository_id]


def build_profile_record(
    *,
    name: str,
    profile_id: str,
    config: AppConfig,
) -> RetrievalStrategyProfileRecord:
    payload = build_retrieval_strategy_profile_payload(config)
    provider = payload.embedding_providers.local_hash
    return RetrievalStrategyProfileRecord(
        name=name,
        profile_id=profile_id,
        payload=payload,
        provider_id=payload.semantic_indexing.provider_id,
        model_id=provider.model_id if provider is not None else None,
        model_version=provider.model_version if provider is not None else None,
        vector_engine=payload.semantic_indexing.vector_engine,
        vector_dimension=payload.semantic_indexing.resolved_vector_dimension(),
        created_at=datetime.now(UTC),
    )


def test_record_run_provenance_builds_secret_safe_effective_config_and_stable_identity(
    tmp_path: Path,
) -> None:
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    store = StubRunProvenanceStore()
    use_case = RecordRunConfigurationProvenanceUseCase(
        config=AppConfig(
            semantic_indexing=SemanticIndexingConfig(
                provider_id="local-hash",
                vector_dimension=32,
            ),
            embedding_providers=EmbeddingProvidersConfig(
                local_hash=EmbeddingProviderConfig(
                    model_id="fixture-local",
                    model_version="2026-03-15",
                    local_model_path=local_model_path,
                    api_key="super-secret",
                )
            ),
        ),
        provenance_store=store,
    )

    record = use_case.execute(
        RecordRunConfigurationProvenanceRequest(
            workflow_type="query.semantic",
            repository_id="repo-123",
            snapshot_id="snapshot-123",
            semantic_config_fingerprint="semantic-fingerprint-123",
            provider_id="local-hash",
            model_id="fixture-local",
            model_version="2026-03-15",
            workflow_context=RunProvenanceWorkflowContext(
                semantic_build_id="semantic-build-123",
                max_results=7,
            ),
        )
    )

    assert store.initialized is True
    assert record.repository_id == "repo-123"
    assert record.workflow_type == "query.semantic"
    assert record.semantic_config_fingerprint == "semantic-fingerprint-123"
    assert record.workflow_context.semantic_build_id == "semantic-build-123"
    assert record.workflow_context.max_results == 7
    assert record.configuration_id
    assert record.configuration_reuse.reuse_kind == "ad_hoc"
    assert record.configuration_reuse.effective_configuration_id == record.configuration_id
    assert record.effective_config.embedding_providers.local_hash is not None
    assert record.effective_config.embedding_providers.local_hash.model_id == "fixture-local"
    assert "super-secret" not in record.effective_config.model_dump_json()


def test_record_run_provenance_respects_explicit_run_id() -> None:
    store = StubRunProvenanceStore()
    use_case = RecordRunConfigurationProvenanceUseCase(
        config=AppConfig(),
        provenance_store=store,
    )

    record = use_case.execute(
        RecordRunConfigurationProvenanceRequest(
            run_id="existing-run-123",
            workflow_type="index.reindex",
            repository_id="repo-123",
            snapshot_id="snapshot-456",
            indexing_config_fingerprint="indexing-fingerprint-123",
            workflow_context=RunProvenanceWorkflowContext(
                previous_snapshot_id="snapshot-123",
                result_snapshot_id="snapshot-456",
                noop=False,
            ),
        )
    )

    assert record.run_id == "existing-run-123"
    assert store.created_records[0].run_id == "existing-run-123"


def test_record_run_provenance_does_not_backfill_semantic_metadata_for_lexical_workflows(
    tmp_path: Path,
) -> None:
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    store = StubRunProvenanceStore()
    use_case = RecordRunConfigurationProvenanceUseCase(
        config=AppConfig(
            semantic_indexing=SemanticIndexingConfig(provider_id="local-hash"),
            embedding_providers=EmbeddingProvidersConfig(
                local_hash=EmbeddingProviderConfig(
                    model_id="fixture-local",
                    model_version="2026-03-15",
                    local_model_path=local_model_path,
                )
            ),
        ),
        provenance_store=store,
    )

    record = use_case.execute(
        RecordRunConfigurationProvenanceRequest(
            workflow_type="query.lexical",
            repository_id="repo-123",
            snapshot_id="snapshot-123",
            indexing_config_fingerprint="indexing-fingerprint-123",
            workflow_context=RunProvenanceWorkflowContext(
                lexical_build_id="lexical-build-123",
                max_results=5,
            ),
        )
    )

    assert record.provider_id is None
    assert record.model_id is None
    assert record.model_version is None
    assert record.configuration_reuse.reuse_kind == "ad_hoc"


def test_record_run_provenance_allows_lexical_workflows_with_unimplemented_semantic_provider() -> (
    None
):
    store = StubRunProvenanceStore()
    use_case = RecordRunConfigurationProvenanceUseCase(
        config=AppConfig(
            semantic_indexing=SemanticIndexingConfig(provider_id="openai"),
        ),
        provenance_store=store,
    )

    record = use_case.execute(
        RecordRunConfigurationProvenanceRequest(
            workflow_type="query.lexical",
            repository_id="repo-123",
            snapshot_id="snapshot-123",
            indexing_config_fingerprint="indexing-fingerprint-123",
            workflow_context=RunProvenanceWorkflowContext(
                lexical_build_id="lexical-build-123",
                max_results=5,
            ),
        )
    )

    assert record.configuration_id
    assert record.effective_config.semantic_indexing.provider_id == "openai"
    assert record.provider_id is None
    assert record.model_id is None
    assert record.model_version is None
    assert record.configuration_reuse.reuse_kind == "ad_hoc"


def test_record_run_provenance_marks_exact_selected_profile_reuse(tmp_path: Path) -> None:
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    store = StubRunProvenanceStore()
    config = AppConfig(
        semantic_indexing=SemanticIndexingConfig(
            provider_id="local-hash",
            vector_dimension=32,
        ),
        embedding_providers=EmbeddingProvidersConfig(
            local_hash=EmbeddingProviderConfig(
                model_id="fixture-local",
                model_version="2026-03-15",
                local_model_path=local_model_path,
            )
        ),
    )
    selected_profile = build_profile_record(
        name="fixture-profile",
        profile_id=build_retrieval_strategy_profile_id(
            build_retrieval_strategy_profile_payload(config)
        ),
        config=config,
    )
    use_case = RecordRunConfigurationProvenanceUseCase(
        config=config,
        provenance_store=store,
        selected_profile=selected_profile,
    )

    record = use_case.execute(
        RecordRunConfigurationProvenanceRequest(
            workflow_type="index.build-lexical",
            repository_id="repo-123",
            snapshot_id="snapshot-123",
            indexing_config_fingerprint="indexing-fingerprint-123",
        )
    )

    assert record.configuration_reuse.reuse_kind == "profile_reuse"
    assert record.configuration_reuse.base_profile_id == selected_profile.profile_id
    assert record.configuration_reuse.base_profile_name == "fixture-profile"
    assert record.configuration_reuse.effective_configuration_id == record.configuration_id
    assert record.configuration_id == selected_profile.profile_id


def test_record_run_provenance_marks_modified_selected_profile_reuse(tmp_path: Path) -> None:
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    store = StubRunProvenanceStore()
    selected_profile_config = AppConfig(
        semantic_indexing=SemanticIndexingConfig(
            provider_id="local-hash",
            vector_dimension=32,
        ),
        embedding_providers=EmbeddingProvidersConfig(
            local_hash=EmbeddingProviderConfig(
                model_id="fixture-local",
                model_version="2026-03-15",
                local_model_path=local_model_path,
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
                model_id="fixture-local",
                model_version="2026-03-15",
                local_model_path=local_model_path,
            )
        ),
    )
    selected_profile = build_profile_record(
        name="fixture-profile",
        profile_id=build_retrieval_strategy_profile_id(
            build_retrieval_strategy_profile_payload(selected_profile_config)
        ),
        config=selected_profile_config,
    )
    use_case = RecordRunConfigurationProvenanceUseCase(
        config=effective_config,
        provenance_store=store,
        selected_profile=selected_profile,
    )

    record = use_case.execute(
        RecordRunConfigurationProvenanceRequest(
            workflow_type="query.semantic",
            repository_id="repo-123",
            snapshot_id="snapshot-123",
            semantic_config_fingerprint="semantic-fingerprint-123",
        )
    )

    assert record.configuration_reuse.reuse_kind == "modified_profile_reuse"
    assert record.configuration_reuse.base_profile_id == selected_profile.profile_id
    assert record.configuration_reuse.base_profile_name == "fixture-profile"
    assert record.configuration_reuse.effective_configuration_id == record.configuration_id
    assert record.configuration_id != selected_profile.profile_id
