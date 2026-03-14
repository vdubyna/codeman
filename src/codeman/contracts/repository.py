"""Repository registration contract DTOs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class RegisterRepositoryRequest(BaseModel):
    """Input DTO for repository registration."""

    model_config = ConfigDict(extra="forbid")

    repository_path: Path


class RepositoryRecord(BaseModel):
    """Metadata persisted for a registered repository."""

    model_config = ConfigDict(extra="forbid")

    repository_id: str
    repository_name: str
    canonical_path: Path
    requested_path: Path
    created_at: datetime
    updated_at: datetime


class RegisterRepositoryResult(BaseModel):
    """Output DTO for successful repository registration."""

    model_config = ConfigDict(extra="forbid")

    repository: RepositoryRecord
    runtime_root: Path
    metadata_database_path: Path
