from __future__ import annotations

import shutil
import sqlite3
import subprocess
from pathlib import Path

from codeman.bootstrap import bootstrap
from codeman.contracts.repository import (
    CreateSnapshotRequest,
    ExtractSourceFilesRequest,
    RegisterRepositoryRequest,
)

FIXTURE_REPOSITORY = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "repositories"
    / "mixed_stack_fixture"
)


def run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def test_extract_source_files_creates_source_inventory_rows_via_alembic(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container = bootstrap(workspace_root=workspace)
    registration = container.register_repository.execute(
        RegisterRepositoryRequest(repository_path=repository_path),
    )
    snapshot = container.create_snapshot.execute(
        CreateSnapshotRequest(repository_id=registration.repository.repository_id),
    )

    result = container.extract_source_files.execute(
        ExtractSourceFilesRequest(snapshot_id=snapshot.snapshot.snapshot_id),
    )

    database_path = workspace / ".codeman" / "metadata.sqlite3"
    connection = sqlite3.connect(database_path)
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'",
        ).fetchall()
    }
    rows = connection.execute(
        """
        SELECT snapshot_id, relative_path, language
        FROM source_files
        ORDER BY relative_path
        """,
    ).fetchall()

    assert "source_files" in tables
    assert result.diagnostics.persisted_total == 5
    assert rows == [
        (snapshot.snapshot.snapshot_id, "assets/app.js", "javascript"),
        (snapshot.snapshot.snapshot_id, "assets/broken.js", "javascript"),
        (snapshot.snapshot.snapshot_id, "public/index.html", "html"),
        (snapshot.snapshot.snapshot_id, "src/Controller/HomeController.php", "php"),
        (snapshot.snapshot.snapshot_id, "templates/page.html.twig", "twig"),
    ]


def test_extract_source_files_does_not_duplicate_rows_for_same_snapshot(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container = bootstrap(workspace_root=workspace)
    registration = container.register_repository.execute(
        RegisterRepositoryRequest(repository_path=repository_path),
    )
    snapshot = container.create_snapshot.execute(
        CreateSnapshotRequest(repository_id=registration.repository.repository_id),
    )

    first = container.extract_source_files.execute(
        ExtractSourceFilesRequest(snapshot_id=snapshot.snapshot.snapshot_id),
    )
    second = container.extract_source_files.execute(
        ExtractSourceFilesRequest(snapshot_id=snapshot.snapshot.snapshot_id),
    )

    database_path = workspace / ".codeman" / "metadata.sqlite3"
    row_count = sqlite3.connect(database_path).execute(
        "SELECT COUNT(*) FROM source_files",
    ).fetchone()[0]

    assert first.diagnostics.persisted_total == 5
    assert second.diagnostics.persisted_total == 5
    assert row_count == 5


def test_extract_source_files_skips_gitignored_supported_files(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    (repository_path / "src").mkdir()
    (repository_path / "generated").mkdir()
    (repository_path / ".gitignore").write_text("generated/\n", encoding="utf-8")
    (repository_path / "src" / "tracked.php").write_text(
        "<?php echo 'tracked';\n",
        encoding="utf-8",
    )
    run_git(["init"], repository_path)
    run_git(["config", "user.name", "Codeman Tests"], repository_path)
    run_git(["config", "user.email", "tests@example.com"], repository_path)
    run_git(["add", ".gitignore", "src/tracked.php"], repository_path)
    run_git(["commit", "-m", "Initial commit"], repository_path)
    (repository_path / "generated" / "ignored.php").write_text(
        "<?php echo 'ignored';\n",
        encoding="utf-8",
    )

    container = bootstrap(workspace_root=workspace)
    registration = container.register_repository.execute(
        RegisterRepositoryRequest(repository_path=repository_path),
    )
    snapshot = container.create_snapshot.execute(
        CreateSnapshotRequest(repository_id=registration.repository.repository_id),
    )

    result = container.extract_source_files.execute(
        ExtractSourceFilesRequest(snapshot_id=snapshot.snapshot.snapshot_id),
    )

    assert [record.relative_path for record in result.source_files] == ["src/tracked.php"]
    assert result.diagnostics.persisted_total == 1
    assert result.diagnostics.skipped_by_reason["ignored"] == 1
