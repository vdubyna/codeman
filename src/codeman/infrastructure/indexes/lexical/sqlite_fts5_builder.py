"""SQLite FTS5 lexical-index builder."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Sequence

from codeman.application.ports.lexical_index_port import LexicalIndexPort
from codeman.contracts.retrieval import (
    LexicalIndexArtifact,
    LexicalIndexDocument,
)
from codeman.runtime import RuntimePaths, provision_runtime_paths

LEXICAL_ENGINE_ID = "sqlite-fts5"
TOKENIZER_SPEC = "unicode61 remove_diacritics 0 tokenchars '_'"
INDEXED_FIELDS = ("content", "relative_path")


def _ordered_documents(
    documents: Sequence[LexicalIndexDocument],
) -> list[LexicalIndexDocument]:
    return sorted(
        documents,
        key=lambda document: (
            document.relative_path,
            document.chunk_id,
        ),
    )


@dataclass(slots=True)
class SqliteFts5LexicalIndexBuilder(LexicalIndexPort):
    """Build a snapshot-scoped SQLite FTS5 lexical index."""

    runtime_paths: RuntimePaths

    def build(
        self,
        *,
        repository_id: str,
        snapshot_id: str,
        documents: Sequence[LexicalIndexDocument],
    ) -> LexicalIndexArtifact:
        """Persist a lexical index database atomically under `.codeman/indexes/`."""

        provision_runtime_paths(self.runtime_paths)
        final_path = (
            self.runtime_paths.indexes
            / "lexical"
            / repository_id
            / snapshot_id
            / "lexical.sqlite3"
        )
        final_path.parent.mkdir(parents=True, exist_ok=True)
        refreshed_existing_artifact = final_path.exists()

        temp_path = self._allocate_temp_path()
        try:
            self._write_database(temp_path, _ordered_documents(documents))
            temp_path.replace(final_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

        return LexicalIndexArtifact(
            lexical_engine=LEXICAL_ENGINE_ID,
            tokenizer_spec=TOKENIZER_SPEC,
            indexed_fields=list(INDEXED_FIELDS),
            chunks_indexed=len(documents),
            index_path=final_path,
            refreshed_existing_artifact=refreshed_existing_artifact,
        )

    def _allocate_temp_path(self) -> Path:
        with NamedTemporaryFile(
            dir=self.runtime_paths.tmp,
            prefix="lexical-",
            suffix=".sqlite3",
            delete=False,
        ) as handle:
            return Path(handle.name)

    @staticmethod
    def _write_database(
        database_path: Path,
        documents: Sequence[LexicalIndexDocument],
    ) -> None:
        connection = sqlite3.connect(database_path)
        try:
            connection.execute(
                """
                CREATE VIRTUAL TABLE lexical_chunks USING fts5(
                    content,
                    relative_path,
                    chunk_id UNINDEXED,
                    snapshot_id UNINDEXED,
                    repository_id UNINDEXED,
                    language UNINDEXED,
                    strategy UNINDEXED,
                    tokenize = "unicode61 remove_diacritics 0 tokenchars '_'"
                )
                """
            )
            connection.executemany(
                """
                INSERT INTO lexical_chunks (
                    content,
                    relative_path,
                    chunk_id,
                    snapshot_id,
                    repository_id,
                    language,
                    strategy
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        document.content,
                        document.relative_path,
                        document.chunk_id,
                        document.snapshot_id,
                        document.repository_id,
                        document.language,
                        document.strategy,
                    )
                    for document in documents
                ],
            )
            connection.commit()
        finally:
            connection.close()
