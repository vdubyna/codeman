"""Configuration model placeholders."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codeman.config.indexing import IndexingConfig


class RuntimeConfig(BaseModel):
    """Runtime path configuration."""

    model_config = ConfigDict(extra="forbid")

    workspace_root: Path = Field(
        default_factory=lambda: Path(
            os.environ.get("CODEMAN_WORKSPACE_ROOT", Path.cwd())
        ).resolve(),
    )
    root_dir_name: str = Field(
        default_factory=lambda: os.environ.get("CODEMAN_RUNTIME_ROOT_DIR", ".codeman"),
    )
    metadata_database_name: str = Field(
        default_factory=lambda: os.environ.get(
            "CODEMAN_METADATA_DATABASE_NAME", "metadata.sqlite3"
        ),
    )


class AppConfig(BaseModel):
    """Top-level application configuration placeholder."""

    model_config = ConfigDict(extra="forbid")

    project_name: str = "codeman"
    default_output_format: str = "text"
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
