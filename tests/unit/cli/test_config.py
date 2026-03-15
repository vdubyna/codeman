from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from codeman.cli.app import app
from codeman.config.retrieval_profiles import RetrievalStrategyProfilePayload
from codeman.contracts.configuration import (
    RunConfigurationProvenanceRecord,
    RunProvenanceWorkflowContext,
)

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
    assert payload["data"]["metadata"]["configuration_reuse"]["reuse_kind"] == "ad_hoc"
    assert payload["data"]["metadata"]["configuration_reuse"]["base_profile_id"] is None
    assert payload["data"]["metadata"]["configuration_reuse"]["effective_configuration_id"]


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
        selected_show_payload["data"]["metadata"]["selected_profile"]["name"] == "fixture-profile"
    )
    assert (
        selected_show_payload["data"]["metadata"]["selected_profile"]["selector"]
        == "fixture-profile"
    )
    assert (
        selected_show_payload["data"]["metadata"]["configuration_reuse"]["reuse_kind"]
        == "profile_reuse"
    )
    assert (
        selected_show_payload["data"]["metadata"]["configuration_reuse"]["base_profile_id"]
        == selected_show_payload["data"]["metadata"]["selected_profile"]["profile_id"]
    )
    assert selected_show_payload["data"]["semantic_indexing"]["model_id"] == "fixture-local"
    assert (
        selected_show_payload["data"]["embedding_providers"]["local_hash"]["api_key_configured"]
        is False
    )


def test_config_show_marks_selected_profile_overrides_as_modified_reuse(tmp_path: Path) -> None:
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

    save_result = runner.invoke(
        app,
        [
            "--workspace-root",
            str(workspace),
            "config",
            "profile",
            "save",
            "fixture-profile",
        ],
        env=env,
    )
    modified_show_result = runner.invoke(
        app,
        [
            "--workspace-root",
            str(workspace),
            "--profile",
            "fixture-profile",
            "config",
            "show",
            "--output-format",
            "json",
        ],
        env={**env, "CODEMAN_INDEXING_FINGERPRINT_SALT": "profile-v2"},
    )

    payload = json.loads(modified_show_result.stdout)

    assert save_result.exit_code == 0, save_result.stdout
    assert modified_show_result.exit_code == 0, modified_show_result.stdout
    assert payload["data"]["metadata"]["configuration_reuse"]["reuse_kind"] == (
        "modified_profile_reuse"
    )
    assert (
        payload["data"]["metadata"]["configuration_reuse"]["base_profile_name"]
        == "fixture-profile"
    )
    assert (
        payload["data"]["metadata"]["configuration_reuse"]["effective_configuration_id"]
        != payload["data"]["metadata"]["selected_profile"]["profile_id"]
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


def test_config_provenance_show_renders_json_output(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    database_path = workspace / ".codeman" / "metadata.sqlite3"

    from codeman.infrastructure.persistence.sqlite.engine import create_sqlite_engine
    from codeman.infrastructure.persistence.sqlite.repositories.run_provenance_repository import (
        SqliteRunProvenanceStore,
    )

    store = SqliteRunProvenanceStore(
        engine=create_sqlite_engine(database_path),
        database_path=database_path,
    )
    store.initialize()
    store.create_record(
        RunConfigurationProvenanceRecord(
            run_id="run-123",
            workflow_type="query.semantic",
            repository_id="repo-123",
            snapshot_id="snapshot-123",
            configuration_id="config-123",
            semantic_config_fingerprint="semantic-fingerprint-123",
            provider_id="local-hash",
            model_id="fixture-local",
            model_version="2026-03-15",
            effective_config=RetrievalStrategyProfilePayload.model_validate(
                {
                    "indexing": {"fingerprint_salt": "indexing-salt"},
                    "semantic_indexing": {
                        "provider_id": "local-hash",
                        "vector_engine": "sqlite-exact",
                        "vector_dimension": 16,
                    },
                    "embedding_providers": {
                        "local_hash": {
                            "model_id": "fixture-local",
                            "model_version": "2026-03-15",
                            "local_model_path": str((tmp_path / "local-model").resolve()),
                        }
                    },
                }
            ),
            workflow_context=RunProvenanceWorkflowContext(
                semantic_build_id="semantic-build-123",
                max_results=5,
            ),
            created_at=datetime(2026, 3, 15, 7, 0, tzinfo=UTC),
        )
    )

    result = runner.invoke(
        app,
        [
            "--workspace-root",
            str(workspace),
            "config",
            "provenance",
            "show",
            "run-123",
            "--output-format",
            "json",
        ],
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 0, result.stdout
    assert payload["ok"] is True
    assert payload["meta"]["command"] == "config.provenance.show"
    assert payload["data"]["provenance"]["run_id"] == "run-123"
    assert payload["data"]["provenance"]["configuration_id"] == "config-123"
    assert payload["data"]["provenance"]["configuration_reuse"]["reuse_kind"] == "ad_hoc"
    assert payload["data"]["provenance"]["workflow_context"]["semantic_build_id"] == (
        "semantic-build-123"
    )


def test_config_provenance_show_returns_stable_failure_for_missing_run_id(
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
            "provenance",
            "show",
            "missing-run",
            "--output-format",
            "json",
        ],
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 58
    assert payload["ok"] is False
    assert payload["error"]["code"] == "configuration_provenance_not_found"
    assert not (workspace / ".codeman" / "metadata.sqlite3").exists()


def test_config_provenance_show_rejects_blank_run_id_with_stable_configuration_failure(
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
            "provenance",
            "show",
            "   ",
            "--output-format",
            "json",
        ],
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 18
    assert payload["ok"] is False
    assert payload["error"]["code"] == "configuration_invalid"
    assert payload["error"]["message"] == "Run provenance id must not be blank."
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
