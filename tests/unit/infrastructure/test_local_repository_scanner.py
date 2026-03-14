from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from codeman.infrastructure.snapshotting.local_repository_scanner import (
    LocalRepositoryScanner,
    build_source_file_id,
    classify_source_language,
    is_binary_content,
)

FIXTURE_REPOSITORY = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "repositories"
    / "mixed_stack_fixture"
)


def test_classify_source_language_supports_mvp_extensions() -> None:
    assert classify_source_language("src/Controller/HomeController.php") == "php"
    assert classify_source_language("assets/app.js") == "javascript"
    assert classify_source_language("public/index.html") == "html"
    assert classify_source_language("templates/page.html.twig") == "twig"
    assert classify_source_language("README.md") is None


def test_is_binary_content_detects_null_bytes() -> None:
    assert is_binary_content(b"\x00\x01binary") is True
    assert is_binary_content(b"plain text\n") is False


def test_scan_collects_supported_files_and_skips_binary_ignored_and_unsupported(
    tmp_path: Path,
) -> None:
    repository_path = tmp_path / "fixture-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)
    scanner = LocalRepositoryScanner()

    result = scanner.scan(
        repository_path=repository_path,
        snapshot_id="snapshot-123",
        repository_id="repo-123",
        discovered_at=datetime.now(UTC),
    )

    assert [record.relative_path for record in result.source_files] == [
        "assets/app.js",
        "assets/broken.js",
        "public/index.html",
        "src/Controller/HomeController.php",
        "templates/page.html.twig",
    ]
    assert result.skipped_by_reason == {
        "binary": 1,
        "ignored": 1,
        "unsupported_extension": 1,
    }


def test_source_file_identifiers_and_hashes_are_stable_across_traversal_order(
    tmp_path: Path,
) -> None:
    scanner = LocalRepositoryScanner()
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    for repository_path in (repo_a, repo_b):
        (repository_path / "src").mkdir(parents=True)
        (repository_path / "templates").mkdir(parents=True)

    (repo_a / "src" / "first.php").write_text("<?php echo 'a';\n", encoding="utf-8")
    (repo_a / "templates" / "view.html.twig").write_text(
        "<h1>A</h1>\n",
        encoding="utf-8",
    )
    (repo_b / "templates" / "view.html.twig").write_text(
        "<h1>A</h1>\n",
        encoding="utf-8",
    )
    (repo_b / "src" / "first.php").write_text("<?php echo 'a';\n", encoding="utf-8")

    first = scanner.scan(
        repository_path=repo_a,
        snapshot_id="snapshot-123",
        repository_id="repo-123",
        discovered_at=datetime.now(UTC),
    )
    second = scanner.scan(
        repository_path=repo_b,
        snapshot_id="snapshot-123",
        repository_id="repo-123",
        discovered_at=datetime.now(UTC),
    )

    first_records = {
        record.relative_path: (record.source_file_id, record.content_hash)
        for record in first.source_files
    }
    second_records = {
        record.relative_path: (record.source_file_id, record.content_hash)
        for record in second.source_files
    }

    assert first_records == second_records
    assert build_source_file_id(
        "snapshot-123",
        "src/first.php",
    ) == first_records["src/first.php"][0]


def test_scan_counts_each_file_inside_ignored_directories(
    tmp_path: Path,
) -> None:
    repository_path = tmp_path / "fixture-repo"
    (repository_path / "vendor" / "nested").mkdir(parents=True)
    (repository_path / "src").mkdir(parents=True)
    (repository_path / "vendor" / "ignored-a.php").write_text(
        "<?php echo 'a';\n",
        encoding="utf-8",
    )
    (repository_path / "vendor" / "nested" / "ignored-b.js").write_text(
        "console.log('b');\n",
        encoding="utf-8",
    )
    (repository_path / "src" / "tracked.php").write_text(
        "<?php echo 'tracked';\n",
        encoding="utf-8",
    )
    scanner = LocalRepositoryScanner()

    result = scanner.scan(
        repository_path=repository_path,
        snapshot_id="snapshot-123",
        repository_id="repo-123",
        discovered_at=datetime.now(UTC),
    )

    assert [record.relative_path for record in result.source_files] == ["src/tracked.php"]
    assert result.skipped_by_reason["ignored"] == 2
