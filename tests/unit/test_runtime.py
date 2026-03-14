from pathlib import Path

from codeman.runtime import RuntimePaths, build_runtime_paths, provision_runtime_paths


def test_build_runtime_paths_uses_dot_codeman_workspace(tmp_path: Path) -> None:
    paths = build_runtime_paths(tmp_path)

    assert isinstance(paths, RuntimePaths)
    assert paths.root == tmp_path / ".codeman"
    assert paths.artifacts == paths.root / "artifacts"
    assert paths.indexes == paths.root / "indexes"
    assert paths.cache == paths.root / "cache"
    assert paths.logs == paths.root / "logs"
    assert paths.tmp == paths.root / "tmp"
    assert paths.metadata_database_path == paths.root / "metadata.sqlite3"


def test_provision_runtime_paths_creates_expected_directories(tmp_path: Path) -> None:
    paths = build_runtime_paths(tmp_path)

    provision_runtime_paths(paths)

    assert paths.root.is_dir()
    assert paths.artifacts.is_dir()
    assert paths.indexes.is_dir()
    assert paths.cache.is_dir()
    assert paths.logs.is_dir()
    assert paths.tmp.is_dir()
