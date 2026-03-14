import json

import click
from typer.testing import CliRunner

from codeman.bootstrap import bootstrap
from codeman.cli.app import app, get_container

runner = CliRunner()


def test_root_help_lists_expected_command_groups() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command_name in ["repo", "index", "query", "eval", "compare", "config"]:
        assert command_name in result.stdout


def test_get_container_reuses_context_object() -> None:
    container = bootstrap()
    ctx = click.Context(click.Command("codeman"), obj=container)

    resolved = get_container(ctx)

    assert resolved is container


def test_cli_returns_json_failure_when_configuration_is_invalid(tmp_path) -> None:
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()

    result = runner.invoke(
        app,
        ["repo", "register", str(target_repo), "--output-format", "json"],
        env={"CODEMAN_SEMANTIC_VECTOR_DIMENSION": "abc"},
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 18
    assert payload["ok"] is False
    assert payload["error"]["code"] == "configuration_invalid"
    assert "configuration" in payload["error"]["message"].lower()
