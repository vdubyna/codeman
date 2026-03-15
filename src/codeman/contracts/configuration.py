"""Configuration and retrieval-profile contract DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
