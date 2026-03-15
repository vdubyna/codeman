"""List saved retrieval strategy profiles."""

from __future__ import annotations

from dataclasses import dataclass

from codeman.application.ports.retrieval_profile_store_port import (
    RetrievalStrategyProfileStorePort,
)
from codeman.contracts.configuration import ListRetrievalStrategyProfilesResult


@dataclass(slots=True)
class ListRetrievalStrategyProfilesUseCase:
    """List retrieval-strategy profiles saved in the current workspace."""

    profile_store: RetrievalStrategyProfileStorePort

    def execute(self) -> ListRetrievalStrategyProfilesResult:
        """Return the saved profiles in deterministic order."""

        return ListRetrievalStrategyProfilesResult(profiles=self.profile_store.list_profiles())
