"""Embedding-provider configuration models and safe operator payload helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

LOCAL_HASH_PROVIDER_ID = "local-hash"
PROVIDER_ID_TO_FIELD_NAME = {
    LOCAL_HASH_PROVIDER_ID: "local_hash",
}
SECRET_PROVIDER_FIELD_NAMES = frozenset({"api_key"})


class EmbeddingProviderConfig(BaseModel):
    """Provider-owned configuration kept separate from semantic workflow selection."""

    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(default="hash-embedding")
    model_version: str = Field(default="1")
    local_model_path: Path | None = Field(default=None)
    api_key: SecretStr | None = Field(default=None)

    @field_validator("local_model_path", mode="before")
    @classmethod
    def _resolve_local_model_path(cls, value: Path | str | None) -> Path | None:
        if value in (None, ""):
            return None
        return Path(value).expanduser().resolve()

    @field_validator("api_key", mode="before")
    @classmethod
    def _normalize_api_key(cls, value: SecretStr | str | None) -> SecretStr | None:
        if value in (None, ""):
            return None
        if isinstance(value, SecretStr):
            return value
        return SecretStr(value)

    def to_operator_payload(self) -> dict[str, Any]:
        """Return a secret-safe representation suitable for CLI inspection."""

        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "local_model_path": (
                str(self.local_model_path) if self.local_model_path is not None else None
            ),
            "api_key_configured": self.api_key is not None,
        }


class EmbeddingProvidersConfig(BaseModel):
    """All configured embedding providers keyed by the provider registry id."""

    model_config = ConfigDict(extra="forbid")

    local_hash: EmbeddingProviderConfig = Field(default_factory=EmbeddingProviderConfig)

    def get_provider_config(self, provider_id: str | None) -> EmbeddingProviderConfig | None:
        """Return the configured provider block for the selected provider id."""

        if provider_id in (None, ""):
            return None

        field_name = PROVIDER_ID_TO_FIELD_NAME.get(provider_id)
        if field_name is None:
            return None
        return getattr(self, field_name)

    def to_operator_payload(self) -> dict[str, dict[str, Any]]:
        """Return a secret-safe representation of every provider config."""

        return {
            "local_hash": self.local_hash.to_operator_payload(),
        }


__all__ = [
    "EmbeddingProviderConfig",
    "EmbeddingProvidersConfig",
    "LOCAL_HASH_PROVIDER_ID",
    "PROVIDER_ID_TO_FIELD_NAME",
    "SECRET_PROVIDER_FIELD_NAMES",
]
