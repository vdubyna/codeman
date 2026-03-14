"""Ports for source inventory extraction and persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, Sequence

from codeman.contracts.repository import SourceFileRecord


@dataclass(frozen=True, slots=True)
class ScanSourceFilesResult:
    """In-memory result produced by a concrete repository scanner."""

    source_files: tuple[SourceFileRecord, ...]
    skipped_by_reason: dict[str, int]


class SourceScannerPort(Protocol):
    """Boundary for filesystem-backed source discovery implementations."""

    def scan(
        self,
        *,
        repository_path: Path,
        snapshot_id: str,
        repository_id: str,
        discovered_at: datetime,
    ) -> ScanSourceFilesResult:
        """Discover supported source files for a repository path."""


class SourceInventoryStorePort(Protocol):
    """Persistence boundary for source-file metadata inventory rows."""

    def initialize(self) -> None:
        """Prepare source inventory persistence for use."""

    def upsert_source_files(
        self,
        source_files: Sequence[SourceFileRecord],
    ) -> list[SourceFileRecord]:
        """Persist source-file rows without duplicating the same snapshot/path pair."""
