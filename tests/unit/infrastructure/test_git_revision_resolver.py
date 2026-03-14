from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from codeman.infrastructure.snapshotting.git_revision_resolver import GitRevisionResolver


def run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def test_git_revision_resolver_returns_head_commit_for_git_repository(tmp_path: Path) -> None:
    repository_path = tmp_path / "git-repo"
    repository_path.mkdir()
    (repository_path / "README.md").write_text("snapshot story\n", encoding="utf-8")

    run_git(["init"], repository_path)
    run_git(["config", "user.name", "Codeman Tests"], repository_path)
    run_git(["config", "user.email", "tests@example.com"], repository_path)
    run_git(["add", "README.md"], repository_path)
    run_git(["commit", "-m", "Initial commit"], repository_path)

    resolved = GitRevisionResolver().resolve(repository_path)

    assert resolved.source == "git"
    assert resolved.identity == run_git(["rev-parse", "HEAD"], repository_path)


def test_git_revision_resolver_falls_back_for_dirty_git_repository(tmp_path: Path) -> None:
    repository_path = tmp_path / "git-repo"
    repository_path.mkdir()
    tracked_file = repository_path / "README.md"
    tracked_file.write_text("snapshot story\n", encoding="utf-8")

    run_git(["init"], repository_path)
    run_git(["config", "user.name", "Codeman Tests"], repository_path)
    run_git(["config", "user.email", "tests@example.com"], repository_path)
    run_git(["add", "README.md"], repository_path)
    run_git(["commit", "-m", "Initial commit"], repository_path)

    tracked_file.write_text("dirty working tree\n", encoding="utf-8")

    resolved = GitRevisionResolver().resolve(repository_path)

    assert resolved.source == "filesystem_fingerprint"
    assert resolved.identity != run_git(["rev-parse", "HEAD"], repository_path)


def test_git_revision_resolver_falls_back_to_deterministic_filesystem_fingerprint(
    tmp_path: Path,
) -> None:
    first_repository = tmp_path / "repo-a"
    second_repository = tmp_path / "repo-b"
    first_repository.mkdir()
    second_repository.mkdir()

    (first_repository / "src").mkdir()
    (second_repository / "src").mkdir()
    (first_repository / "src" / "beta.py").write_text("print('beta')\n", encoding="utf-8")
    (first_repository / "src" / "alpha.py").write_text("print('alpha')\n", encoding="utf-8")
    (second_repository / "src" / "alpha.py").write_text("print('alpha')\n", encoding="utf-8")
    (second_repository / "src" / "beta.py").write_text("print('beta')\n", encoding="utf-8")

    resolver = GitRevisionResolver()
    first = resolver.resolve(first_repository)
    second = resolver.resolve(second_repository)

    assert first.source == "filesystem_fingerprint"
    assert second.source == "filesystem_fingerprint"
    assert first.identity == second.identity

    (first_repository / ".codeman").mkdir()
    (first_repository / ".codeman" / "ignored.txt").write_text("ignore me\n", encoding="utf-8")

    after_runtime_artifact = resolver.resolve(first_repository)

    assert after_runtime_artifact.identity == first.identity


def test_git_revision_resolver_falls_back_when_git_binary_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_path = tmp_path / "repo"
    repository_path.mkdir()
    (repository_path / "example.py").write_text("print('snapshot')\n", encoding="utf-8")

    def raise_file_not_found(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", raise_file_not_found)

    resolved = GitRevisionResolver().resolve(repository_path)

    assert resolved.source == "filesystem_fingerprint"
    assert resolved.identity
