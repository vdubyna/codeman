"""Shared contract DTOs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class CommandMeta(BaseModel):
    """Metadata attached to future command responses."""

    model_config = ConfigDict(extra="forbid")

    command: str
    output_format: Literal["text", "json"] = "text"


class SuccessEnvelope(BaseModel):
    """Success response envelope placeholder."""

    model_config = ConfigDict(extra="forbid")

    ok: Literal[True] = True
    data: Any
    meta: CommandMeta | None = None
