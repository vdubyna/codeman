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
vector_engine = "sqlite-exact"
vector_dimension = 8
fingerprint_salt = "project-semantic-salt"

[tool.codeman.embedding_providers.local_hash]
model_id = "project-model"
model_version = "1"
local_model_path = "/tmp/project-model"
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

[embedding_providers.local_hash]
api_key = "local-secret"
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
            "CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_MODEL_ID": "env-model",
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
    assert config.semantic_indexing.vector_engine == "sqlite-exact"
    assert config.embedding_providers.local_hash.model_id == "env-model"
    assert config.embedding_providers.local_hash.model_version == "2026-03-14"
    assert (
        config.embedding_providers.local_hash.local_model_path
        == Path("/tmp/project-model").resolve()
    )
    assert config.embedding_providers.local_hash.api_key is not None
    assert config.embedding_providers.local_hash.api_key.get_secret_value() == "local-secret"


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


def test_load_app_config_rejects_secret_values_in_project_defaults(tmp_path: Path) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """
[tool.codeman.embedding_providers.local_hash]
api_key = "committed-secret"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationResolutionError) as exc_info:
        load_app_config(
            pyproject_path=pyproject_path,
            environ={},
        )

    assert "project defaults" in str(exc_info.value)
    assert "committed-secret" not in str(exc_info.value)


def test_load_app_config_accepts_legacy_semantic_provider_fields_in_file_sources(
    tmp_path: Path,
) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """
[tool.codeman.semantic_indexing]
provider_id = "local-hash"
model_id = "project-legacy-model"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    local_config_path = tmp_path / "local-config.toml"
    local_config_path.write_text(
        """
[semantic_indexing]
model_version = "local-legacy-version"
local_model_path = "/tmp/local-legacy-model"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = load_app_config(
        pyproject_path=pyproject_path,
        config_path=local_config_path,
        allow_missing_local_config=False,
        environ={},
    )

    assert config.semantic_indexing.provider_id == "local-hash"
    assert config.embedding_providers.local_hash.model_id == "project-legacy-model"
    assert config.embedding_providers.local_hash.model_version == "local-legacy-version"
    assert (
        config.embedding_providers.local_hash.local_model_path
        == Path("/tmp/local-legacy-model").resolve()
    )


def test_load_app_config_empty_provider_env_values_clear_lower_precedence_values(
    tmp_path: Path,
) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """
[tool.codeman.semantic_indexing]
provider_id = "local-hash"

[tool.codeman.embedding_providers.local_hash]
model_id = "project-model"
model_version = "project-version"
local_model_path = "/tmp/project-model"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    local_config_path = tmp_path / "local-config.toml"
    local_config_path.write_text(
        """
[embedding_providers.local_hash]
api_key = "local-secret"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = load_app_config(
        pyproject_path=pyproject_path,
        config_path=local_config_path,
        allow_missing_local_config=False,
        environ={
            "CODEMAN_SEMANTIC_PROVIDER_ID": "",
            "CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_MODEL_ID": "",
            "CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_MODEL_VERSION": "",
            "CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_LOCAL_MODEL_PATH": "",
            "CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_API_KEY": "",
        },
    )

    assert config.semantic_indexing.provider_id is None
    assert config.embedding_providers.local_hash.model_id == "hash-embedding"
    assert config.embedding_providers.local_hash.model_version == "1"
    assert config.embedding_providers.local_hash.local_model_path is None
    assert config.embedding_providers.local_hash.api_key is None
