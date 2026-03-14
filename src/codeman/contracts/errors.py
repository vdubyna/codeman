"""Error contract DTOs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from codeman.contracts.common import CommandMeta


class ErrorDetail(BaseModel):
    """Stable error payload placeholder."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: Any | None = None


class FailureEnvelope(BaseModel):
    """Failure response envelope placeholder."""

    model_config = ConfigDict(extra="forbid")

    ok: Literal[False] = False
    error: ErrorDetail
    meta: CommandMeta | None = None


class ErrorCode:
    """Stable error-code identifiers for the current CLI surface."""

    REPOSITORY_PATH_NOT_FOUND = "repository_path_not_found"
    REPOSITORY_PATH_NOT_DIRECTORY = "repository_path_not_directory"
    REPOSITORY_PATH_NOT_READABLE = "repository_path_not_readable"
    REPOSITORY_ALREADY_REGISTERED = "repository_already_registered"
    INTERNAL_ERROR = "internal_error"
