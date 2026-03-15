"""Typed retrieval-profile errors shared by config resolution and CLI commands."""

from __future__ import annotations

from codeman.config.loader import ConfigurationResolutionError
from codeman.contracts.errors import ErrorCode


class RetrievalStrategyProfileNotFoundError(ConfigurationResolutionError):
    """Raised when a selected retrieval profile does not exist."""

    exit_code = 55
    error_code = ErrorCode.CONFIGURATION_PROFILE_NOT_FOUND


class RetrievalStrategyProfileNameConflictError(ConfigurationResolutionError):
    """Raised when a profile name already exists with different content."""

    exit_code = 56
    error_code = ErrorCode.CONFIGURATION_PROFILE_NAME_CONFLICT


class RetrievalStrategyProfileAmbiguousError(ConfigurationResolutionError):
    """Raised when a selector matches more than one stored profile."""

    exit_code = 57
    error_code = ErrorCode.CONFIGURATION_PROFILE_AMBIGUOUS
