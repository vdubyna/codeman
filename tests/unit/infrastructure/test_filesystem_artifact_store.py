from __future__ import annotations

import json
from pathlib import Path

from codeman.contracts.chunking import ChunkPayloadDocument
from codeman.infrastructure.artifacts.filesystem_artifact_store import (
    FilesystemArtifactStore,
)


def test_write_chunk_payload_persists_json_artifact(tmp_path: Path) -> None:
    artifact_store = FilesystemArtifactStore(tmp_path)
    payload = ChunkPayloadDocument(
        chunk_id="chunk-123",
        snapshot_id="snapshot-123",
        repository_id="repo-123",
        source_file_id="source-123",
        relative_path="assets/app.js",
        language="javascript",
        strategy="javascript_structure",
        source_content_hash="hash-123",
        start_line=1,
        end_line=3,
        start_byte=0,
        end_byte=42,
        content='export function boot() {\n  return "codeman";\n}\n',
    )

    destination = artifact_store.write_chunk_payload(
        payload,
        snapshot_id=payload.snapshot_id,
    )

    assert destination == tmp_path / "snapshots" / "snapshot-123" / "chunks" / "chunk-123.json"
    stored = json.loads(destination.read_text(encoding="utf-8"))
    assert stored["chunk_id"] == "chunk-123"
    assert stored["relative_path"] == "assets/app.js"


def test_read_chunk_payload_round_trips_json_artifact(tmp_path: Path) -> None:
    artifact_store = FilesystemArtifactStore(tmp_path)
    payload = ChunkPayloadDocument(
        chunk_id="chunk-123",
        snapshot_id="snapshot-123",
        repository_id="repo-123",
        source_file_id="source-123",
        relative_path="assets/app.js",
        language="javascript",
        strategy="javascript_structure",
        source_content_hash="hash-123",
        start_line=1,
        end_line=3,
        start_byte=0,
        end_byte=42,
        content='export function boot() {\n  return "codeman";\n}\n',
    )

    destination = artifact_store.write_chunk_payload(
        payload,
        snapshot_id=payload.snapshot_id,
    )
    restored = artifact_store.read_chunk_payload(destination)

    assert restored.chunk_id == payload.chunk_id
    assert restored.snapshot_id == payload.snapshot_id
    assert restored.content == payload.content
