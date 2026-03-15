"""Persistence port for run-configuration provenance records."""

from __future__ import annotations

from typing import Protocol

from codeman.contracts.configuration import RunConfigurationProvenanceRecord


class RunProvenanceStorePort(Protocol):
    """Persistence boundary for workspace-local run provenance records."""

    def initialize(self) -> None:
        """Prepare the run-provenance store for writes."""

    def create_record(
        self, record: RunConfigurationProvenanceRecord
    ) -> RunConfigurationProvenanceRecord:
        """Persist one run provenance record."""

    def get_by_run_id(self, run_id: str) -> RunConfigurationProvenanceRecord | None:
        """Return one run provenance record by run id, if present."""

    def list_by_repository_id(self, repository_id: str) -> list[RunConfigurationProvenanceRecord]:
        """Return repository-scoped run provenance records in deterministic order."""
