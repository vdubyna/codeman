"""Helpers for classifying selected-profile reuse against the effective config."""

from __future__ import annotations

from codeman.config.provenance import build_effective_config_provenance_id
from codeman.config.retrieval_profiles import RetrievalStrategyProfilePayload
from codeman.contracts.configuration import (
    ConfigurationReuseLineage,
    RetrievalStrategyProfileRecord,
)


def build_configuration_reuse_lineage(
    *,
    selected_profile: RetrievalStrategyProfileRecord | None,
    effective_config: RetrievalStrategyProfilePayload,
) -> ConfigurationReuseLineage:
    """Classify whether the current config is ad hoc, exact profile reuse, or modified reuse."""

    effective_configuration_id = build_effective_config_provenance_id(effective_config)
    if selected_profile is None:
        return ConfigurationReuseLineage(
            reuse_kind="ad_hoc",
            effective_configuration_id=effective_configuration_id,
        )

    reuse_kind = "profile_reuse"
    if selected_profile.profile_id != effective_configuration_id:
        reuse_kind = "modified_profile_reuse"

    return ConfigurationReuseLineage(
        reuse_kind=reuse_kind,
        effective_configuration_id=effective_configuration_id,
        base_profile_id=selected_profile.profile_id,
        base_profile_name=selected_profile.name,
    )


__all__ = ["build_configuration_reuse_lineage"]
