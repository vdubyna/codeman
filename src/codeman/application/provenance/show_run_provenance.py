"""Load one persisted run configuration provenance record."""

from __future__ import annotations

from dataclasses import dataclass

from codeman.application.ports.run_provenance_store_port import RunProvenanceStorePort
from codeman.config.provenance_errors import RunConfigurationProvenanceNotFoundError
from codeman.contracts.configuration import (
    ShowRunConfigurationProvenanceRequest,
    ShowRunConfigurationProvenanceResult,
)


@dataclass(slots=True)
class ShowRunConfigurationProvenanceUseCase:
    """Show one stored run-provenance record by run id."""

    provenance_store: RunProvenanceStorePort

    def execute(
        self,
        request: ShowRunConfigurationProvenanceRequest,
    ) -> ShowRunConfigurationProvenanceResult:
        """Return the stored provenance record for the requested run id."""

        record = self.provenance_store.get_by_run_id(request.run_id)
        if record is None:
            raise RunConfigurationProvenanceNotFoundError(
                f"Run provenance record was not found: {request.run_id}",
                details={"run_id": request.run_id},
            )
        return ShowRunConfigurationProvenanceResult(provenance=record)
