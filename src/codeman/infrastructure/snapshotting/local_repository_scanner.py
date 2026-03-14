"""Scan local repositories for supported source files."""

from __future__ import annotations

import hashlib
import os
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from codeman.application.ports.source_inventory_port import (
    ScanSourceFilesResult,
    SourceScannerPort,
)
from codeman.contracts.repository import SourceFileRecord, SourceLanguage

BUFFER_SIZE = 8192
TEXT_CONTROL_BYTES = {7, 8, 9, 10, 12, 13, 27}
DEFAULT_IGNORED_DIRECTORY_NAMES = (
    ".git",
    ".codeman",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "vendor",
    ".venv",
    "venv",
)


def classify_source_language(relative_path: str) -> SourceLanguage | None:
    """Map the supported MVP extension policy to a normalized language label."""

    normalized_path = relative_path.lower()
    if normalized_path.endswith(".twig"):
        return "twig"
    if normalized_path.endswith(".php"):
        return "php"
    if normalized_path.endswith((".js", ".mjs", ".cjs")):
        return "javascript"
    if normalized_path.endswith((".html", ".htm")):
        return "html"
    return None


def build_source_file_id(snapshot_id: str, relative_path: str) -> str:
    """Build a deterministic source-file identifier for snapshot-local persistence."""

    return hashlib.sha256(f"{snapshot_id}:{relative_path}".encode("utf-8")).hexdigest()


def compute_content_hash(chunks: list[bytes]) -> str:
    """Return a deterministic digest for a source file body."""

    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk)
    return digest.hexdigest()


def is_binary_content(content: bytes) -> bool:
    """Heuristically detect binary payloads without decoding their contents."""

    if not content:
        return False
    if b"\x00" in content:
        return True

    non_text_bytes = sum(
        byte < 32 and byte not in TEXT_CONTROL_BYTES for byte in content
    )
    return non_text_bytes / len(content) > 0.3


@dataclass(frozen=True, slots=True)
class FileInspection:
    """Metadata gathered while reading a candidate file once."""

    byte_size: int
    content_hash: str | None
    is_binary: bool


@dataclass(slots=True)
class LocalRepositoryScanner(SourceScannerPort):
    """Walk a repository tree and collect supported source-file metadata."""

    ignored_directory_names: tuple[str, ...] = DEFAULT_IGNORED_DIRECTORY_NAMES

    def scan(
        self,
        *,
        repository_path: Path,
        snapshot_id: str,
        repository_id: str,
        discovered_at: datetime,
    ) -> ScanSourceFilesResult:
        """Scan only within the repository root and classify supported source files."""

        source_files: list[SourceFileRecord] = []
        skipped_by_reason: Counter[str] = Counter()
        git_file_listing = discover_git_file_listing(repository_path)

        if git_file_listing is not None:
            skipped_by_reason["ignored"] += git_file_listing.ignored_file_count
            candidate_paths = git_file_listing.candidate_paths
            return self._collect_source_files(
                repository_path=repository_path,
                snapshot_id=snapshot_id,
                repository_id=repository_id,
                discovered_at=discovered_at,
                candidate_paths=candidate_paths,
                skipped_by_reason=skipped_by_reason,
            )

        for root, dirs, files in os.walk(repository_path, topdown=True, followlinks=False):
            current_root = Path(root)
            dirs[:] = self._filter_directories(
                current_root=current_root,
                directories=dirs,
                skipped_by_reason=skipped_by_reason,
            )

            for file_name in sorted(files):
                source_files.extend(
                    self._build_source_file_records(
                        repository_path=repository_path,
                        snapshot_id=snapshot_id,
                        repository_id=repository_id,
                        discovered_at=discovered_at,
                        candidate_paths=(current_root / file_name,),
                        skipped_by_reason=skipped_by_reason,
                    )
                )

        source_files.sort(key=lambda record: record.relative_path)
        return ScanSourceFilesResult(
            source_files=tuple(source_files),
            skipped_by_reason=dict(sorted(skipped_by_reason.items())),
        )

    def _filter_directories(
        self,
        *,
        current_root: Path,
        directories: list[str],
        skipped_by_reason: Counter[str],
    ) -> list[str]:
        """Retain only safe directories within the repository root."""

        retained_directories: list[str] = []
        for directory_name in sorted(directories):
            directory_path = current_root / directory_name
            if directory_name in self.ignored_directory_names:
                skipped_by_reason["ignored"] += count_files_in_tree(directory_path)
                continue
            if directory_path.is_symlink():
                skipped_by_reason["ignored"] += 1
                continue
            retained_directories.append(directory_name)
        return retained_directories

    def _collect_source_files(
        self,
        *,
        repository_path: Path,
        snapshot_id: str,
        repository_id: str,
        discovered_at: datetime,
        candidate_paths: tuple[str, ...],
        skipped_by_reason: Counter[str],
    ) -> ScanSourceFilesResult:
        """Build source records from a precomputed set of relative candidate paths."""

        source_files = self._build_source_file_records(
            repository_path=repository_path,
            snapshot_id=snapshot_id,
            repository_id=repository_id,
            discovered_at=discovered_at,
            candidate_paths=tuple(repository_path / path for path in candidate_paths),
            skipped_by_reason=skipped_by_reason,
        )
        source_files.sort(key=lambda record: record.relative_path)
        return ScanSourceFilesResult(
            source_files=tuple(source_files),
            skipped_by_reason=dict(sorted(skipped_by_reason.items())),
        )

    def _build_source_file_records(
        self,
        *,
        repository_path: Path,
        snapshot_id: str,
        repository_id: str,
        discovered_at: datetime,
        candidate_paths: tuple[Path, ...],
        skipped_by_reason: Counter[str],
    ) -> list[SourceFileRecord]:
        """Inspect candidate files and convert supported ones into contract DTOs."""

        source_files: list[SourceFileRecord] = []
        for file_path in candidate_paths:
            relative_path = file_path.relative_to(repository_path).as_posix()

            if file_path.is_symlink():
                skipped_by_reason["ignored"] += 1
                continue

            try:
                inspection = inspect_file(file_path)
            except OSError:
                skipped_by_reason["unreadable"] += 1
                continue

            if inspection.is_binary:
                skipped_by_reason["binary"] += 1
                continue

            language = classify_source_language(relative_path)
            if language is None:
                skipped_by_reason["unsupported_extension"] += 1
                continue

            source_files.append(
                SourceFileRecord(
                    source_file_id=build_source_file_id(snapshot_id, relative_path),
                    snapshot_id=snapshot_id,
                    repository_id=repository_id,
                    relative_path=relative_path,
                    language=language,
                    content_hash=inspection.content_hash or "",
                    byte_size=inspection.byte_size,
                    discovered_at=discovered_at,
                )
            )

        return source_files


@dataclass(frozen=True, slots=True)
class GitFileListing:
    """Git-aware candidate and ignored file listing relative to the repo root."""

    candidate_paths: tuple[str, ...]
    ignored_file_count: int


def discover_git_file_listing(repository_path: Path) -> GitFileListing | None:
    """Return git-visible candidate files and ignored-file counts when possible."""

    if not is_git_repository(repository_path):
        return None

    candidate_result = run_git_command(
        repository_path,
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "-z",
    )
    ignored_result = run_git_command(
        repository_path,
        "ls-files",
        "--others",
        "-i",
        "--exclude-standard",
        "-z",
    )
    if (
        candidate_result is None
        or ignored_result is None
        or candidate_result.returncode != 0
        or ignored_result.returncode != 0
    ):
        return None

    candidate_paths = tuple(sorted(parse_nul_delimited_paths(candidate_result.stdout)))
    ignored_paths = parse_nul_delimited_paths(ignored_result.stdout)
    return GitFileListing(
        candidate_paths=candidate_paths,
        ignored_file_count=len(ignored_paths),
    )


def is_git_repository(repository_path: Path) -> bool:
    """Return whether the repository root is backed by Git metadata."""

    result = run_git_command(repository_path, "rev-parse", "--is-inside-work-tree")
    return result is not None and result.returncode == 0 and result.stdout.strip() == "true"


def run_git_command(
    repository_path: Path,
    *args: str,
) -> subprocess.CompletedProcess[str] | None:
    """Run a git command or return `None` if git is unavailable."""

    try:
        return subprocess.run(
            ["git", "-C", str(repository_path), *args],
            capture_output=True,
            check=False,
            text=True,
        )
    except FileNotFoundError:
        return None


def parse_nul_delimited_paths(output: str) -> tuple[str, ...]:
    """Parse a git `-z` response into normalized relative paths."""

    return tuple(path for path in output.split("\x00") if path)


def count_files_in_tree(directory_path: Path) -> int:
    """Count files under an ignored directory without following symlinked dirs."""

    total = 0
    for root, dirs, files in os.walk(directory_path, topdown=True, followlinks=False):
        current_root = Path(root)
        retained_directories: list[str] = []
        for directory_name in dirs:
            candidate = current_root / directory_name
            if candidate.is_symlink():
                total += 1
                continue
            retained_directories.append(directory_name)
        dirs[:] = retained_directories
        total += len(files)
    return total


def inspect_file(file_path: Path) -> FileInspection:
    """Read a candidate file once to determine size, hash, and binary state."""

    with file_path.open("rb") as handle:
        first_chunk = handle.read(BUFFER_SIZE)
        if is_binary_content(first_chunk):
            return FileInspection(byte_size=len(first_chunk), content_hash=None, is_binary=True)

        chunks = [first_chunk]
        byte_size = len(first_chunk)
        while chunk := handle.read(BUFFER_SIZE):
            chunks.append(chunk)
            byte_size += len(chunk)

    return FileInspection(
        byte_size=byte_size,
        content_hash=compute_content_hash(chunks),
        is_binary=False,
    )
