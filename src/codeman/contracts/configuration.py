"""Configuration and retrieval-profile contract DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codeman.config.retrieval_profiles import (
    RetrievalStrategyProfilePayload,
    normalize_retrieval_profile_selector,
)


class RetrievalStrategyProfileRecord(BaseModel):
    """Persisted retrieval-strategy profile record."""

    model_config = ConfigDict(extra="forbid")

    name: str
    profile_id: str
    payload: RetrievalStrategyProfilePayload
    provider_id: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    vector_engine: str
    vector_dimension: int
    created_at: datetime


class SelectedRetrievalStrategyProfile(BaseModel):
    """Resolved retrieval-profile selection metadata for operator-facing surfaces."""

    model_config = ConfigDict(extra="forbid")

    selector: str
    name: str
    profile_id: str


class SaveRetrievalStrategyProfileRequest(BaseModel):
    """Input DTO for saving the current retrieval settings as a named profile."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: str | None) -> str:
        return normalize_retrieval_profile_selector(value, field_name="name")


class SaveRetrievalStrategyProfileResult(BaseModel):
    """Output DTO for save-profile execution."""

    model_config = ConfigDict(extra="forbid")

    profile: RetrievalStrategyProfileRecord
    created: bool


class ListRetrievalStrategyProfilesResult(BaseModel):
    """Output DTO for listing saved retrieval profiles."""

    model_config = ConfigDict(extra="forbid")

    profiles: list[RetrievalStrategyProfileRecord] = Field(default_factory=list)


class ShowRetrievalStrategyProfileRequest(BaseModel):
    """Input DTO for showing one saved retrieval profile."""

    model_config = ConfigDict(extra="forbid")

    selector: str = Field(min_length=1)

    @field_validator("selector", mode="before")
    @classmethod
    def _normalize_selector(cls, value: str | None) -> str:
        return normalize_retrieval_profile_selector(value, field_name="selector")


class ShowRetrievalStrategyProfileResult(BaseModel):
    """Output DTO for profile inspection by name or id."""

    model_config = ConfigDict(extra="forbid")

    profile: RetrievalStrategyProfileRecord


ComparedRetrievalMode = Literal["lexical", "semantic", "hybrid"]
ConfigurationReuseKind = Literal["ad_hoc", "profile_reuse", "modified_profile_reuse"]
RunProvenanceWorkflowType = Literal[
    "index.build-chunks",
    "index.build-lexical",
    "index.build-semantic",
    "index.reindex",
    "query.lexical",
    "query.semantic",
    "query.hybrid",
    "compare.query_modes",
]


class ConfigurationReuseLineage(BaseModel):
    """Machine-readable selected-profile lineage for the effective configuration."""

    model_config = ConfigDict(extra="forbid")

    reuse_kind: ConfigurationReuseKind
    effective_configuration_id: str
    base_profile_id: str | None = None
    base_profile_name: str | None = None


class RunProvenanceWorkflowContext(BaseModel):
    """Workflow-specific references retained with one run provenance record."""

    model_config = ConfigDict(extra="forbid")

    previous_snapshot_id: str | None = None
    result_snapshot_id: str | None = None
    lexical_build_id: str | None = None
    semantic_build_id: str | None = None
    compared_modes: list[ComparedRetrievalMode] = Field(default_factory=list)
    max_results: int | None = None
    rank_constant: int | None = None
    rank_window_size: int | None = None
    noop: bool | None = None


class RunConfigurationProvenanceRecord(BaseModel):
    """Persisted run-level configuration provenance record."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    workflow_type: RunProvenanceWorkflowType
    repository_id: str
    snapshot_id: str | None = None
    configuration_id: str
    configuration_reuse: ConfigurationReuseLineage | None = None
    indexing_config_fingerprint: str | None = None
    semantic_config_fingerprint: str | None = None
    provider_id: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    effective_config: RetrievalStrategyProfilePayload
    workflow_context: RunProvenanceWorkflowContext = Field(
        default_factory=RunProvenanceWorkflowContext
    )
    created_at: datetime

    @model_validator(mode="after")
    def _ensure_configuration_reuse(self) -> RunConfigurationProvenanceRecord:
        if self.configuration_reuse is None:
            self.configuration_reuse = ConfigurationReuseLineage(
                reuse_kind="ad_hoc",
                effective_configuration_id=self.configuration_id,
            )
            return self

        if self.configuration_reuse.effective_configuration_id != self.configuration_id:
            raise ValueError(
                "Configuration reuse lineage must reference the effective configuration id."
            )

        return self


class RecordRunConfigurationProvenanceRequest(BaseModel):
    """Input DTO for persisting one successful workflow provenance record."""

    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    workflow_type: RunProvenanceWorkflowType
    repository_id: str
    snapshot_id: str | None = None
    indexing_config_fingerprint: str | None = None
    semantic_config_fingerprint: str | None = None
    provider_id: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    workflow_context: RunProvenanceWorkflowContext = Field(
        default_factory=RunProvenanceWorkflowContext
    )

    @field_validator("run_id", mode="before")
    @classmethod
    def _normalize_run_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ShowRunConfigurationProvenanceRequest(BaseModel):
    """Input DTO for looking up one stored run provenance record."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)

    @field_validator("run_id", mode="before")
    @classmethod
    def _normalize_run_id(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Run provenance id must not be blank.")
        normalized = value.strip()
        if not normalized:
            raise ValueError("Run provenance id must not be blank.")
        return normalized


class ShowRunConfigurationProvenanceResult(BaseModel):
    """Output DTO for one run provenance inspection command."""

    model_config = ConfigDict(extra="forbid")

    provenance: RunConfigurationProvenanceRecord
