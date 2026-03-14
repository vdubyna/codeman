"""Register a local repository for future indexing workflows."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from codeman.application.ports.metadata_store_port import RepositoryMetadataStorePort
from codeman.contracts.errors import ErrorCode
from codeman.contracts.repository import RegisterRepositoryRequest, RegisterRepositoryResult
from codeman.runtime import RuntimePaths, provision_runtime_paths


class RepositoryRegistrationError(Exception):
    """Base exception for repository registration failures."""

    exit_code = 1
    error_code = ErrorCode.INTERNAL_ERROR

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RepositoryPathNotFoundError(RepositoryRegistrationError):
    """Raised when the requested repository path does not exist."""

    exit_code = 20
    error_code = ErrorCode.REPOSITORY_PATH_NOT_FOUND


class RepositoryPathNotDirectoryError(RepositoryRegistrationError):
    """Raised when the requested repository path is not a directory."""

    exit_code = 21
    error_code = ErrorCode.REPOSITORY_PATH_NOT_DIRECTORY


class RepositoryPathNotReadableError(RepositoryRegistrationError):
    """Raised when the requested repository path is not readable."""

    exit_code = 22
    error_code = ErrorCode.REPOSITORY_PATH_NOT_READABLE


class RepositoryAlreadyRegisteredError(RepositoryRegistrationError):
    """Raised when the canonical repository path is already registered."""

    exit_code = 23
    error_code = ErrorCode.REPOSITORY_ALREADY_REGISTERED


def normalize_repository_path(repository_path: Path) -> Path:
    """Resolve the repository path to a canonical absolute directory."""

    candidate = repository_path.expanduser()

    try:
        canonical_path = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise RepositoryPathNotFoundError(
            f"Repository path does not exist: {repository_path}",
        ) from exc

    if not canonical_path.is_dir():
        raise RepositoryPathNotDirectoryError(
            f"Repository path is not a directory: {canonical_path}",
        )

    if not os.access(canonical_path, os.R_OK | os.X_OK):
        raise RepositoryPathNotReadableError(
            f"Repository path is not readable: {canonical_path}",
        )

    return canonical_path


def derive_repository_name(canonical_path: Path) -> str:
    """Build a human-readable repository name from a canonical path."""

    return canonical_path.name or canonical_path.as_posix()


@dataclass(slots=True)
class RegisterRepositoryUseCase:
    """Register local repositories and prepare runtime storage."""

    runtime_paths: RuntimePaths
    metadata_store: RepositoryMetadataStorePort

    def execute(self, request: RegisterRepositoryRequest) -> RegisterRepositoryResult:
        """Register the repository described by the request."""

        canonical_path = normalize_repository_path(request.repository_path)
        provision_runtime_paths(self.runtime_paths)
        self.metadata_store.initialize()
        existing_record = self.metadata_store.get_by_canonical_path(canonical_path)
        if existing_record is not None:
            raise RepositoryAlreadyRegisteredError(
                f"Repository is already registered: {canonical_path}",
            )

        repository = self.metadata_store.create_repository(
            repository_name=derive_repository_name(canonical_path),
            canonical_path=canonical_path,
            requested_path=canonical_path,
        )
        return RegisterRepositoryResult(
            repository=repository,
            runtime_root=self.runtime_paths.root,
            metadata_database_path=self.runtime_paths.metadata_database_path,
        )
