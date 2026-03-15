from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from codeman.cli.app import app

runner = CliRunner()


def test_config_show_renders_text_output(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()

    result = runner.invoke(
        app,
        ["--workspace-root", str(workspace), "config", "show"],
        env={
            "CODEMAN_SEMANTIC_PROVIDER_ID": "local-hash",
            "CODEMAN_SEMANTIC_LOCAL_MODEL_PATH": str(local_model_path),
            "CODEMAN_SEMANTIC_MODEL_VERSION": "2026-03-14",
            "CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_API_KEY": "super-secret",
        },
    )

    assert result.exit_code == 0, result.stdout
    assert (
        "Configuration source precedence: "
        "project_defaults -> local_config -> selected_profile -> cli_overrides -> environment"
    ) in result.stdout
    assert f"Workspace root: {workspace.resolve()}" in result.stdout
    assert "Local config present: no" in result.stdout
    assert "Semantic provider id: local-hash" in result.stdout
    assert "Embedding provider local-hash model version: 2026-03-14" in result.stdout
    assert (
        f"Embedding provider local-hash local model path: {local_model_path.resolve()}"
        in result.stdout
    )
    assert "Embedding provider local-hash api key configured: yes" in result.stdout
    assert "super-secret" not in result.stdout


def test_config_show_renders_json_output(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = runner.invoke(
        app,
        ["--workspace-root", str(workspace), "config", "show", "--output-format", "json"],
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 0, result.stdout
    assert payload["ok"] is True
    assert payload["meta"]["command"] == "config.show"
    assert payload["data"]["runtime"]["workspace_root"] == str(workspace.resolve())
    assert payload["data"]["metadata"]["local_config_present"] is False
    assert payload["data"]["metadata"]["precedence"] == [
        "project_defaults",
        "local_config",
        "selected_profile",
        "cli_overrides",
        "environment",
    ]
    assert payload["data"]["semantic_indexing"]["model_id"] == "hash-embedding"
    assert payload["data"]["semantic_indexing"]["model_version"] == "1"
    assert payload["data"]["semantic_indexing"]["local_model_path"] is None
    assert payload["data"]["embedding_providers"]["local_hash"]["model_id"] == "hash-embedding"
    assert payload["data"]["embedding_providers"]["local_hash"]["api_key_configured"] is False


def test_config_show_redacts_provider_secrets_in_json_output(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = runner.invoke(
        app,
        ["--workspace-root", str(workspace), "config", "show", "--output-format", "json"],
        env={"CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_API_KEY": "super-secret"},
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 0, result.stdout
    assert payload["data"]["embedding_providers"]["local_hash"]["api_key_configured"] is True
    assert "api_key" not in payload["data"]["embedding_providers"]["local_hash"]
    assert "super-secret" not in result.stdout


def test_config_show_returns_json_failure_for_invalid_configuration() -> None:
    result = runner.invoke(
        app,
        ["config", "show", "--output-format", "json"],
        env={"CODEMAN_SEMANTIC_VECTOR_DIMENSION": "abc"},
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 18
    assert payload["ok"] is False
    assert payload["error"]["code"] == "configuration_invalid"


def test_config_profile_commands_support_save_list_show_and_selected_profile(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    env = {
        "CODEMAN_SEMANTIC_PROVIDER_ID": "local-hash",
        "CODEMAN_SEMANTIC_LOCAL_MODEL_PATH": str(local_model_path),
        "CODEMAN_SEMANTIC_MODEL_ID": "fixture-local",
        "CODEMAN_SEMANTIC_MODEL_VERSION": "2026-03-14",
        "CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_API_KEY": "super-secret",
    }

    save_result = runner.invoke(
        app,
        [
            "--workspace-root",
            str(workspace),
            "config",
            "profile",
            "save",
            "  fixture-profile  ",
        ],
        env=env,
    )
    list_result = runner.invoke(
        app,
        [
            "--workspace-root",
            str(workspace),
            "config",
            "profile",
            "list",
            "--output-format",
            "json",
        ],
    )
    show_result = runner.invoke(
        app,
        [
            "--workspace-root",
            str(workspace),
            "config",
            "profile",
            "show",
            "  fixture-profile  ",
        ],
    )
    selected_show_result = runner.invoke(
        app,
        [
            "--workspace-root",
            str(workspace),
            "--profile",
            "  fixture-profile  ",
            "config",
            "show",
            "--output-format",
            "json",
        ],
    )

    list_payload = json.loads(list_result.stdout)
    selected_show_payload = json.loads(selected_show_result.stdout)

    assert save_result.exit_code == 0, save_result.stdout
    assert "Saved retrieval strategy profile." in save_result.stdout
    assert "Name: fixture-profile" in save_result.stdout
    assert "super-secret" not in save_result.stdout
    assert list_result.exit_code == 0, list_result.stdout
    assert list_payload["ok"] is True
    assert list_payload["data"]["profiles"][0]["name"] == "fixture-profile"
    assert show_result.exit_code == 0, show_result.stdout
    assert "Canonical Payload:" in show_result.stdout
    assert "fixture-profile" in show_result.stdout
    assert "super-secret" not in show_result.stdout
    assert selected_show_result.exit_code == 0, selected_show_result.stdout
    assert selected_show_payload["data"]["metadata"]["precedence"] == [
        "project_defaults",
        "local_config",
        "selected_profile",
        "cli_overrides",
        "environment",
    ]
    assert (
        selected_show_payload["data"]["metadata"]["selected_profile"]["name"]
        == "fixture-profile"
    )
    assert (
        selected_show_payload["data"]["metadata"]["selected_profile"]["selector"]
        == "fixture-profile"
    )
    assert selected_show_payload["data"]["semantic_indexing"]["model_id"] == "fixture-local"
    assert (
        selected_show_payload["data"]["embedding_providers"]["local_hash"]["api_key_configured"]
        is False
    )


def test_config_profile_save_rejects_blank_profile_names_without_creating_runtime_metadata(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = runner.invoke(
        app,
        [
            "--workspace-root",
            str(workspace),
            "config",
            "profile",
            "save",
            "   ",
            "--output-format",
            "json",
        ],
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 18
    assert payload["ok"] is False
    assert payload["error"]["code"] == "configuration_invalid"
    assert payload["error"]["message"] == "Retrieval strategy profile name must not be blank."
    assert not (workspace / ".codeman" / "metadata.sqlite3").exists()


def test_config_profile_list_does_not_create_runtime_metadata_in_empty_workspace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = runner.invoke(
        app,
        [
            "--workspace-root",
            str(workspace),
            "config",
            "profile",
            "list",
            "--output-format",
            "json",
        ],
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 0, result.stdout
    assert payload["ok"] is True
    assert payload["data"]["profiles"] == []
    assert not (workspace / ".codeman" / "metadata.sqlite3").exists()


def test_config_profile_save_rejects_duplicate_name_with_different_content(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()

    first_result = runner.invoke(
        app,
        ["--workspace-root", str(workspace), "config", "profile", "save", "fixture-profile"],
        env={
            "CODEMAN_SEMANTIC_PROVIDER_ID": "local-hash",
            "CODEMAN_SEMANTIC_LOCAL_MODEL_PATH": str(local_model_path),
            "CODEMAN_SEMANTIC_MODEL_ID": "fixture-local",
            "CODEMAN_SEMANTIC_MODEL_VERSION": "2026-03-14",
        },
    )
    second_result = runner.invoke(
        app,
        [
            "--workspace-root",
            str(workspace),
            "config",
            "profile",
            "save",
            "fixture-profile",
            "--output-format",
            "json",
        ],
        env={
            "CODEMAN_SEMANTIC_PROVIDER_ID": "local-hash",
            "CODEMAN_SEMANTIC_LOCAL_MODEL_PATH": str(local_model_path),
            "CODEMAN_SEMANTIC_MODEL_ID": "fixture-local",
            "CODEMAN_SEMANTIC_MODEL_VERSION": "2026-03-15",
        },
    )

    payload = json.loads(second_result.stdout)

    assert first_result.exit_code == 0, first_result.stdout
    assert second_result.exit_code == 56
    assert payload["ok"] is False
    assert payload["error"]["code"] == "configuration_profile_name_conflict"


def test_config_profile_show_rejects_ambiguous_profile_id_selection(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    env = {
        "CODEMAN_SEMANTIC_PROVIDER_ID": "local-hash",
        "CODEMAN_SEMANTIC_LOCAL_MODEL_PATH": str(local_model_path),
        "CODEMAN_SEMANTIC_MODEL_ID": "fixture-local",
        "CODEMAN_SEMANTIC_MODEL_VERSION": "2026-03-14",
    }

    first_result = runner.invoke(
        app,
        ["--workspace-root", str(workspace), "config", "profile", "save", "alpha"],
        env=env,
    )
    second_result = runner.invoke(
        app,
        ["--workspace-root", str(workspace), "config", "profile", "save", "beta"],
        env=env,
    )
    list_result = runner.invoke(
        app,
        [
            "--workspace-root",
            str(workspace),
            "config",
            "profile",
            "list",
            "--output-format",
            "json",
        ],
    )
    list_payload = json.loads(list_result.stdout)
    shared_profile_id = list_payload["data"]["profiles"][0]["profile_id"]

    show_result = runner.invoke(
        app,
        [
            "--workspace-root",
            str(workspace),
            "config",
            "profile",
            "show",
            shared_profile_id,
            "--output-format",
            "json",
        ],
    )

    payload = json.loads(show_result.stdout)

    assert first_result.exit_code == 0, first_result.stdout
    assert second_result.exit_code == 0, second_result.stdout
    assert show_result.exit_code == 57
    assert payload["ok"] is False
    assert payload["error"]["code"] == "configuration_profile_ambiguous"
