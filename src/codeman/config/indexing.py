"""Narrow indexing policy configuration and fingerprint helpers."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

CHUNK_SERIALIZATION_VERSION = "1"
INDEXING_FINGERPRINT_SCHEMA_VERSION = "1"
SOURCE_DISCOVERY_POLICY_VERSION = "git-aware-supported-source-files-v1"
PARSER_POLICY_VERSIONS = {
    "html": "html-parser-v1",
    "javascript": "javascript-parser-v1",
    "php": "php-parser-v1",
    "twig": "twig-parser-v1",
}
CHUNKER_POLICY_VERSIONS = {
    "html_fallback": "html-fallback-v1",
    "html_structure": "html-structure-v1",
    "javascript_fallback": "javascript-fallback-v1",
    "javascript_structure": "javascript-structure-v1",
    "php_fallback": "php-fallback-v1",
    "php_structure": "php-structure-v1",
    "twig_fallback": "twig-fallback-v1",
    "twig_structure": "twig-structure-v1",
}


class IndexingConfig(BaseModel):
    """Minimal indexing configuration needed for current attribution."""

    model_config = ConfigDict(extra="forbid")

    fingerprint_salt: str = Field(
        default_factory=lambda: os.environ.get("CODEMAN_INDEXING_FINGERPRINT_SALT", ""),
    )


def build_indexing_policy_descriptor(config: IndexingConfig) -> dict[str, Any]:
    """Return the normalized fingerprint payload for the current indexing policy."""

    return {
        "schema_version": INDEXING_FINGERPRINT_SCHEMA_VERSION,
        "source_discovery_policy_version": SOURCE_DISCOVERY_POLICY_VERSION,
        "chunk_serialization_version": CHUNK_SERIALIZATION_VERSION,
        "parser_policies": dict(sorted(PARSER_POLICY_VERSIONS.items())),
        "chunker_policies": dict(sorted(CHUNKER_POLICY_VERSIONS.items())),
        "cli_knobs": {
            "fingerprint_salt": config.fingerprint_salt,
        },
    }


def build_indexing_fingerprint(config: IndexingConfig) -> str:
    """Build a deterministic fingerprint for the current indexing policy."""

    descriptor = build_indexing_policy_descriptor(config)
    encoded = json.dumps(
        descriptor,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
