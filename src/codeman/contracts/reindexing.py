"""Re-index request, result, and persistence contract DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from codeman.contracts.repository import RepositoryRecord

ChangeReason = Literal[
    "no_change",
    "source_changed",
    "config_changed",
    "source_and_config_changed",
]


class ReindexRepositoryRequest(BaseModel):
    """Input DTO for repository re-index operations."""

    model_config = ConfigDict(extra="forbid")

    repository_id: str


class ReindexDiagnostics(BaseModel):
    """Summary diagnostics safe for CLI and JSON output."""

    model_config = ConfigDict(extra="forbid")

    source_files_scanned: int = 0
    source_files_skipped: int = 0
    source_files_unchanged: int = 0
    source_files_added: int = 0
    source_files_changed: int = 0
    source_files_reused: int = 0
    source_files_rebuilt: int = 0
    source_files_removed: int = 0
    source_files_newly_unsupported: int = 0
    source_files_invalidated_by_config: int = 0
    chunks_reused: int = 0
    chunks_rebuilt: int = 0
    chunks_removed: int = 0
    chunks_invalidated_by_config: int = 0


class ReindexRunRecord(BaseModel):
    """Persisted attribution record for a re-index run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    repository_id: str
    previous_snapshot_id: str
    result_snapshot_id: str
    previous_revision_identity: str
    result_revision_identity: str
    previous_config_fingerprint: str
    current_config_fingerprint: str
    change_reason: ChangeReason
    source_files_reused: int
    source_files_rebuilt: int
    source_files_removed: int
    chunks_reused: int
    chunks_rebuilt: int
    created_at: datetime


class ReindexRepositoryResult(BaseModel):
    """Output DTO for successful repository re-index operations."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    repository: RepositoryRecord
    previous_snapshot_id: str
    result_snapshot_id: str
    change_reason: ChangeReason
    previous_revision_identity: str
    result_revision_identity: str
    previous_config_fingerprint: str
    current_config_fingerprint: str
    source_files_reused: int
    source_files_rebuilt: int
    source_files_removed: int
    chunks_reused: int
    chunks_rebuilt: int
    noop: bool
    diagnostics: ReindexDiagnostics
