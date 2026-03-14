"""Configuration model placeholders."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
