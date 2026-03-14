from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

from codeman.bootstrap import bootstrap
from codeman.contracts.repository import CreateSnapshotRequest, RegisterRepositoryRequest


def run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def test_create_snapshot_persists_git_revision_and_manifest(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    (repository_path / "README.md").write_text("registered repo\n", encoding="utf-8")
    run_git(["init"], repository_path)
    run_git(["config", "user.name", "Codeman Tests"], repository_path)
    run_git(["config", "user.email", "tests@example.com"], repository_path)
    run_git(["add", "README.md"], repository_path)
    run_git(["commit", "-m", "Initial commit"], repository_path)

    container = bootstrap(workspace_root=workspace)
    registration = container.register_repository.execute(
        RegisterRepositoryRequest(repository_path=repository_path),
    )

    result = container.create_snapshot.execute(
        CreateSnapshotRequest(repository_id=registration.repository.repository_id),
    )

    db_row = (
        sqlite3.connect(result.snapshot.manifest_path.parents[3] / "metadata.sqlite3")
        .execute(
            """
            SELECT repository_id, revision_identity, revision_source, manifest_path
            FROM snapshots
            """,
        )
        .fetchone()
    )
    manifest = json.loads(result.snapshot.manifest_path.read_text(encoding="utf-8"))

    assert result.snapshot.manifest_path.exists()
    assert db_row == (
        registration.repository.repository_id,
        run_git(["rev-parse", "HEAD"], repository_path),
        "git",
        str(result.snapshot.manifest_path),
    )
    assert manifest["snapshot_id"] == result.snapshot.snapshot_id
    assert manifest["repository_id"] == registration.repository.repository_id
    assert manifest["revision_source"] == "git"


def test_create_snapshot_uses_deterministic_fallback_for_non_git_repository(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    (repository_path / "src").mkdir()
    (repository_path / "src" / "example.py").write_text("print('snapshot')\n", encoding="utf-8")
    container = bootstrap(workspace_root=workspace)
    registration = container.register_repository.execute(
        RegisterRepositoryRequest(repository_path=repository_path),
    )

    first = container.create_snapshot.execute(
        CreateSnapshotRequest(repository_id=registration.repository.repository_id),
    )
    second = container.create_snapshot.execute(
        CreateSnapshotRequest(repository_id=registration.repository.repository_id),
    )

    assert first.snapshot.revision_source == "filesystem_fingerprint"
    assert second.snapshot.revision_source == "filesystem_fingerprint"
    assert first.snapshot.revision_identity == second.snapshot.revision_identity
    assert first.snapshot.manifest_path.exists()
    assert second.snapshot.manifest_path.exists()
