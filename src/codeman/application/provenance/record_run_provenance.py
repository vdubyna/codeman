"""Persist secret-safe configuration provenance for successful workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from codeman.application.ports.run_provenance_store_port import RunProvenanceStorePort
from codeman.config.models import AppConfig
from codeman.config.provenance import (
    build_effective_config_provenance_id,
    build_effective_config_provenance_payload,
)
from codeman.contracts.configuration import (
    RecordRunConfigurationProvenanceRequest,
    RunConfigurationProvenanceRecord,
)


@dataclass(slots=True)
class RecordRunConfigurationProvenanceUseCase:
    """Persist the effective configuration and workflow context for one successful run."""

    config: AppConfig
    provenance_store: RunProvenanceStorePort

    def execute(
        self,
        request: RecordRunConfigurationProvenanceRequest,
    ) -> RunConfigurationProvenanceRecord:
        """Persist one run-provenance record and return the stored DTO."""

        self.provenance_store.initialize()
        effective_config = build_effective_config_provenance_payload(self.config)
        record = RunConfigurationProvenanceRecord(
            run_id=request.run_id or uuid4().hex,
            workflow_type=request.workflow_type,
            repository_id=request.repository_id,
            snapshot_id=request.snapshot_id,
            configuration_id=build_effective_config_provenance_id(effective_config),
            indexing_config_fingerprint=request.indexing_config_fingerprint,
            semantic_config_fingerprint=request.semantic_config_fingerprint,
            provider_id=request.provider_id,
            model_id=request.model_id,
            model_version=request.model_version,
            effective_config=effective_config,
            workflow_context=request.workflow_context,
            created_at=datetime.now(UTC),
        )
        return self.provenance_store.create_record(record)
