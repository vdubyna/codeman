"""Helpers for materializing snapshot-local chunk artifacts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

from codeman.application.ports.artifact_store_port import ArtifactStorePort
from codeman.application.ports.chunker_port import ChunkDraft, ChunkerRegistryPort
from codeman.application.ports.parser_port import ParserFailure, ParserRegistryPort
from codeman.config.indexing import CHUNK_SERIALIZATION_VERSION
from codeman.contracts.chunking import (
    ChunkFileDiagnostic,
    ChunkPayloadDocument,
    ChunkRecord,
)
from codeman.contracts.repository import SourceFileRecord


def build_chunk_id(
    *,
    source_file_id: str,
    strategy: str,
    start_line: int,
    end_line: int,
    start_byte: int,
    end_byte: int,
    serialization_version: str = CHUNK_SERIALIZATION_VERSION,
) -> str:
    """Build a deterministic identifier for a chunk span."""

    payload = ":".join(
        [
            source_file_id,
            strategy,
            str(start_line),
            str(end_line),
            str(start_byte),
            str(end_byte),
            serialization_version,
        ],
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class ChunkMaterializer:
    """Generate or clone chunk artifacts into a target snapshot namespace."""

    parser_registry: ParserRegistryPort
    chunker_registry: ChunkerRegistryPort
    artifact_store: ArtifactStorePort

    def build_for_source_file(
        self,
        *,
        source_file: SourceFileRecord,
        repository_path: Path,
        created_at: datetime,
    ) -> tuple[list[ChunkRecord], ChunkFileDiagnostic]:
        """Generate chunk records and one per-file diagnostic."""

        source_text = self.read_source_text(
            repository_path=repository_path,
            relative_path=source_file.relative_path,
        )
        parser = self.parser_registry.get(source_file.language)
        structural_chunker = self.chunker_registry.get_structural(source_file.language)
        fallback_chunker = self.chunker_registry.get_fallback(source_file.language)
        preferred_strategy = (
            structural_chunker.strategy_name
            if structural_chunker is not None
            else fallback_chunker.strategy_name
        )
        reason: str | None = None
        message: str | None = None

        try:
            if parser is None or structural_chunker is None:
                raise ParserFailure(
                    "No preferred structural parser is registered for: "
                    f"{source_file.relative_path}",
                )

            drafts = structural_chunker.chunk(
                source_text=source_text,
                relative_path=source_file.relative_path,
                boundaries=parser.parse(
                    source_text=source_text,
                    relative_path=source_file.relative_path,
                ),
            )
            if not drafts:
                raise ParserFailure(
                    f"No structural boundaries detected for: {source_file.relative_path}",
                )
            mode = "structural"
            strategy_used = structural_chunker.strategy_name
        except Exception as exc:
            drafts = fallback_chunker.chunk(
                source_text=source_text,
                relative_path=source_file.relative_path,
            )
            mode = "fallback"
            strategy_used = fallback_chunker.strategy_name
            reason = "preferred_path_unavailable"
            message = str(exc)

        chunk_records = self._persist_chunk_payloads(
            source_file=source_file,
            drafts=drafts,
            created_at=created_at,
        )
        diagnostic = ChunkFileDiagnostic(
            source_file_id=source_file.source_file_id,
            relative_path=source_file.relative_path,
            language=source_file.language,
            preferred_strategy=preferred_strategy,
            strategy_used=strategy_used,
            mode=mode,
            chunk_count=len(chunk_records),
            reason=reason,
            message=message,
        )
        return chunk_records, diagnostic

    def clone_for_source_file(
        self,
        *,
        source_file: SourceFileRecord,
        baseline_chunks: Sequence[ChunkRecord],
        created_at: datetime,
    ) -> list[ChunkRecord]:
        """Re-materialize previously generated chunks into a new snapshot namespace."""

        records: list[ChunkRecord] = []
        for baseline_chunk in sorted(
            baseline_chunks,
            key=lambda item: (
                item.relative_path,
                item.start_line,
                item.start_byte,
                item.end_line,
                item.end_byte,
                item.strategy,
            ),
        ):
            payload = self.artifact_store.read_chunk_payload(baseline_chunk.payload_path)
            chunk_id = build_chunk_id(
                source_file_id=source_file.source_file_id,
                strategy=baseline_chunk.strategy,
                start_line=baseline_chunk.start_line,
                end_line=baseline_chunk.end_line,
                start_byte=baseline_chunk.start_byte,
                end_byte=baseline_chunk.end_byte,
                serialization_version=baseline_chunk.serialization_version,
            )
            cloned_payload = payload.model_copy(
                update={
                    "chunk_id": chunk_id,
                    "snapshot_id": source_file.snapshot_id,
                    "repository_id": source_file.repository_id,
                    "source_file_id": source_file.source_file_id,
                    "relative_path": source_file.relative_path,
                    "language": source_file.language,
                    "source_content_hash": source_file.content_hash,
                    "serialization_version": baseline_chunk.serialization_version,
                }
            )
            payload_path = self.artifact_store.write_chunk_payload(
                cloned_payload,
                snapshot_id=source_file.snapshot_id,
            )
            records.append(
                ChunkRecord(
                    chunk_id=chunk_id,
                    snapshot_id=source_file.snapshot_id,
                    repository_id=source_file.repository_id,
                    source_file_id=source_file.source_file_id,
                    relative_path=source_file.relative_path,
                    language=source_file.language,
                    strategy=baseline_chunk.strategy,
                    serialization_version=baseline_chunk.serialization_version,
                    source_content_hash=source_file.content_hash,
                    start_line=baseline_chunk.start_line,
                    end_line=baseline_chunk.end_line,
                    start_byte=baseline_chunk.start_byte,
                    end_byte=baseline_chunk.end_byte,
                    payload_path=payload_path,
                    created_at=created_at,
                ),
            )

        return records

    def _persist_chunk_payloads(
        self,
        *,
        source_file: SourceFileRecord,
        drafts: Sequence[ChunkDraft],
        created_at: datetime,
    ) -> list[ChunkRecord]:
        """Write payload artifacts and convert drafts into persisted records."""

        records: list[ChunkRecord] = []
        for draft in sorted(
            drafts,
            key=lambda item: (
                item.start_line,
                item.start_byte,
                item.end_line,
                item.end_byte,
                item.strategy,
            ),
        ):
            chunk_id = build_chunk_id(
                source_file_id=source_file.source_file_id,
                strategy=draft.strategy,
                start_line=draft.start_line,
                end_line=draft.end_line,
                start_byte=draft.start_byte,
                end_byte=draft.end_byte,
            )
            payload = ChunkPayloadDocument(
                chunk_id=chunk_id,
                snapshot_id=source_file.snapshot_id,
                repository_id=source_file.repository_id,
                source_file_id=source_file.source_file_id,
                relative_path=source_file.relative_path,
                language=source_file.language,
                strategy=draft.strategy,
                serialization_version=CHUNK_SERIALIZATION_VERSION,
                source_content_hash=source_file.content_hash,
                start_line=draft.start_line,
                end_line=draft.end_line,
                start_byte=draft.start_byte,
                end_byte=draft.end_byte,
                content=draft.content,
            )
            payload_path = self.artifact_store.write_chunk_payload(
                payload,
                snapshot_id=source_file.snapshot_id,
            )
            records.append(
                ChunkRecord(
                    chunk_id=chunk_id,
                    snapshot_id=source_file.snapshot_id,
                    repository_id=source_file.repository_id,
                    source_file_id=source_file.source_file_id,
                    relative_path=source_file.relative_path,
                    language=source_file.language,
                    strategy=draft.strategy,
                    serialization_version=CHUNK_SERIALIZATION_VERSION,
                    source_content_hash=source_file.content_hash,
                    start_line=draft.start_line,
                    end_line=draft.end_line,
                    start_byte=draft.start_byte,
                    end_byte=draft.end_byte,
                    payload_path=payload_path,
                    created_at=created_at,
                ),
            )

        return records

    @staticmethod
    def read_source_text(*, repository_path: Path, relative_path: str) -> str:
        """Load a source file body as text for chunk generation."""

        file_path = repository_path / relative_path
        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return file_path.read_text(encoding="utf-8", errors="replace")
