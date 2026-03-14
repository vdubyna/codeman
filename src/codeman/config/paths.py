"""Configuration-related path helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

USER_CONFIG_DIRECTORY_NAME = "codeman"
USER_CONFIG_FILE_NAME = "config.toml"


def _resolve_path(path_value: str | Path) -> Path:
    return Path(path_value).expanduser().resolve()


def resolve_project_pyproject_path(project_root: Path | None = None) -> Path:
    """Return the canonical ``pyproject.toml`` path for the current project."""

    if project_root is not None:
        return project_root.resolve() / "pyproject.toml"
    return Path(__file__).resolve().parents[3] / "pyproject.toml"


def resolve_user_config_path(
    config_path: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Resolve the canonical optional user-local config path."""

    if config_path is not None:
        return _resolve_path(config_path)

    environment = env if env is not None else os.environ
    explicit_path = environment.get("CODEMAN_CONFIG_PATH")
    if explicit_path:
        return _resolve_path(explicit_path)

    config_home = environment.get("XDG_CONFIG_HOME")
    if config_home:
        base_path = _resolve_path(config_home)
    else:
        home_directory = environment.get("HOME")
        base_path = (
            _resolve_path(home_directory) / ".config"
            if home_directory
            else Path.home().expanduser().resolve() / ".config"
        )

    return (base_path / USER_CONFIG_DIRECTORY_NAME / USER_CONFIG_FILE_NAME).resolve()


__all__ = ["resolve_project_pyproject_path", "resolve_user_config_path"]
