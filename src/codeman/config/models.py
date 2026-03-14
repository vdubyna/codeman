"""Configuration model placeholders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codeman.config.embedding_providers import EmbeddingProvidersConfig
from codeman.config.indexing import IndexingConfig
from codeman.config.semantic_indexing import SemanticIndexingConfig


class RuntimeConfig(BaseModel):
    """Runtime path configuration."""

    model_config = ConfigDict(extra="forbid")

    workspace_root: Path = Field(default_factory=lambda: Path.cwd().resolve())
    root_dir_name: str = Field(default=".codeman", min_length=1)
    metadata_database_name: str = Field(default="metadata.sqlite3", min_length=1)

    @field_validator("workspace_root", mode="before")
    @classmethod
    def _resolve_workspace_root(cls, value: Path | str | None) -> Path:
        if value is None:
            return Path.cwd().resolve()
        return Path(value).expanduser().resolve()


class AppConfig(BaseModel):
    """Top-level application configuration placeholder."""

    model_config = ConfigDict(extra="forbid")

    project_name: str = "codeman"
    default_output_format: str = "text"
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
    semantic_indexing: SemanticIndexingConfig = Field(default_factory=SemanticIndexingConfig)
    embedding_providers: EmbeddingProvidersConfig = Field(default_factory=EmbeddingProvidersConfig)

    def _semantic_operator_payload(self) -> dict[str, Any]:
        semantic_payload = self.semantic_indexing.model_dump(mode="json")
        compatibility_provider = (
            self.embedding_providers.get_provider_config(self.semantic_indexing.provider_id)
            or self.embedding_providers.local_hash
        )
        semantic_payload["model_id"] = compatibility_provider.model_id
        semantic_payload["model_version"] = compatibility_provider.model_version
        semantic_payload["local_model_path"] = (
            str(compatibility_provider.local_model_path)
            if compatibility_provider.local_model_path is not None
            else None
        )
        return semantic_payload

    def to_operator_payload(self) -> dict[str, Any]:
        """Return a secret-safe payload for CLI inspection surfaces."""

        return {
            "project_name": self.project_name,
            "default_output_format": self.default_output_format,
            "runtime": self.runtime.model_dump(mode="json"),
            "indexing": self.indexing.model_dump(mode="json"),
            "semantic_indexing": self._semantic_operator_payload(),
            "embedding_providers": self.embedding_providers.to_operator_payload(),
        }
