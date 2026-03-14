"""Layered configuration resolution helpers."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from pydantic import ValidationError

from codeman.config.defaults import IN_CODE_DEFAULTS, load_project_defaults
from codeman.config.models import AppConfig
from codeman.config.paths import resolve_project_pyproject_path, resolve_user_config_path
from codeman.contracts.errors import ErrorCode

CONFIG_PRECEDENCE = (
    "project_defaults",
    "local_config",
    "cli_overrides",
    "environment",
)


@dataclass(frozen=True, slots=True)
class ResolvedLocalConfigPath:
    """Resolved local-config path plus whether the source was explicit."""

    path: Path
    is_explicit: bool


class ConfigurationResolutionError(Exception):
    """Raised when configuration sources cannot be resolved into one valid app config."""

    exit_code = 18
    error_code = ErrorCode.CONFIGURATION_INVALID

    def __init__(
        self,
        message: str,
        *,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


@dataclass(slots=True)
class ConfigOverrides:
    """CLI-supplied configuration overrides for the current invocation."""

    config_path: Path | None = None
    workspace_root: Path | None = None
    runtime_root_dir: str | None = None
    metadata_database_name: str | None = None


def _merge_nested_dicts(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = {**base}
    for key, value in override.items():
        if isinstance(merged.get(key), dict) and isinstance(value, Mapping):
            merged[key] = _merge_nested_dicts(merged[key], value)
            continue
        merged[key] = value
    return merged


def _read_toml_file(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as file_handle:
            data = tomllib.load(file_handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationResolutionError(
            f"Configuration file is not valid TOML: {path}",
            details={"path": str(path)},
        ) from exc
    except OSError as exc:
        raise ConfigurationResolutionError(
            f"Configuration file could not be read: {path}",
            details={"path": str(path)},
        ) from exc

    if not isinstance(data, dict):
        raise ConfigurationResolutionError(
            f"Configuration file must decode to a TOML table: {path}",
            details={"path": str(path)},
        )
    return data


def _build_cli_override_payload(cli_overrides: ConfigOverrides) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    runtime_payload: dict[str, Any] = {}

    if cli_overrides.workspace_root is not None:
        runtime_payload["workspace_root"] = cli_overrides.workspace_root.resolve()
    if cli_overrides.runtime_root_dir is not None:
        runtime_payload["root_dir_name"] = cli_overrides.runtime_root_dir
    if cli_overrides.metadata_database_name is not None:
        runtime_payload["metadata_database_name"] = cli_overrides.metadata_database_name

    if runtime_payload:
        payload["runtime"] = runtime_payload
    return payload


def _build_environment_override_payload(environment: Mapping[str, str]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    runtime_payload: dict[str, Any] = {}
    indexing_payload: dict[str, Any] = {}
    semantic_payload: dict[str, Any] = {}

    if workspace_root := environment.get("CODEMAN_WORKSPACE_ROOT"):
        runtime_payload["workspace_root"] = Path(workspace_root).expanduser().resolve()
    if runtime_root_dir := environment.get("CODEMAN_RUNTIME_ROOT_DIR"):
        runtime_payload["root_dir_name"] = runtime_root_dir
    if metadata_database_name := environment.get("CODEMAN_METADATA_DATABASE_NAME"):
        runtime_payload["metadata_database_name"] = metadata_database_name

    if indexing_fingerprint_salt := environment.get("CODEMAN_INDEXING_FINGERPRINT_SALT"):
        indexing_payload["fingerprint_salt"] = indexing_fingerprint_salt

    if semantic_provider_id := environment.get("CODEMAN_SEMANTIC_PROVIDER_ID"):
        semantic_payload["provider_id"] = semantic_provider_id
    if semantic_model_id := environment.get("CODEMAN_SEMANTIC_MODEL_ID"):
        semantic_payload["model_id"] = semantic_model_id
    if semantic_model_version := environment.get("CODEMAN_SEMANTIC_MODEL_VERSION"):
        semantic_payload["model_version"] = semantic_model_version
    if semantic_local_model_path := environment.get("CODEMAN_SEMANTIC_LOCAL_MODEL_PATH"):
        semantic_payload["local_model_path"] = (
            Path(semantic_local_model_path).expanduser().resolve()
        )
    if semantic_vector_engine := environment.get("CODEMAN_SEMANTIC_VECTOR_ENGINE"):
        semantic_payload["vector_engine"] = semantic_vector_engine
    if semantic_vector_dimension := environment.get("CODEMAN_SEMANTIC_VECTOR_DIMENSION"):
        semantic_payload["vector_dimension"] = semantic_vector_dimension
    if semantic_fingerprint_salt := environment.get("CODEMAN_SEMANTIC_FINGERPRINT_SALT"):
        semantic_payload["fingerprint_salt"] = semantic_fingerprint_salt

    if runtime_payload:
        payload["runtime"] = runtime_payload
    if indexing_payload:
        payload["indexing"] = indexing_payload
    if semantic_payload:
        payload["semantic_indexing"] = semantic_payload
    return payload


def _build_dynamic_defaults() -> dict[str, Any]:
    return {
        "runtime": {
            "workspace_root": Path.cwd().resolve(),
        }
    }


def _resolve_local_config_path(
    *,
    config_path: Path | None,
    cli_overrides: ConfigOverrides,
    environment: Mapping[str, str],
) -> ResolvedLocalConfigPath:
    explicit_path = config_path or cli_overrides.config_path
    if explicit_path is not None:
        return ResolvedLocalConfigPath(
            path=resolve_user_config_path(explicit_path),
            is_explicit=True,
        )

    if environment.get("CODEMAN_CONFIG_PATH"):
        return ResolvedLocalConfigPath(
            path=resolve_user_config_path(env=environment),
            is_explicit=True,
        )

    return ResolvedLocalConfigPath(
        path=resolve_user_config_path(env=environment),
        is_explicit=False,
    )


def load_app_config(
    *,
    pyproject_path: Path | None = None,
    config_path: Path | None = None,
    cli_overrides: ConfigOverrides | None = None,
    allow_missing_local_config: bool = True,
    environ: Mapping[str, str] | None = None,
) -> AppConfig:
    """Resolve the effective application configuration using the supported layer order."""

    environment = environ if environ is not None else os.environ
    overrides = cli_overrides or ConfigOverrides()
    resolved_pyproject_path = pyproject_path or resolve_project_pyproject_path()
    resolved_local_config = _resolve_local_config_path(
        config_path=config_path,
        cli_overrides=overrides,
        environment=environment,
    )

    merged_payload = _merge_nested_dicts(IN_CODE_DEFAULTS, _build_dynamic_defaults())
    try:
        project_defaults = load_project_defaults(resolved_pyproject_path)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationResolutionError(
            f"Project defaults file is not valid TOML: {resolved_pyproject_path}",
            details={"path": str(resolved_pyproject_path)},
        ) from exc
    except OSError as exc:
        raise ConfigurationResolutionError(
            f"Project defaults file could not be read: {resolved_pyproject_path}",
            details={"path": str(resolved_pyproject_path)},
        ) from exc

    merged_payload = _merge_nested_dicts(
        merged_payload,
        project_defaults,
    )

    if resolved_local_config.path.exists():
        merged_payload = _merge_nested_dicts(
            merged_payload,
            _read_toml_file(resolved_local_config.path),
        )
    elif resolved_local_config.is_explicit or not allow_missing_local_config:
        raise ConfigurationResolutionError(
            f"Configuration file does not exist: {resolved_local_config.path}",
            details={"path": str(resolved_local_config.path)},
        )

    merged_payload = _merge_nested_dicts(
        merged_payload,
        _build_cli_override_payload(overrides),
    )
    merged_payload = _merge_nested_dicts(
        merged_payload,
        _build_environment_override_payload(environment),
    )

    try:
        return AppConfig.model_validate(merged_payload)
    except ValidationError as exc:
        details = exc.errors(
            include_url=False,
            include_context=False,
            include_input=False,
        )
        message = "Resolved configuration is invalid."
        if details:
            message = f"{message} {details[0]['msg']}"
        raise ConfigurationResolutionError(
            message,
            details=details,
        ) from exc


__all__ = [
    "CONFIG_PRECEDENCE",
    "ConfigOverrides",
    "ConfigurationResolutionError",
    "load_app_config",
]
