"""Repository registration contract DTOs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

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


class CreateSnapshotRequest(BaseModel):
    """Input DTO for snapshot creation."""

    model_config = ConfigDict(extra="forbid")

    repository_id: str


class SnapshotRecord(BaseModel):
    """Metadata persisted for a repository snapshot."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    repository_id: str
    revision_identity: str
    revision_source: Literal["git", "filesystem_fingerprint"]
    manifest_path: Path
    created_at: datetime


class SnapshotManifestDocument(BaseModel):
    """Machine-readable manifest stored for an immutable repository snapshot."""

    model_config = ConfigDict(extra="forbid")

    manifest_version: str = "1"
    snapshot_id: str
    repository_id: str
    repository_name: str
    canonical_path: Path
    created_at: datetime
    revision_identity: str
    revision_source: Literal["git", "filesystem_fingerprint"]


class CreateSnapshotResult(BaseModel):
    """Output DTO for successful snapshot creation."""

    model_config = ConfigDict(extra="forbid")

    repository: RepositoryRecord
    snapshot: SnapshotRecord
