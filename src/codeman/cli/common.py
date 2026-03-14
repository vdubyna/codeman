"""Shared CLI helpers."""

from __future__ import annotations

from enum import StrEnum

import typer

from codeman.contracts.common import CommandMeta, SuccessEnvelope
from codeman.contracts.errors import FailureEnvelope


class OutputFormat(StrEnum):
    """Supported output formats for CLI commands."""

    TEXT = "text"
    JSON = "json"


def build_command_meta(
    command: str, output_format: OutputFormat = OutputFormat.TEXT
) -> CommandMeta:
    """Create command metadata for future JSON output handling."""

    return CommandMeta(command=command, output_format=output_format.value)


def emit_json_response(response: SuccessEnvelope | FailureEnvelope) -> None:
    """Write a JSON envelope to stdout."""

    typer.echo(response.model_dump_json())
