"""Resolve repository revision identity using Git or a deterministic fallback."""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from codeman.application.ports.snapshot_port import ResolvedRevision, RevisionResolverPort


@dataclass(slots=True)
class GitRevisionResolver(RevisionResolverPort):
    """Resolve Git HEAD when available, otherwise use a filesystem fingerprint."""

    ignored_directories: tuple[str, ...] = (".git", ".codeman", "__pycache__")

    def resolve(self, repository_path: Path) -> ResolvedRevision:
        """Resolve the repository revision using the best available strategy."""

        git_revision = self._resolve_clean_git_head(repository_path)
        if git_revision is not None:
            return ResolvedRevision(identity=git_revision, source="git")

        return ResolvedRevision(
            identity=self._build_filesystem_fingerprint(repository_path),
            source="filesystem_fingerprint",
        )

    @staticmethod
    def _run_git_command(
        repository_path: Path,
        *args: str,
    ) -> subprocess.CompletedProcess[str] | None:
        """Run a git command for the repository or return `None` if git is unavailable."""

        try:
            return subprocess.run(
                ["git", "-C", str(repository_path), *args],
                capture_output=True,
                check=False,
                text=True,
            )
        except FileNotFoundError:
            return None

    @classmethod
    def _resolve_clean_git_head(cls, repository_path: Path) -> str | None:
        """Return Git HEAD only when the repository metadata is available and clean."""

        head_result = cls._run_git_command(repository_path, "rev-parse", "HEAD")
        if head_result is None or head_result.returncode != 0:
            return None

        status_result = cls._run_git_command(
            repository_path,
            "status",
            "--porcelain",
            "--untracked-files=all",
        )
        if status_result is None or status_result.returncode != 0:
            return None
        if status_result.stdout.strip():
            return None

        revision = head_result.stdout.strip()
        return revision or None

    def _build_filesystem_fingerprint(self, repository_path: Path) -> str:
        """Create a deterministic fingerprint from repository file paths and contents."""

        digest = hashlib.sha256()

        for root, dirs, files in os.walk(repository_path, topdown=True):
            dirs[:] = sorted(
                directory for directory in dirs if directory not in self.ignored_directories
            )
            for file_name in sorted(files):
                path = Path(root) / file_name
                if any(part in self.ignored_directories for part in path.parts):
                    continue

                relative_path = path.relative_to(repository_path).as_posix()
                digest.update(relative_path.encode("utf-8"))

                if path.is_symlink():
                    digest.update(b"symlink")
                    digest.update(os.readlink(path).encode("utf-8"))
                    continue

                if not path.is_file():
                    continue

                digest.update(b"file")
                with path.open("rb") as handle:
                    while chunk := handle.read(8192):
                        digest.update(chunk)

        return digest.hexdigest()
