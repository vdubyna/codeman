"""Helpers for materializing snapshot-local chunk artifacts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from codeman.application.ports.artifact_store_port import ArtifactStorePort
from codeman.application.ports.cache_store_port import CacheStorePort
from codeman.application.ports.chunker_port import ChunkDraft, ChunkerRegistryPort
from codeman.application.ports.parser_port import (
    ParserFailure,
    ParserRegistryPort,
    StructuralBoundary,
)
from codeman.config.cache_identity import build_chunk_cache_key, build_parser_cache_key
from codeman.config.indexing import CHUNK_SERIALIZATION_VERSION, PARSER_POLICY_VERSIONS
from codeman.contracts.cache import (
    CacheUsageSummary,
    ChunkCacheArtifactDocument,
    ChunkDraftDocument,
    ParserCacheArtifactDocument,
    StructuralBoundaryDocument,
)
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


@dataclass(frozen=True, slots=True)
class BuildSourceFileChunksResult:
    """Chunk materialization result for one source file."""

    chunk_records: list[ChunkRecord]
    diagnostic: ChunkFileDiagnostic
    cache_summary: CacheUsageSummary


def _merge_cache_summaries(*summaries: CacheUsageSummary) -> CacheUsageSummary:
    return CacheUsageSummary(
        parser_entries_reused=sum(summary.parser_entries_reused for summary in summaries),
        parser_entries_regenerated=sum(summary.parser_entries_regenerated for summary in summaries),
        chunk_entries_reused=sum(summary.chunk_entries_reused for summary in summaries),
        chunk_entries_regenerated=sum(summary.chunk_entries_regenerated for summary in summaries),
        embedding_documents_reused=sum(summary.embedding_documents_reused for summary in summaries),
        embedding_documents_regenerated=sum(
            summary.embedding_documents_regenerated for summary in summaries
        ),
    )


@dataclass(slots=True)
class ChunkMaterializer:
    """Generate or clone chunk artifacts into a target snapshot namespace."""

    parser_registry: ParserRegistryPort
    chunker_registry: ChunkerRegistryPort
    artifact_store: ArtifactStorePort
    cache_store: CacheStorePort

    def build_for_source_file(
        self,
        *,
        source_file: SourceFileRecord,
        repository_path: Path,
        created_at: datetime,
        indexing_config_fingerprint: str,
    ) -> BuildSourceFileChunksResult:
        """Generate chunk records and one per-file diagnostic."""

        chunk_cache_key = build_chunk_cache_key(
            language=source_file.language,
            relative_path=source_file.relative_path,
            source_content_hash=source_file.content_hash,
            indexing_config_fingerprint=indexing_config_fingerprint,
        )
        parser = self.parser_registry.get(source_file.language)
        structural_chunker = self.chunker_registry.get_structural(source_file.language)
        fallback_chunker = self.chunker_registry.get_fallback(source_file.language)
        preferred_strategy = (
            structural_chunker.strategy_name
            if structural_chunker is not None
            else fallback_chunker.strategy_name
        )
        cached_chunk_artifact = self._read_chunk_cache(chunk_cache_key)
        if (
            cached_chunk_artifact is not None
            and cached_chunk_artifact.mode == "structural"
            and cached_chunk_artifact.preferred_strategy == preferred_strategy
            and cached_chunk_artifact.strategy_used == preferred_strategy
        ):
            chunk_records = self._persist_chunk_payloads(
                source_file=source_file,
                drafts=self._chunk_drafts_from_documents(cached_chunk_artifact.drafts),
                created_at=created_at,
            )
            diagnostic = ChunkFileDiagnostic(
                source_file_id=source_file.source_file_id,
                relative_path=source_file.relative_path,
                language=source_file.language,
                preferred_strategy=cached_chunk_artifact.preferred_strategy,
                strategy_used=cached_chunk_artifact.strategy_used,
                mode=cached_chunk_artifact.mode,
                chunk_count=len(chunk_records),
                reason=cached_chunk_artifact.reason,
                message=cached_chunk_artifact.message,
            )
            return BuildSourceFileChunksResult(
                chunk_records=chunk_records,
                diagnostic=diagnostic,
                cache_summary=CacheUsageSummary(chunk_entries_reused=1),
            )

        source_text = self.read_source_text(
            repository_path=repository_path,
            relative_path=source_file.relative_path,
        )
        reason: str | None = None
        message: str | None = None
        parser_cache_summary = CacheUsageSummary()
        parser_cache_key: str | None = None

        try:
            if parser is None or structural_chunker is None:
                raise ParserFailure(
                    "No preferred structural parser is registered for: "
                    f"{source_file.relative_path}",
                )

            parser_policy_id = PARSER_POLICY_VERSIONS.get(source_file.language)
            if parser_policy_id is None:
                raise ParserFailure(
                    f"No parser cache policy is registered for: {source_file.relative_path}",
                )
            parser_cache_key = build_parser_cache_key(
                language=source_file.language,
                relative_path=source_file.relative_path,
                source_content_hash=source_file.content_hash,
                parser_policy_id=parser_policy_id,
            )
            boundaries, parser_cache_summary = self._load_or_parse_boundaries(
                parser_cache_key=parser_cache_key,
                parser_policy_id=parser_policy_id,
                source_file=source_file,
                parser=parser,
                source_text=source_text,
            )
            drafts = structural_chunker.chunk(
                source_text=source_text,
                relative_path=source_file.relative_path,
                boundaries=boundaries,
            )
            if not drafts:
                raise ParserFailure(
                    f"No structural boundaries detected for: {source_file.relative_path}",
                )
            mode = "structural"
            strategy_used = structural_chunker.strategy_name
        except Exception as exc:
            mode = "fallback"
            strategy_used = fallback_chunker.strategy_name
            reason = "preferred_path_unavailable"
            message = str(exc)
            if (
                cached_chunk_artifact is not None
                and cached_chunk_artifact.mode == "fallback"
                and cached_chunk_artifact.preferred_strategy == preferred_strategy
                and cached_chunk_artifact.strategy_used == strategy_used
            ):
                chunk_records = self._persist_chunk_payloads(
                    source_file=source_file,
                    drafts=self._chunk_drafts_from_documents(cached_chunk_artifact.drafts),
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
                return BuildSourceFileChunksResult(
                    chunk_records=chunk_records,
                    diagnostic=diagnostic,
                    cache_summary=_merge_cache_summaries(
                        parser_cache_summary,
                        CacheUsageSummary(chunk_entries_reused=1),
                    ),
                )

            drafts = fallback_chunker.chunk(
                source_text=source_text,
                relative_path=source_file.relative_path,
            )

        self.cache_store.write_chunk_cache(
            ChunkCacheArtifactDocument(
                cache_key=chunk_cache_key,
                parser_cache_key=parser_cache_key,
                indexing_config_fingerprint=indexing_config_fingerprint,
                language=source_file.language,
                relative_path=source_file.relative_path,
                source_content_hash=source_file.content_hash,
                preferred_strategy=preferred_strategy,
                strategy_used=strategy_used,
                mode=mode,
                reason=reason,
                message=message,
                drafts=[
                    ChunkDraftDocument(
                        strategy=draft.strategy,
                        start_line=draft.start_line,
                        end_line=draft.end_line,
                        start_byte=draft.start_byte,
                        end_byte=draft.end_byte,
                        content=draft.content,
                    )
                    for draft in drafts
                ],
            )
        )
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
        return BuildSourceFileChunksResult(
            chunk_records=chunk_records,
            diagnostic=diagnostic,
            cache_summary=_merge_cache_summaries(
                parser_cache_summary,
                CacheUsageSummary(chunk_entries_regenerated=1),
            ),
        )

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
    def _chunk_drafts_from_documents(
        drafts: Sequence[ChunkDraftDocument],
    ) -> tuple[ChunkDraft, ...]:
        return tuple(
            ChunkDraft(
                strategy=draft.strategy,
                start_line=draft.start_line,
                end_line=draft.end_line,
                start_byte=draft.start_byte,
                end_byte=draft.end_byte,
                content=draft.content,
            )
            for draft in drafts
        )

    @staticmethod
    def _boundaries_from_documents(
        boundaries: Sequence[StructuralBoundaryDocument],
    ) -> tuple[StructuralBoundary, ...]:
        return tuple(
            StructuralBoundary(
                kind=boundary.kind,
                start_line=boundary.start_line,
                label=boundary.label,
            )
            for boundary in boundaries
        )

    def _load_or_parse_boundaries(
        self,
        *,
        parser_cache_key: str,
        parser_policy_id: str,
        source_file: SourceFileRecord,
        parser: object,
        source_text: str,
    ) -> tuple[tuple[StructuralBoundary, ...], CacheUsageSummary]:
        cached_parser_artifact = self._read_parser_cache(parser_cache_key)
        if cached_parser_artifact is not None:
            return (
                self._boundaries_from_documents(cached_parser_artifact.boundaries),
                CacheUsageSummary(parser_entries_reused=1),
            )

        boundaries = parser.parse(
            source_text=source_text,
            relative_path=source_file.relative_path,
        )
        self.cache_store.write_parser_cache(
            ParserCacheArtifactDocument(
                cache_key=parser_cache_key,
                language=source_file.language,
                relative_path=source_file.relative_path,
                source_content_hash=source_file.content_hash,
                parser_policy_id=parser_policy_id,
                boundaries=[
                    StructuralBoundaryDocument(
                        kind=boundary.kind,
                        start_line=boundary.start_line,
                        label=boundary.label,
                    )
                    for boundary in boundaries
                ],
            )
        )
        return tuple(boundaries), CacheUsageSummary(parser_entries_regenerated=1)

    def _read_parser_cache(self, cache_key: str) -> ParserCacheArtifactDocument | None:
        try:
            artifact = self.cache_store.read_parser_cache(cache_key)
        except (OSError, ValidationError, ValueError):
            return None
        if artifact is None or artifact.cache_key != cache_key:
            return None
        return artifact

    def _read_chunk_cache(self, cache_key: str) -> ChunkCacheArtifactDocument | None:
        try:
            artifact = self.cache_store.read_chunk_cache(cache_key)
        except (OSError, ValidationError, ValueError):
            return None
        if artifact is None or artifact.cache_key != cache_key:
            return None
        return artifact

    @staticmethod
    def read_source_text(*, repository_path: Path, relative_path: str) -> str:
        """Load a source file body as text for chunk generation."""

        file_path = repository_path / relative_path
        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return file_path.read_text(encoding="utf-8", errors="replace")
