"""Save the current retrieval strategy as a reusable profile."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from codeman.application.ports.retrieval_profile_store_port import (
    RetrievalStrategyProfileStorePort,
)
from codeman.config.loader import ConfigurationResolutionError
from codeman.config.models import AppConfig
from codeman.config.profile_errors import RetrievalStrategyProfileNameConflictError
from codeman.config.retrieval_profiles import (
    build_retrieval_strategy_profile_id,
    build_retrieval_strategy_profile_payload,
)
from codeman.contracts.configuration import (
    RetrievalStrategyProfileRecord,
    SaveRetrievalStrategyProfileRequest,
    SaveRetrievalStrategyProfileResult,
)


@dataclass(slots=True)
class SaveRetrievalStrategyProfileUseCase:
    """Persist the current retrieval-affecting settings as a named profile."""

    config: AppConfig
    profile_store: RetrievalStrategyProfileStorePort

    def execute(
        self, request: SaveRetrievalStrategyProfileRequest
    ) -> SaveRetrievalStrategyProfileResult:
        """Save the current config as a named retrieval strategy profile."""

        self.profile_store.initialize()
        try:
            payload = build_retrieval_strategy_profile_payload(self.config)
        except ValueError as exc:
            raise ConfigurationResolutionError(str(exc)) from exc

        profile_id = build_retrieval_strategy_profile_id(payload)
        existing_profile = self.profile_store.get_by_name(request.name)
        if existing_profile is not None:
            if existing_profile.profile_id == profile_id and existing_profile.payload == payload:
                return SaveRetrievalStrategyProfileResult(
                    profile=existing_profile,
                    created=False,
                )
            raise RetrievalStrategyProfileNameConflictError(
                f"Retrieval strategy profile name already exists with different content: "
                f"{request.name}",
                details={
                    "selector": request.name,
                    "existing_profile_id": existing_profile.profile_id,
                },
            )

        selected_provider = payload.embedding_providers.get_provider_config(
            payload.semantic_indexing.provider_id
        )
        profile = RetrievalStrategyProfileRecord(
            name=request.name,
            profile_id=profile_id,
            payload=payload,
            provider_id=payload.semantic_indexing.provider_id,
            model_id=selected_provider.model_id if selected_provider is not None else None,
            model_version=(
                selected_provider.model_version if selected_provider is not None else None
            ),
            vector_engine=payload.semantic_indexing.vector_engine,
            vector_dimension=payload.semantic_indexing.vector_dimension,
            created_at=datetime.now(UTC),
        )
        persisted_profile = self.profile_store.create_profile(profile)
        return SaveRetrievalStrategyProfileResult(profile=persisted_profile, created=True)
