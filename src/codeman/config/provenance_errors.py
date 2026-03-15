"""Typed run-provenance lookup errors for configuration inspection surfaces."""

from __future__ import annotations

from codeman.config.loader import ConfigurationResolutionError
from codeman.contracts.errors import ErrorCode


class RunConfigurationProvenanceNotFoundError(ConfigurationResolutionError):
    """Raised when a requested run provenance record does not exist."""

    exit_code = 58
    error_code = ErrorCode.CONFIGURATION_PROVENANCE_NOT_FOUND
