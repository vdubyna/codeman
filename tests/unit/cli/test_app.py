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
