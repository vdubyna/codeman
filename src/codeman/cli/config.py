"""Configuration command group and retrieval-profile management commands."""

from __future__ import annotations

import json
import os

import typer
from pydantic import ValidationError

from codeman.cli.common import (
    OutputFormat,
    build_command_meta,
    emit_failure_response,
    emit_json_response,
)
from codeman.config.configuration_reuse import build_configuration_reuse_lineage
from codeman.config.loader import CONFIG_PRECEDENCE, ConfigOverrides, ConfigurationResolutionError
from codeman.config.paths import resolve_project_pyproject_path, resolve_user_config_path
from codeman.config.provenance import build_effective_config_provenance_payload
from codeman.config.retrieval_profiles import normalize_retrieval_profile_selector
from codeman.contracts.common import SuccessEnvelope
from codeman.contracts.configuration import (
    RetrievalStrategyProfileRecord,
    SaveRetrievalStrategyProfileRequest,
    SelectedRetrievalStrategyProfile,
    ShowRetrievalStrategyProfileRequest,
    ShowRunConfigurationProvenanceRequest,
    ShowRunConfigurationProvenanceResult,
)

app = typer.Typer(help="Configuration inspection and override commands.", no_args_is_help=True)
profile_app = typer.Typer(
    help="Save, list, and inspect reusable retrieval strategy profiles.",
    no_args_is_help=True,
)
provenance_app = typer.Typer(
    help="Inspect persisted run configuration provenance records.",
    no_args_is_help=True,
)
app.add_typer(profile_app, name="profile")
app.add_typer(provenance_app, name="provenance")


@app.callback()
def config_group() -> None:
    """Inspect configuration and runtime defaults."""


@profile_app.callback()
def config_profile_group() -> None:
    """Manage reusable retrieval strategy profiles."""


@provenance_app.callback()
def config_provenance_group() -> None:
    """Inspect persisted configuration provenance."""


def _render_value(value: object | None) -> str:
    if value is None:
        return "unset"
    if value == "":
        return "<empty>"
    return str(value)


def _selected_profile_metadata(
    *,
    selector: str | None,
    profile: RetrievalStrategyProfileRecord | None,
) -> dict[str, str] | None:
    if profile is None:
        return None

    resolved_selector = profile.name
    if selector is not None:
        try:
            resolved_selector = normalize_retrieval_profile_selector(
                selector,
                field_name="selector",
            )
        except ValueError:
            resolved_selector = profile.name

    selected_profile = SelectedRetrievalStrategyProfile(
        selector=resolved_selector,
        name=profile.name,
        profile_id=profile.profile_id,
    )
    return selected_profile.model_dump(mode="json")


def _profile_local_model_path(profile: RetrievalStrategyProfileRecord) -> str | None:
    provider_config = profile.payload.embedding_providers.get_provider_config(profile.provider_id)
    if provider_config is None or provider_config.local_model_path is None:
        return None
    return str(provider_config.local_model_path)


def _profile_detail_lines(profile: RetrievalStrategyProfileRecord) -> list[str]:
    return [
        f"Name: {profile.name}",
        f"Profile ID: {profile.profile_id}",
        f"Provider: {_render_value(profile.provider_id)}",
        f"Model ID: {_render_value(profile.model_id)}",
        f"Model Version: {_render_value(profile.model_version)}",
        f"Vector Engine: {profile.vector_engine}",
        f"Vector Dimension: {profile.vector_dimension}",
        (f"Indexing Fingerprint Salt: {_render_value(profile.payload.indexing.fingerprint_salt)}"),
        (
            "Semantic Fingerprint Salt: "
            f"{_render_value(profile.payload.semantic_indexing.fingerprint_salt)}"
        ),
        f"Local Model Path: {_render_value(_profile_local_model_path(profile))}",
        f"Created At: {profile.created_at.isoformat()}",
    ]


def _render_profile_text(
    *,
    title: str,
    profile: RetrievalStrategyProfileRecord,
    include_payload: bool,
) -> str:
    lines = [title]
    lines.extend(_profile_detail_lines(profile))
    if include_payload:
        lines.extend(
            [
                "Canonical Payload:",
                json.dumps(
                    profile.payload.to_loader_payload(),
                    indent=2,
                    sort_keys=True,
                ),
            ]
        )
    return "\n".join(lines)


def _render_profile_list_text(profiles: list[RetrievalStrategyProfileRecord]) -> str:
    blocks: list[str] = []
    for index, profile in enumerate(profiles, start=1):
        block_lines = [
            f"{index}. {profile.name}",
            f"   profile id: {profile.profile_id}",
            (
                "   provider/model: "
                f"{_render_value(profile.provider_id)} "
                f"{_render_value(profile.model_id)}@{_render_value(profile.model_version)}"
            ),
            f"   vector: {profile.vector_engine} dim={profile.vector_dimension}",
            f"   local model path: {_render_value(_profile_local_model_path(profile))}",
            (
                "   salts: "
                f"indexing={_render_value(profile.payload.indexing.fingerprint_salt)} "
                f"semantic={_render_value(profile.payload.semantic_indexing.fingerprint_salt)}"
            ),
        ]
        blocks.append("\n".join(block_lines))
    return "\n\n".join(blocks)


def _handle_profile_error(
    *,
    error: ConfigurationResolutionError,
    output_format: OutputFormat,
    command_name: str,
) -> None:
    emit_failure_response(
        error_code=error.error_code,
        message=error.message,
        details=error.details,
        exit_code=error.exit_code,
        output_format=output_format,
        command_name=command_name,
    )


def _render_run_provenance_text(result: ShowRunConfigurationProvenanceResult) -> str:
    provenance = result.provenance
    effective_config = json.dumps(
        provenance.effective_config.to_loader_payload(),
        indent=2,
        sort_keys=True,
    )
    workflow_context = json.dumps(
        provenance.workflow_context.model_dump(
            mode="json",
            exclude_none=True,
            exclude_defaults=True,
        ),
        indent=2,
        sort_keys=True,
    )
    lines = [
        f"Run ID: {provenance.run_id}",
        f"Workflow: {provenance.workflow_type}",
        f"Repository ID: {provenance.repository_id}",
        f"Snapshot ID: {_render_value(provenance.snapshot_id)}",
        f"Reuse Kind: {provenance.configuration_reuse.reuse_kind}",
        f"Base Profile ID: {_render_value(provenance.configuration_reuse.base_profile_id)}",
        f"Base Profile Name: {_render_value(provenance.configuration_reuse.base_profile_name)}",
        f"Configuration ID: {provenance.configuration_id}",
        (f"Indexing Config Fingerprint: {_render_value(provenance.indexing_config_fingerprint)}"),
        (f"Semantic Config Fingerprint: {_render_value(provenance.semantic_config_fingerprint)}"),
        f"Provider: {_render_value(provenance.provider_id)}",
        f"Model ID: {_render_value(provenance.model_id)}",
        f"Model Version: {_render_value(provenance.model_version)}",
        f"Created At: {provenance.created_at.isoformat()}",
        "Effective Configuration:",
        effective_config,
        "Workflow Context:",
        workflow_context,
    ]
    return "\n".join(lines)


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
    configuration_reuse = build_configuration_reuse_lineage(
        selected_profile=container.selected_profile,
        effective_config=build_effective_config_provenance_payload(container.config),
    )
    payload["metadata"] = {
        "precedence": list(CONFIG_PRECEDENCE),
        "project_defaults_path": str(project_defaults_path),
        "local_config_path": str(local_config_path),
        "local_config_present": local_config_path.exists(),
        "selected_profile": _selected_profile_metadata(
            selector=bootstrap_state.config_overrides.profile,
            profile=container.selected_profile,
        ),
        "configuration_reuse": configuration_reuse.model_dump(mode="json"),
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
    selected_profile = payload["metadata"]["selected_profile"]
    configuration_reuse = payload["metadata"]["configuration_reuse"]
    selected_profile_line = "Selected profile: none"
    if selected_profile is not None:
        selected_profile_line = (
            f"Selected profile: {selected_profile['name']} ({selected_profile['profile_id']})"
        )
    lines = [
        "Configuration source precedence: " + " -> ".join(payload["metadata"]["precedence"]),
        selected_profile_line,
        f"Configuration reuse: {configuration_reuse['reuse_kind']}",
        f"Base profile id: {_render_value(configuration_reuse['base_profile_id'])}",
        f"Base profile name: {_render_value(configuration_reuse['base_profile_name'])}",
        (
            "Effective configuration id: "
            f"{configuration_reuse['effective_configuration_id']}"
        ),
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


@provenance_app.command("show")
def show_run_provenance(
    ctx: typer.Context,
    run_id: str,
    output_format: OutputFormat = typer.Option(OutputFormat.TEXT, "--output-format"),
) -> None:
    """Show the stored effective configuration provenance for one successful run."""

    from codeman.cli.app import get_container

    container = get_container(ctx)
    try:
        request = ShowRunConfigurationProvenanceRequest(run_id=run_id)
        result = container.show_run_provenance.execute(request)
    except (ConfigurationResolutionError, ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            validation_message = error.errors()[0]["msg"] if error.errors() else str(error)
            error = ConfigurationResolutionError(validation_message.removeprefix("Value error, "))
        elif not isinstance(error, ConfigurationResolutionError):
            error = ConfigurationResolutionError(str(error))
        _handle_profile_error(
            error=error,
            output_format=output_format,
            command_name="config.provenance.show",
        )

    envelope = SuccessEnvelope(
        data=result,
        meta=build_command_meta("config.provenance.show", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    typer.echo(_render_run_provenance_text(result))


@profile_app.command("save")
def save_profile(
    ctx: typer.Context,
    name: str,
    output_format: OutputFormat = typer.Option(OutputFormat.TEXT, "--output-format"),
) -> None:
    """Save the current retrieval-affecting config as a named profile."""

    from codeman.cli.app import get_container

    container = get_container(ctx)
    try:
        normalized_name = normalize_retrieval_profile_selector(name, field_name="name")
        result = container.save_retrieval_strategy_profile.execute(
            SaveRetrievalStrategyProfileRequest(name=normalized_name),
        )
    except (ConfigurationResolutionError, ValidationError, ValueError) as error:
        if not isinstance(error, ConfigurationResolutionError):
            error = ConfigurationResolutionError(str(error))
        _handle_profile_error(
            error=error,
            output_format=output_format,
            command_name="config.profile.save",
        )

    envelope = SuccessEnvelope(
        data=result,
        meta=build_command_meta("config.profile.save", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    title = "Saved retrieval strategy profile."
    if not result.created:
        title = "Retrieval strategy profile already exists with identical content."
    typer.echo(
        _render_profile_text(
            title=title,
            profile=result.profile,
            include_payload=False,
        )
    )


@profile_app.command("list")
def list_profiles(
    ctx: typer.Context,
    output_format: OutputFormat = typer.Option(OutputFormat.TEXT, "--output-format"),
) -> None:
    """List saved retrieval strategy profiles for the current workspace."""

    from codeman.cli.app import get_container

    container = get_container(ctx)
    try:
        result = container.list_retrieval_strategy_profiles.execute()
    except ConfigurationResolutionError as error:
        _handle_profile_error(
            error=error,
            output_format=output_format,
            command_name="config.profile.list",
        )

    envelope = SuccessEnvelope(
        data=result,
        meta=build_command_meta("config.profile.list", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    if not result.profiles:
        typer.echo("No retrieval strategy profiles saved in this workspace.")
        return

    typer.echo(_render_profile_list_text(result.profiles))


@profile_app.command("show")
def show_profile(
    ctx: typer.Context,
    selector: str,
    output_format: OutputFormat = typer.Option(OutputFormat.TEXT, "--output-format"),
) -> None:
    """Show one saved retrieval strategy profile by exact name or stable id."""

    from codeman.cli.app import get_container

    container = get_container(ctx)
    try:
        normalized_selector = normalize_retrieval_profile_selector(
            selector,
            field_name="selector",
        )
        result = container.show_retrieval_strategy_profile.execute(
            ShowRetrievalStrategyProfileRequest(selector=normalized_selector),
        )
    except (ConfigurationResolutionError, ValidationError, ValueError) as error:
        if not isinstance(error, ConfigurationResolutionError):
            error = ConfigurationResolutionError(str(error))
        _handle_profile_error(
            error=error,
            output_format=output_format,
            command_name="config.profile.show",
        )

    envelope = SuccessEnvelope(
        data=result,
        meta=build_command_meta("config.profile.show", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    typer.echo(
        _render_profile_text(
            title="Retrieval strategy profile.",
            profile=result.profile,
            include_payload=True,
        )
    )
