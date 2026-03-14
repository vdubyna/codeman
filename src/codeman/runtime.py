"""Runtime path helpers for workspace-managed artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    """Resolved runtime directories under `.codeman/`."""

    workspace_root: Path
    root: Path
    artifacts: Path
    indexes: Path
    cache: Path
    logs: Path
    tmp: Path
    metadata_database_path: Path


def build_runtime_paths(
    workspace_root: Path | None = None,
    root_dir_name: str = ".codeman",
    metadata_database_name: str = "metadata.sqlite3",
) -> RuntimePaths:
    """Resolve the runtime directory tree without creating it."""

    base_workspace = (workspace_root or Path.cwd()).resolve()
    root = base_workspace / root_dir_name
    return RuntimePaths(
        workspace_root=base_workspace,
        root=root,
        artifacts=root / "artifacts",
        indexes=root / "indexes",
        cache=root / "cache",
        logs=root / "logs",
        tmp=root / "tmp",
        metadata_database_path=root / metadata_database_name,
    )


def provision_runtime_paths(paths: RuntimePaths) -> RuntimePaths:
    """Create the runtime directory tree for the current workspace."""

    for directory in (
        paths.root,
        paths.artifacts,
        paths.indexes,
        paths.cache,
        paths.logs,
        paths.tmp,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    return paths
