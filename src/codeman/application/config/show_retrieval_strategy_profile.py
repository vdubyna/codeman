"""Inspect one saved retrieval strategy profile."""

from __future__ import annotations

from dataclasses import dataclass

from codeman.application.config.retrieval_profile_selection import (
    resolve_retrieval_strategy_profile_selector,
)
from codeman.application.ports.retrieval_profile_store_port import (
    RetrievalStrategyProfileStorePort,
)
from codeman.contracts.configuration import (
    ShowRetrievalStrategyProfileRequest,
    ShowRetrievalStrategyProfileResult,
)


@dataclass(slots=True)
class ShowRetrievalStrategyProfileUseCase:
    """Resolve and return one saved retrieval strategy profile."""

    profile_store: RetrievalStrategyProfileStorePort

    def execute(
        self, request: ShowRetrievalStrategyProfileRequest
    ) -> ShowRetrievalStrategyProfileResult:
        """Return the profile that matches the supplied selector."""

        profile = resolve_retrieval_strategy_profile_selector(
            self.profile_store,
            request.selector,
        )
        return ShowRetrievalStrategyProfileResult(profile=profile)
