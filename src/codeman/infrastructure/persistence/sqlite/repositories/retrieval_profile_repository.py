"""SQLite adapter for retrieval-strategy profile records."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import asc, insert, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from codeman.application.ports.retrieval_profile_store_port import (
    RetrievalStrategyProfileStorePort,
)
from codeman.config.loader import ConfigurationResolutionError
from codeman.config.profile_errors import RetrievalStrategyProfileNameConflictError
from codeman.config.retrieval_profiles import RetrievalStrategyProfilePayload
from codeman.contracts.configuration import RetrievalStrategyProfileRecord
from codeman.infrastructure.persistence.sqlite.migrations import upgrade_database
from codeman.infrastructure.persistence.sqlite.tables import retrieval_strategy_profiles_table


@dataclass(slots=True)
class SqliteRetrievalStrategyProfileStore(RetrievalStrategyProfileStorePort):
    """Persist retrieval-strategy profiles in the runtime SQLite database."""

    engine: Engine
    database_path: Path

    def initialize(self) -> None:
        """Ensure the runtime metadata schema is up to date."""

        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        upgrade_database(self.database_path)

    def get_by_name(self, name: str) -> RetrievalStrategyProfileRecord | None:
        """Return the saved profile for the exact name, if present."""

        if not self._profiles_table_exists():
            return None

        query = (
            select(retrieval_strategy_profiles_table)
            .where(retrieval_strategy_profiles_table.c.name == name)
            .limit(1)
        )
        with self.engine.begin() as connection:
            row = connection.execute(query).mappings().first()

        if row is None:
            return None
        return self._row_to_record(row)

    def list_by_profile_id(self, profile_id: str) -> list[RetrievalStrategyProfileRecord]:
        """Return every saved profile that matches the stable content id."""

        if not self._profiles_table_exists():
            return []

        query = (
            select(retrieval_strategy_profiles_table)
            .where(retrieval_strategy_profiles_table.c.profile_id == profile_id)
            .order_by(
                asc(retrieval_strategy_profiles_table.c.name),
                asc(retrieval_strategy_profiles_table.c.created_at),
            )
        )
        with self.engine.begin() as connection:
            rows = connection.execute(query).mappings().all()

        return [self._row_to_record(row) for row in rows]

    def list_profiles(self) -> list[RetrievalStrategyProfileRecord]:
        """Return every saved profile in deterministic order."""

        if not self._profiles_table_exists():
            return []

        query = select(retrieval_strategy_profiles_table).order_by(
            asc(retrieval_strategy_profiles_table.c.name),
            asc(retrieval_strategy_profiles_table.c.created_at),
            asc(retrieval_strategy_profiles_table.c.profile_id),
        )
        with self.engine.begin() as connection:
            rows = connection.execute(query).mappings().all()

        return [self._row_to_record(row) for row in rows]

    def create_profile(
        self, profile: RetrievalStrategyProfileRecord
    ) -> RetrievalStrategyProfileRecord:
        """Persist one retrieval-profile record."""

        statement = insert(retrieval_strategy_profiles_table).values(
            name=profile.name,
            profile_id=profile.profile_id,
            payload_json=profile.payload.model_dump_json(),
            provider_id=profile.provider_id,
            model_id=profile.model_id,
            model_version=profile.model_version,
            vector_engine=profile.vector_engine,
            vector_dimension=profile.vector_dimension,
            created_at=profile.created_at,
        )

        try:
            with self.engine.begin() as connection:
                connection.execute(statement)
        except IntegrityError as exc:
            raise RetrievalStrategyProfileNameConflictError(
                f"Retrieval strategy profile name already exists with different content: "
                f"{profile.name}",
                details={"selector": profile.name},
            ) from exc

        return profile

    def _profiles_table_exists(self) -> bool:
        """Return whether the runtime database already exposes the profile table."""

        if not self.database_path.exists():
            return False
        return inspect(self.engine).has_table(retrieval_strategy_profiles_table.name)

    @staticmethod
    def _row_to_record(row: Any) -> RetrievalStrategyProfileRecord:
        """Convert a row mapping into a retrieval-profile DTO."""

        try:
            payload = RetrievalStrategyProfilePayload.model_validate(
                json.loads(row["payload_json"])
            )
        except (TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise ConfigurationResolutionError(
                f"Persisted retrieval strategy profile is invalid: {row['name']}",
                details={"selector": row["name"]},
            ) from exc

        return RetrievalStrategyProfileRecord(
            name=row["name"],
            profile_id=row["profile_id"],
            payload=payload,
            provider_id=row["provider_id"],
            model_id=row["model_id"],
            model_version=row["model_version"],
            vector_engine=row["vector_engine"],
            vector_dimension=row["vector_dimension"],
            created_at=row["created_at"],
        )
