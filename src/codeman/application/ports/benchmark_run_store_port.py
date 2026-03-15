"""Persistence port for benchmark execution attribution records."""

from __future__ import annotations

from typing import Protocol

from codeman.contracts.evaluation import BenchmarkRunRecord


class BenchmarkRunStorePort(Protocol):
    """Persistence boundary for benchmark execution lifecycle records."""

    def initialize(self) -> None:
        """Prepare benchmark-run persistence for use."""

    def create_run(self, record: BenchmarkRunRecord) -> BenchmarkRunRecord:
        """Persist one newly-started benchmark run record."""

    def update_run(self, record: BenchmarkRunRecord) -> BenchmarkRunRecord:
        """Persist the latest lifecycle state for an existing benchmark run."""

    def get_by_run_id(self, run_id: str) -> BenchmarkRunRecord | None:
        """Return one benchmark run record by run id, if present."""

    def list_by_repository_id(self, repository_id: str) -> list[BenchmarkRunRecord]:
        """Return repository-scoped benchmark runs in deterministic order."""
