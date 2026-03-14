"""SQLite adapter for repository registration metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from codeman.application.ports.metadata_store_port import RepositoryMetadataStorePort
from codeman.application.repo.register_repository import RepositoryAlreadyRegisteredError
from codeman.contracts.repository import RepositoryRecord
from codeman.infrastructure.persistence.sqlite.migrations import upgrade_database
from codeman.infrastructure.persistence.sqlite.tables import repositories_table


@dataclass(slots=True)
class SqliteRepositoryMetadataStore(RepositoryMetadataStorePort):
    """Persist repository metadata in a SQLite database."""

    engine: Engine
    database_path: Path

    def initialize(self) -> None:
        """Ensure the runtime metadata schema is up to date."""

        upgrade_database(self.database_path)

    def get_by_repository_id(self, repository_id: str) -> RepositoryRecord | None:
        """Look up a repository by its persisted identifier."""

        if not self.database_path.exists():
            return None

        query = select(repositories_table).where(repositories_table.c.id == repository_id)
        with self.engine.begin() as connection:
            row = connection.execute(query).mappings().first()

        if row is None:
            return None

        return self._row_to_record(row)

    def get_by_canonical_path(self, canonical_path: Path) -> RepositoryRecord | None:
        """Look up a repository by its canonical path."""

        if not self.database_path.exists():
            return None

        query = select(repositories_table).where(
            repositories_table.c.canonical_path == str(canonical_path),
        )
        with self.engine.begin() as connection:
            row = connection.execute(query).mappings().first()

        if row is None:
            return None

        return self._row_to_record(row)

    def create_repository(
        self,
        *,
        repository_name: str,
        canonical_path: Path,
        requested_path: Path,
    ) -> RepositoryRecord:
        """Persist a new repository registration."""

        now = datetime.now(UTC)
        repository_id = uuid4().hex
        statement = insert(repositories_table).values(
            id=repository_id,
            repository_name=repository_name,
            canonical_path=str(canonical_path),
            requested_path=str(requested_path),
            created_at=now,
            updated_at=now,
        )

        try:
            with self.engine.begin() as connection:
                connection.execute(statement)
        except IntegrityError as exc:
            raise RepositoryAlreadyRegisteredError(
                f"Repository is already registered: {canonical_path}",
            ) from exc

        return RepositoryRecord(
            repository_id=repository_id,
            repository_name=repository_name,
            canonical_path=canonical_path,
            requested_path=requested_path,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _row_to_record(row: Any) -> RepositoryRecord:
        """Convert a SQLAlchemy row mapping into a contract DTO."""

        return RepositoryRecord(
            repository_id=row["id"],
            repository_name=row["repository_name"],
            canonical_path=Path(row["canonical_path"]),
            requested_path=Path(row["requested_path"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
