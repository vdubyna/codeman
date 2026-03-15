"""Root Typer application."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer

from codeman.bootstrap import BootstrapContainer, bootstrap
from codeman.cli import compare, config, eval, index, query, repo
from codeman.cli.common import OutputFormat, emit_failure_response
from codeman.config.loader import ConfigOverrides, ConfigurationResolutionError


@dataclass(slots=True)
class CliBootstrapState:
    """Deferred bootstrap inputs collected from root CLI options."""

    config_overrides: ConfigOverrides
    allow_missing_local_config: bool = True


def _command_name_from_context(ctx: typer.Context) -> str:
    parts: list[str] = []
    current: typer.Context | None = ctx
    while current is not None:
        if current.info_name:
            parts.append(current.info_name)
        current = current.parent

    ordered_parts = list(reversed(parts))
    if len(ordered_parts) > 1:
        ordered_parts = ordered_parts[1:]
    return ".".join(ordered_parts) or "codeman"


def create_app() -> typer.Typer:
    """Build the root CLI application."""

    app = typer.Typer(
        help="codeman CLI for repository retrieval experiments.",
        no_args_is_help=True,
        pretty_exceptions_show_locals=False,
    )

    @app.callback()
    def app_callback(
        ctx: typer.Context,
        config_path: Path | None = typer.Option(
            None,
            "--config-path",
            help="Use an explicit local config TOML file for this invocation.",
        ),
        profile: str | None = typer.Option(
            None,
            "--profile",
            help="Apply a saved retrieval strategy profile before CLI/environment overrides.",
        ),
        workspace_root: Path | None = typer.Option(
            None,
            "--workspace-root",
            help="Override the workspace root used for `.codeman/` runtime data.",
        ),
        runtime_root_dir: str | None = typer.Option(
            None,
            "--runtime-root-dir",
            help="Override the runtime root directory name under the workspace.",
        ),
        metadata_database_name: str | None = typer.Option(
            None,
            "--metadata-database-name",
            help="Override the runtime metadata database filename.",
        ),
    ) -> None:
        """Initialize shared CLI context."""

        if isinstance(ctx.obj, BootstrapContainer):
            return

        ctx.obj = CliBootstrapState(
            config_overrides=ConfigOverrides(
                config_path=config_path.resolve() if config_path is not None else None,
                profile=profile,
                workspace_root=workspace_root.resolve() if workspace_root is not None else None,
                runtime_root_dir=runtime_root_dir,
                metadata_database_name=metadata_database_name,
            ),
            allow_missing_local_config=config_path is None,
        )

    app.add_typer(repo.app, name="repo")
    app.add_typer(index.app, name="index")
    app.add_typer(query.app, name="query")
    app.add_typer(eval.app, name="eval")
    app.add_typer(compare.app, name="compare")
    app.add_typer(config.app, name="config")

    return app


app = create_app()


def get_container(ctx: typer.Context) -> BootstrapContainer:
    """Return the shared bootstrap container for the current command invocation."""

    if isinstance(ctx.obj, BootstrapContainer):
        return ctx.obj

    output_format = ctx.params.get("output_format", OutputFormat.TEXT)
    if not isinstance(output_format, OutputFormat):
        output_format = OutputFormat(str(output_format))

    state = (
        ctx.obj
        if isinstance(ctx.obj, CliBootstrapState)
        else CliBootstrapState(config_overrides=ConfigOverrides())
    )

    try:
        container = bootstrap(
            cli_overrides=state.config_overrides,
            allow_missing_local_config=state.allow_missing_local_config,
        )
    except ConfigurationResolutionError as error:
        emit_failure_response(
            error_code=error.error_code,
            message=error.message,
            details=error.details,
            exit_code=error.exit_code,
            output_format=output_format,
            command_name=_command_name_from_context(ctx),
        )

    ctx.obj = container
    return container


def main() -> None:
    """Console script entrypoint."""

    app()
