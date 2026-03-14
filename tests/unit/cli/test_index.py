from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from codeman.application.indexing.build_chunks import SourceInventoryMissingError
from codeman.application.indexing.extract_source_files import SnapshotSourceMismatchError
from codeman.bootstrap import bootstrap
from codeman.cli.app import app
from codeman.contracts.chunking import (
    BuildChunksResult,
    ChunkFileDiagnostic,
    ChunkGenerationDiagnostics,
    ChunkRecord,
)
from codeman.contracts.repository import (
    ExtractSourceFilesResult,
    RepositoryRecord,
    SnapshotRecord,
    SourceFileRecord,
    SourceInventoryDiagnostics,
)

runner = CliRunner()


def build_result(repository_path: Path) -> ExtractSourceFilesResult:
    now = datetime.now(UTC)
    repository = RepositoryRecord(
        repository_id="repo-123",
        repository_name=repository_path.name,
        canonical_path=repository_path,
        requested_path=repository_path,
        created_at=now,
        updated_at=now,
    )
    snapshot = SnapshotRecord(
        snapshot_id="snapshot-123",
        repository_id=repository.repository_id,
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        manifest_path=repository_path / "manifest.json",
        created_at=now,
    )
    return ExtractSourceFilesResult(
        repository=repository,
        snapshot=snapshot,
        source_files=[
            SourceFileRecord(
                source_file_id="source-123",
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                relative_path="assets/app.js",
                language="javascript",
                content_hash="hash-123",
                byte_size=16,
                discovered_at=now,
            )
        ],
        diagnostics=SourceInventoryDiagnostics(
            persisted_by_language={"javascript": 1},
            skipped_by_reason={"unsupported_extension": 1},
            persisted_total=1,
            skipped_total=1,
        ),
    )


def build_chunk_result(repository_path: Path) -> BuildChunksResult:
    now = datetime.now(UTC)
    repository = RepositoryRecord(
        repository_id="repo-123",
        repository_name=repository_path.name,
        canonical_path=repository_path,
        requested_path=repository_path,
        created_at=now,
        updated_at=now,
    )
    snapshot = SnapshotRecord(
        snapshot_id="snapshot-123",
        repository_id=repository.repository_id,
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        manifest_path=repository_path / "manifest.json",
        created_at=now,
    )
    return BuildChunksResult(
        repository=repository,
        snapshot=snapshot,
        chunks=[
            ChunkRecord(
                chunk_id="chunk-123",
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                source_file_id="source-123",
                relative_path="assets/app.js",
                language="javascript",
                strategy="javascript_structure",
                source_content_hash="hash-123",
                start_line=1,
                end_line=3,
                start_byte=0,
                end_byte=42,
                payload_path=repository_path / ".codeman" / "chunk-123.json",
                created_at=now,
            ),
            ChunkRecord(
                chunk_id="chunk-456",
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                source_file_id="source-456",
                relative_path="assets/broken.js",
                language="javascript",
                strategy="javascript_fallback",
                source_content_hash="hash-456",
                start_line=1,
                end_line=2,
                start_byte=0,
                end_byte=31,
                payload_path=repository_path / ".codeman" / "chunk-456.json",
                created_at=now,
            ),
        ],
        diagnostics=ChunkGenerationDiagnostics(
            chunks_by_language={"javascript": 2},
            chunks_by_strategy={
                "javascript_fallback": 1,
                "javascript_structure": 1,
            },
            total_chunks=2,
            fallback_file_count=1,
            degraded_file_count=1,
            skipped_file_count=0,
            file_diagnostics=[
                ChunkFileDiagnostic(
                    source_file_id="source-123",
                    relative_path="assets/app.js",
                    language="javascript",
                    preferred_strategy="javascript_structure",
                    strategy_used="javascript_structure",
                    mode="structural",
                    chunk_count=1,
                ),
                ChunkFileDiagnostic(
                    source_file_id="source-456",
                    relative_path="assets/broken.js",
                    language="javascript",
                    preferred_strategy="javascript_structure",
                    strategy_used="javascript_fallback",
                    mode="fallback",
                    chunk_count=1,
                    reason="preferred_path_unavailable",
                    message="Unbalanced braces detected in JavaScript source",
                ),
            ],
        ),
    )


def test_index_extract_sources_command_renders_text_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubExtractSourceFilesUseCase:
        def execute(self, _request: object) -> ExtractSourceFilesResult:
            return build_result(target_repo.resolve())

    container.extract_source_files = StubExtractSourceFilesUseCase()

    result = runner.invoke(
        app,
        ["index", "extract-sources", "snapshot-123"],
        obj=container,
    )

    assert result.exit_code == 0, result.stdout
    assert "Extracted source inventory: 1 files" in result.stdout
    assert "Persisted by language: javascript=1" in result.stdout


def test_index_extract_sources_command_returns_json_failure_for_mismatch(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubExtractSourceFilesUseCase:
        def execute(self, _request: object) -> object:
            raise SnapshotSourceMismatchError(
                "Snapshot revision no longer matches the live repository state; "
                "create a new snapshot before extracting sources: snapshot-123",
            )

    container.extract_source_files = StubExtractSourceFilesUseCase()

    result = runner.invoke(
        app,
        ["index", "extract-sources", "snapshot-123", "--output-format", "json"],
        obj=container,
    )

    payload = json.loads(result.stdout.splitlines()[-1])

    assert result.exit_code == 27
    assert payload["ok"] is False
    assert payload["error"]["code"] == "snapshot_source_mismatch"
    assert payload["meta"]["command"] == "index.extract-sources"


def test_index_build_chunks_command_renders_text_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubBuildChunksUseCase:
        def execute(self, _request: object) -> BuildChunksResult:
            return build_chunk_result(target_repo.resolve())

    container.build_chunks = StubBuildChunksUseCase()

    result = runner.invoke(
        app,
        ["index", "build-chunks", "snapshot-123"],
        obj=container,
    )

    assert result.exit_code == 0, result.stdout
    assert "Generated retrieval chunks: 2 chunks" in result.stdout
    assert "Files using fallback: 1" in result.stdout


def test_index_build_chunks_command_returns_json_failure_for_missing_inventory(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubBuildChunksUseCase:
        def execute(self, _request: object) -> object:
            raise SourceInventoryMissingError(
                "Source inventory is missing for snapshot; run "
                "`codeman index extract-sources snapshot-123` first.",
            )

    container.build_chunks = StubBuildChunksUseCase()

    result = runner.invoke(
        app,
        ["index", "build-chunks", "snapshot-123", "--output-format", "json"],
        obj=container,
    )

    payload = json.loads(result.stdout.splitlines()[-1])

    assert result.exit_code == 29
    assert payload["ok"] is False
    assert payload["error"]["code"] == "source_inventory_missing"
    assert payload["meta"]["command"] == "index.build-chunks"
