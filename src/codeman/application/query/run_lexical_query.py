"""Run lexical retrieval queries against the current repository build."""

from __future__ import annotations

from dataclasses import dataclass

from codeman.application.ports.index_build_store_port import IndexBuildStorePort
from codeman.application.ports.lexical_query_port import LexicalQueryPort
from codeman.application.ports.metadata_store_port import RepositoryMetadataStorePort
from codeman.application.ports.snapshot_port import SnapshotMetadataStorePort
from codeman.contracts.errors import ErrorCode
from codeman.contracts.retrieval import RunLexicalQueryRequest, RunLexicalQueryResult
from codeman.runtime import RuntimePaths, provision_runtime_paths

__all__ = [
    "LexicalArtifactMissingError",
    "LexicalBuildBaselineMissingError",
    "LexicalQueryError",
    "LexicalQueryRepositoryNotRegisteredError",
    "RunLexicalQueryUseCase",
]


class LexicalQueryError(Exception):
    """Base exception for lexical-query failures."""

    exit_code = 39
    error_code = ErrorCode.LEXICAL_QUERY_FAILED

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class LexicalQueryRepositoryNotRegisteredError(LexicalQueryError):
    """Raised when querying an unknown repository."""

    exit_code = 24
    error_code = ErrorCode.REPOSITORY_NOT_REGISTERED


class LexicalArtifactMissingError(LexicalQueryError):
    """Raised when lexical build metadata points to a missing artifact."""

    exit_code = 37
    error_code = ErrorCode.LEXICAL_ARTIFACT_MISSING


class LexicalBuildBaselineMissingError(LexicalQueryError):
    """Raised when a repository has no current lexical build to query."""

    exit_code = 38
    error_code = ErrorCode.LEXICAL_BUILD_BASELINE_MISSING


@dataclass(slots=True)
class RunLexicalQueryUseCase:
    """Resolve the current lexical build for a repository and execute one query."""

    runtime_paths: RuntimePaths
    repository_store: RepositoryMetadataStorePort
    snapshot_store: SnapshotMetadataStorePort
    index_build_store: IndexBuildStorePort
    lexical_query: LexicalQueryPort

    def execute(self, request: RunLexicalQueryRequest) -> RunLexicalQueryResult:
        """Run a lexical query against the current repository build."""

        provision_runtime_paths(self.runtime_paths)
        self.repository_store.initialize()
        self.snapshot_store.initialize()
        self.index_build_store.initialize()

        repository = self.repository_store.get_by_repository_id(request.repository_id)
        if repository is None:
            raise LexicalQueryRepositoryNotRegisteredError(
                f"Repository is not registered: {request.repository_id}",
            )

        build = self.index_build_store.get_latest_build_for_repository(
            repository.repository_id,
        )
        if build is None:
            raise LexicalBuildBaselineMissingError(
                "No lexical baseline exists yet for this repository; "
                "run `codeman index build-lexical <snapshot-id>` first.",
            )
        if not build.index_path.exists():
            raise LexicalArtifactMissingError(
                f"Lexical artifact is missing for build: {build.build_id}",
            )

        snapshot = self.snapshot_store.get_by_snapshot_id(build.snapshot_id)
        if snapshot is None:
            raise LexicalQueryError(
                f"Lexical build points to an unknown snapshot: {build.snapshot_id}",
            )

        try:
            query_result = self.lexical_query.query(
                build=build,
                query_text=request.query_text,
            )
        except LexicalQueryError:
            raise
        except Exception as exc:
            raise LexicalQueryError(
                f"Lexical query failed for repository: {request.repository_id}",
            ) from exc

        return RunLexicalQueryResult(
            repository=repository,
            snapshot=snapshot,
            build=build,
            query=request.query_text,
            matches=list(query_result.matches),
            diagnostics=query_result.diagnostics,
        )
