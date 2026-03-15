"""Benchmark dataset contracts and deterministic dataset helpers."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codeman.contracts.repository import SourceLanguage

BENCHMARK_DATASET_SCHEMA_VERSION = "1"


def _normalize_required_text(value: str | None, *, field_name: str) -> str:
    """Trim and validate required authored text fields."""

    if value is None:
        raise ValueError(f"{field_name} must not be blank.")

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank.")
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    """Trim optional text fields and collapse blanks to None."""

    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def normalize_benchmark_relative_path(value: str | Path) -> str:
    """Normalize authored benchmark locators to stable repository-relative POSIX paths."""

    candidate = str(value).strip().replace("\\", "/")
    if not candidate:
        raise ValueError("relative_path must not be blank.")

    path = PurePosixPath(candidate)
    windows_path = PureWindowsPath(candidate)
    if path.is_absolute() or windows_path.is_absolute():
        raise ValueError("relative_path must be repository-relative, not absolute.")

    normalized_parts: list[str] = []
    for part in path.parts:
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError("relative_path must not contain parent-directory traversal.")
        normalized_parts.append(part)

    if not normalized_parts:
        raise ValueError("relative_path must resolve to a repository-relative file path.")

    return PurePosixPath(*normalized_parts).as_posix()


class BenchmarkQuerySourceKind(StrEnum):
    """Supported provenance for benchmark query cases."""

    HUMAN_AUTHORED = "human_authored"
    SYNTHETIC_REVIEWED = "synthetic_reviewed"


class BenchmarkRelevanceJudgment(BaseModel):
    """One expected relevant target anchored to a stable repository-relative locator."""

    model_config = ConfigDict(extra="forbid")

    relative_path: str
    language: SourceLanguage | None = None
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    relevance_grade: int = Field(ge=1)

    @field_validator("relative_path", mode="before")
    @classmethod
    def _normalize_relative_path(cls, value: str | Path) -> str:
        return normalize_benchmark_relative_path(value)

    @model_validator(mode="after")
    def _validate_line_span(self) -> BenchmarkRelevanceJudgment:
        if (self.start_line is None) != (self.end_line is None):
            raise ValueError("Line anchors must provide both start_line and end_line together.")

        if self.start_line is not None and self.end_line is not None:
            if self.end_line < self.start_line:
                raise ValueError("Line anchors must satisfy end_line >= start_line.")

        return self


class BenchmarkQueryCase(BaseModel):
    """One benchmark query plus its expected relevance judgments."""

    model_config = ConfigDict(extra="forbid")

    query_id: str
    query_text: str
    source_kind: BenchmarkQuerySourceKind
    tags: list[str] = Field(default_factory=list)
    judgments: list[BenchmarkRelevanceJudgment] = Field(min_length=1)

    @field_validator("query_id", "query_text", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: str | None, info: Any) -> str:
        return _normalize_required_text(value, field_name=info.field_name)

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, value: list[str] | None) -> list[str]:
        if value in (None, ""):
            return []
        normalized_tags = [_normalize_required_text(tag, field_name="tag") for tag in value]
        return normalized_tags


class BenchmarkDatasetDocument(BaseModel):
    """Canonical benchmark dataset document loaded from authored JSON input."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"]
    dataset_id: str
    dataset_version: str
    description: str | None = None
    notes: str | None = None
    cases: list[BenchmarkQueryCase] = Field(min_length=1)

    @field_validator("dataset_id", "dataset_version", mode="before")
    @classmethod
    def _normalize_required_fields(cls, value: str | None, info: Any) -> str:
        return _normalize_required_text(value, field_name=info.field_name)

    @field_validator("description", "notes", mode="before")
    @classmethod
    def _normalize_optional_fields(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)

    @model_validator(mode="after")
    def _validate_unique_query_ids(self) -> BenchmarkDatasetDocument:
        seen_query_ids: set[str] = set()
        duplicate_query_ids: list[str] = []
        for case in self.cases:
            if case.query_id in seen_query_ids:
                duplicate_query_ids.append(case.query_id)
                continue
            seen_query_ids.add(case.query_id)

        if duplicate_query_ids:
            duplicates = ", ".join(sorted(set(duplicate_query_ids)))
            raise ValueError(f"Duplicate query_id values are not allowed: {duplicates}")

        return self


class LoadBenchmarkDatasetRequest(BaseModel):
    """Input DTO for loading one benchmark dataset file."""

    model_config = ConfigDict(extra="forbid")

    dataset_path: Path


class BenchmarkDatasetSummary(BaseModel):
    """Concise metadata derived from one validated benchmark dataset."""

    model_config = ConfigDict(extra="forbid")

    dataset_path: Path
    schema_version: str = BENCHMARK_DATASET_SCHEMA_VERSION
    dataset_id: str
    dataset_version: str
    case_count: int
    judgment_count: int
    dataset_fingerprint: str


class LoadBenchmarkDatasetResult(BaseModel):
    """Output DTO for a successful benchmark dataset load."""

    model_config = ConfigDict(extra="forbid")

    dataset: BenchmarkDatasetDocument
    summary: BenchmarkDatasetSummary


def build_benchmark_dataset_canonical_json(dataset: BenchmarkDatasetDocument) -> str:
    """Serialize the benchmark dataset deterministically for hashing and persistence."""

    return json.dumps(
        dataset.model_dump(mode="json"),
        separators=(",", ":"),
        sort_keys=True,
    )


def build_benchmark_dataset_fingerprint(dataset: BenchmarkDatasetDocument) -> str:
    """Derive the stable dataset fingerprint from the canonical dataset payload."""

    return hashlib.sha256(
        build_benchmark_dataset_canonical_json(dataset).encode("utf-8")
    ).hexdigest()


__all__ = [
    "BENCHMARK_DATASET_SCHEMA_VERSION",
    "BenchmarkDatasetDocument",
    "BenchmarkDatasetSummary",
    "BenchmarkQueryCase",
    "BenchmarkQuerySourceKind",
    "BenchmarkRelevanceJudgment",
    "LoadBenchmarkDatasetRequest",
    "LoadBenchmarkDatasetResult",
    "build_benchmark_dataset_canonical_json",
    "build_benchmark_dataset_fingerprint",
    "normalize_benchmark_relative_path",
]
