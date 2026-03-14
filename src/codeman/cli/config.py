"""Configuration command group placeholder."""

from __future__ import annotations

import os

import typer

from codeman.cli.common import OutputFormat, build_command_meta, emit_json_response
from codeman.config.loader import CONFIG_PRECEDENCE, ConfigOverrides
from codeman.config.paths import resolve_project_pyproject_path, resolve_user_config_path
from codeman.contracts.common import SuccessEnvelope

app = typer.Typer(help="Configuration inspection and override commands.", no_args_is_help=True)


@app.callback()
def config_group() -> None:
    """Inspect configuration and runtime defaults."""


def _render_value(value: object | None) -> str:
    if value is None:
        return "unset"
    if value == "":
        return "<empty>"
    return str(value)


@app.command("show")
def show_config(
    ctx: typer.Context,
    output_format: OutputFormat = typer.Option(OutputFormat.TEXT, "--output-format"),
) -> None:
    """Show the effective resolved configuration for the current invocation."""

    from codeman.cli.app import CliBootstrapState, get_container

    bootstrap_state = (
        ctx.obj
        if isinstance(ctx.obj, CliBootstrapState)
        else CliBootstrapState(config_overrides=ConfigOverrides())
    )
    container = get_container(ctx)

    project_defaults_path = resolve_project_pyproject_path()
    local_config_path = resolve_user_config_path(
        bootstrap_state.config_overrides.config_path,
        env=os.environ,
    )
    payload = container.config.to_operator_payload()
    payload["metadata"] = {
        "precedence": list(CONFIG_PRECEDENCE),
        "project_defaults_path": str(project_defaults_path),
        "local_config_path": str(local_config_path),
        "local_config_present": local_config_path.exists(),
    }

    envelope = SuccessEnvelope(
        data=payload,
        meta=build_command_meta("config.show", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    runtime = payload["runtime"]
    indexing = payload["indexing"]
    semantic = payload["semantic_indexing"]
    embedding_providers = payload["embedding_providers"]
    lines = [
        "Configuration source precedence: " + " -> ".join(payload["metadata"]["precedence"]),
        f"Project defaults file: {payload['metadata']['project_defaults_path']}",
        f"Local config file: {payload['metadata']['local_config_path']}",
        (
            "Local config present: "
            + ("yes" if payload["metadata"]["local_config_present"] else "no")
        ),
        f"Project name: {payload['project_name']}",
        f"Default output format: {payload['default_output_format']}",
        f"Workspace root: {runtime['workspace_root']}",
        f"Runtime root dir: {runtime['root_dir_name']}",
        f"Metadata database name: {runtime['metadata_database_name']}",
        f"Indexing fingerprint salt: {_render_value(indexing['fingerprint_salt'])}",
        f"Semantic provider id: {_render_value(semantic['provider_id'])}",
        f"Semantic vector engine: {semantic['vector_engine']}",
        f"Semantic vector dimension: {semantic['vector_dimension']}",
        f"Semantic fingerprint salt: {_render_value(semantic['fingerprint_salt'])}",
    ]
    for provider_key, provider_payload in embedding_providers.items():
        provider_id = provider_key.replace("_", "-")
        lines.extend(
            [
                f"Embedding provider {provider_id} model id: {provider_payload['model_id']}",
                "Embedding provider "
                f"{provider_id} model version: {provider_payload['model_version']}",
                "Embedding provider "
                f"{provider_id} local model path: "
                f"{_render_value(provider_payload['local_model_path'])}",
                "Embedding provider "
                f"{provider_id} api key configured: "
                + ("yes" if provider_payload["api_key_configured"] else "no"),
            ]
        )
    typer.echo("\n".join(lines))
