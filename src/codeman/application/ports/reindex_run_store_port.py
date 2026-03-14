"""Persistence port for attributed re-index runs."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from codeman.contracts.reindexing import ChangeReason, ReindexRunRecord


class ReindexRunStorePort(Protocol):
    """Persistence boundary for re-index attribution runs."""

    def initialize(self) -> None:
        """Prepare re-index run persistence for use."""

    def create_run(
        self,
        *,
        repository_id: str,
        previous_snapshot_id: str,
        result_snapshot_id: str,
        previous_revision_identity: str,
        result_revision_identity: str,
        previous_config_fingerprint: str,
        current_config_fingerprint: str,
        change_reason: ChangeReason,
        source_files_reused: int,
        source_files_rebuilt: int,
        source_files_removed: int,
        chunks_reused: int,
        chunks_rebuilt: int,
        created_at: datetime,
    ) -> ReindexRunRecord:
        """Persist one attributable re-index run record."""
