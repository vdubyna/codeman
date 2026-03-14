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
        },
    )

    assert result.exit_code == 0, result.stdout
    assert (
        "Configuration source precedence: "
        "project_defaults -> local_config -> cli_overrides -> environment"
    ) in result.stdout
    assert f"Workspace root: {workspace.resolve()}" in result.stdout
    assert "Local config present: no" in result.stdout
    assert "Semantic provider id: local-hash" in result.stdout
    assert f"Semantic local model path: {local_model_path.resolve()}" in result.stdout


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
        "cli_overrides",
        "environment",
    ]


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
