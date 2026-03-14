from __future__ import annotations

from pathlib import Path

import pytest

from codeman.config.defaults import IN_CODE_DEFAULTS, load_project_defaults
from codeman.config.loader import ConfigOverrides, ConfigurationResolutionError, load_app_config
from codeman.config.paths import resolve_user_config_path


def test_load_project_defaults_uses_in_code_fallback_when_tool_table_missing(
    tmp_path: Path,
) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """
[project]
name = "example"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    defaults = load_project_defaults(pyproject_path)

    assert defaults == IN_CODE_DEFAULTS


def test_resolve_user_config_path_uses_xdg_config_home_when_available(
    tmp_path: Path,
) -> None:
    resolved_path = resolve_user_config_path(
        env={
            "HOME": str(tmp_path / "home"),
            "XDG_CONFIG_HOME": str(tmp_path / "xdg-config"),
        }
    )

    assert resolved_path == (tmp_path / "xdg-config" / "codeman" / "config.toml").resolve()


def test_load_app_config_applies_defaults_local_cli_and_env_precedence(
    tmp_path: Path,
) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """
[tool.codeman]
project_name = "project-default"
default_output_format = "json"

[tool.codeman.runtime]
workspace_root = "/tmp/project-workspace"
root_dir_name = ".project-root"
metadata_database_name = "project.sqlite3"

[tool.codeman.indexing]
fingerprint_salt = "project-salt"

[tool.codeman.semantic_indexing]
provider_id = "local-hash"
model_id = "project-model"
model_version = "1"
local_model_path = "/tmp/project-model"
vector_engine = "sqlite-exact"
vector_dimension = 8
fingerprint_salt = "project-semantic-salt"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    local_config_path = tmp_path / "local-config.toml"
    local_config_path.write_text(
        """
[runtime]
workspace_root = "/tmp/local-workspace"
root_dir_name = ".local-root"

[indexing]
fingerprint_salt = "local-salt"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = load_app_config(
        pyproject_path=pyproject_path,
        cli_overrides=ConfigOverrides(
            config_path=local_config_path,
            workspace_root=tmp_path / "cli-workspace",
            runtime_root_dir=".cli-root",
        ),
        environ={
            "CODEMAN_RUNTIME_ROOT_DIR": ".env-root",
            "CODEMAN_METADATA_DATABASE_NAME": "env.sqlite3",
            "CODEMAN_INDEXING_FINGERPRINT_SALT": "env-salt",
            "CODEMAN_SEMANTIC_MODEL_VERSION": "2026-03-14",
        },
    )

    assert config.project_name == "project-default"
    assert config.default_output_format == "json"
    assert config.runtime.workspace_root == (tmp_path / "cli-workspace").resolve()
    assert config.runtime.root_dir_name == ".env-root"
    assert config.runtime.metadata_database_name == "env.sqlite3"
    assert config.indexing.fingerprint_salt == "env-salt"
    assert config.semantic_indexing.provider_id == "local-hash"
    assert config.semantic_indexing.model_id == "project-model"
    assert config.semantic_indexing.model_version == "2026-03-14"


def test_load_app_config_keeps_missing_optional_local_config_non_fatal(tmp_path: Path) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """
[tool.codeman]
project_name = "project-default"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = load_app_config(
        pyproject_path=pyproject_path,
        environ={"HOME": str(tmp_path / "home")},
        allow_missing_local_config=True,
    )

    assert config.project_name == "project-default"
    assert config.runtime.root_dir_name == ".codeman"


def test_load_app_config_fails_for_missing_explicit_env_config_path(tmp_path: Path) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """
[tool.codeman]
project_name = "project-default"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationResolutionError) as exc_info:
        load_app_config(
            pyproject_path=pyproject_path,
            environ={"CODEMAN_CONFIG_PATH": str(tmp_path / "missing-config.toml")},
        )

    assert "missing-config.toml" in str(exc_info.value)


def test_load_app_config_fails_for_malformed_local_toml(tmp_path: Path) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """
[tool.codeman]
project_name = "project-default"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    local_config_path = tmp_path / "broken.toml"
    local_config_path.write_text("[runtime\nworkspace_root = 'oops'\n", encoding="utf-8")

    with pytest.raises(ConfigurationResolutionError) as exc_info:
        load_app_config(
            pyproject_path=pyproject_path,
            config_path=local_config_path,
            allow_missing_local_config=False,
        )

    assert "broken.toml" in str(exc_info.value)


def test_load_app_config_fails_for_malformed_project_defaults_toml(tmp_path: Path) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text("[tool.codeman\nproject_name = 'oops'\n", encoding="utf-8")

    with pytest.raises(ConfigurationResolutionError) as exc_info:
        load_app_config(
            pyproject_path=pyproject_path,
            environ={},
        )

    assert "pyproject.toml" in str(exc_info.value)


def test_load_app_config_fails_for_invalid_model_values(tmp_path: Path) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """
[tool.codeman]
project_name = "project-default"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationResolutionError) as exc_info:
        load_app_config(
            pyproject_path=pyproject_path,
            environ={"CODEMAN_SEMANTIC_VECTOR_DIMENSION": "abc"},
        )

    assert "CODEMAN_SEMANTIC_VECTOR_DIMENSION" in str(exc_info.value)
