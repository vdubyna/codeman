"""Benchmark dataset contracts and deterministic dataset helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codeman.contracts.repository import SourceLanguage
from codeman.contracts.retrieval import (
    HybridRetrievalBuildContext,
    LexicalRetrievalBuildContext,
    RetrievalMode,
    RetrievalRepositoryContext,
    RetrievalSnapshotContext,
    RunHybridQueryResult,
    RunLexicalQueryResult,
    RunSemanticQueryResult,
    SemanticRetrievalBuildContext,
)

BENCHMARK_DATASET_SCHEMA_VERSION = "1"
BENCHMARK_RUN_ARTIFACT_SCHEMA_VERSION = "1"
BENCHMARK_METRICS_ARTIFACT_SCHEMA_VERSION = "1"


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


class BenchmarkRunStatus(StrEnum):
    """Truthful lifecycle states for one benchmark execution."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


BenchmarkRetrievalBuildContext = (
    LexicalRetrievalBuildContext | SemanticRetrievalBuildContext | HybridRetrievalBuildContext
)
BenchmarkCaseRetrievalResult = RunLexicalQueryResult | RunSemanticQueryResult | RunHybridQueryResult


class RunBenchmarkRequest(BaseModel):
    """Input DTO for executing one benchmark dataset against one retrieval mode."""

    model_config = ConfigDict(extra="forbid")

    repository_id: str
    dataset_path: Path
    retrieval_mode: RetrievalMode
    max_results: int = Field(default=20, gt=0, le=100)


class BenchmarkRunRecord(BaseModel):
    """Compact persisted row and operator-facing summary for one benchmark run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    repository_id: str
    snapshot_id: str
    retrieval_mode: RetrievalMode
    dataset_id: str
    dataset_version: str
    dataset_fingerprint: str
    case_count: int = Field(ge=0)
    completed_case_count: int = Field(ge=0)
    status: BenchmarkRunStatus
    artifact_path: Path | None = None
    evaluated_at_k: int | None = Field(default=None, gt=0, le=100)
    recall_at_k: float | None = Field(default=None, ge=0.0, le=1.0)
    mrr: float | None = Field(default=None, ge=0.0, le=1.0)
    ndcg_at_k: float | None = Field(default=None, ge=0.0, le=1.0)
    query_latency_mean_ms: float | None = Field(default=None, ge=0.0)
    query_latency_p95_ms: int | None = Field(default=None, ge=0)
    lexical_index_duration_ms: int | None = Field(default=None, ge=0)
    semantic_index_duration_ms: int | None = Field(default=None, ge=0)
    derived_index_duration_ms: int | None = Field(default=None, ge=0)
    metrics_artifact_path: Path | None = None
    metrics_computed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_completion_state(self) -> BenchmarkRunRecord:
        if self.completed_case_count > self.case_count:
            raise ValueError("completed_case_count must not exceed case_count.")

        if self.status == BenchmarkRunStatus.RUNNING and self.completed_at is not None:
            raise ValueError("Running benchmark runs must not set completed_at.")

        if self.status != BenchmarkRunStatus.RUNNING and self.completed_at is None:
            raise ValueError("Completed benchmark runs must set completed_at.")

        if (
            self.status == BenchmarkRunStatus.SUCCEEDED
            and self.completed_case_count != self.case_count
        ):
            raise ValueError("Succeeded benchmark runs must complete every benchmark case.")

        return self


class BenchmarkAggregateMetrics(BaseModel):
    """Aggregate retrieval-quality metrics for one benchmark run."""

    model_config = ConfigDict(extra="forbid")

    recall_at_k: float = Field(ge=0.0, le=1.0)
    mrr: float = Field(ge=0.0, le=1.0)
    ndcg_at_k: float = Field(ge=0.0, le=1.0)


class BenchmarkQueryLatencySummary(BaseModel):
    """Comparable latency summary for one benchmark run."""

    model_config = ConfigDict(extra="forbid")

    sample_count: int = Field(ge=0)
    min_ms: int | None = Field(default=None, ge=0)
    mean_ms: float | None = Field(default=None, ge=0.0)
    median_ms: float | None = Field(default=None, ge=0.0)
    p95_ms: int | None = Field(default=None, ge=0)
    max_ms: int | None = Field(default=None, ge=0)


class BenchmarkIndexingDurationSummary(BaseModel):
    """Comparable indexing-duration summary for one benchmark run."""

    model_config = ConfigDict(extra="forbid")

    lexical_build_duration_ms: int | None = Field(default=None, ge=0)
    semantic_build_duration_ms: int | None = Field(default=None, ge=0)
    derived_total_build_duration_ms: int | None = Field(default=None, ge=0)


class BenchmarkPerformanceSummary(BaseModel):
    """Aggregate performance metrics for one benchmark run."""

    model_config = ConfigDict(extra="forbid")

    query_latency: BenchmarkQueryLatencySummary
    indexing: BenchmarkIndexingDurationSummary


class BenchmarkJudgmentMetricResult(BaseModel):
    """Matching detail for one authored judgment during metric calculation."""

    model_config = ConfigDict(extra="forbid")

    judgment_index: int = Field(ge=0)
    relative_path: str
    language: SourceLanguage | None = None
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    relevance_grade: int = Field(ge=1)
    matched_result_ranks: list[int] = Field(default_factory=list)
    first_matched_rank: int | None = Field(default=None, ge=1)
    gain_rank: int | None = Field(default=None, ge=1)


class BenchmarkCaseMetricResult(BaseModel):
    """Per-case metrics retained for later reporting and inspection."""

    model_config = ConfigDict(extra="forbid")

    query_id: str
    source_kind: BenchmarkQuerySourceKind
    evaluated_at_k: int = Field(gt=0, le=100)
    relevant_judgment_count: int = Field(ge=0)
    matched_judgment_count: int = Field(ge=0)
    first_relevant_rank: int | None = Field(default=None, ge=1)
    recall_at_k: float = Field(ge=0.0, le=1.0)
    reciprocal_rank: float = Field(ge=0.0, le=1.0)
    ndcg_at_k: float = Field(ge=0.0, le=1.0)
    query_latency_ms: int = Field(ge=0)
    judgments: list[BenchmarkJudgmentMetricResult] = Field(default_factory=list)


class BenchmarkMetricsSummary(BaseModel):
    """Compact benchmark-metrics summary surfaced to operators and automation."""

    model_config = ConfigDict(extra="forbid")

    evaluated_at_k: int = Field(gt=0, le=100)
    metrics: BenchmarkAggregateMetrics
    performance: BenchmarkPerformanceSummary
    metrics_computed_at: datetime
    artifact_path: Path | None = None


class CalculateBenchmarkMetricsRequest(BaseModel):
    """Input DTO for calculating metrics for one completed benchmark run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str


class CalculateBenchmarkMetricsResult(BaseModel):
    """Output DTO for benchmark metrics calculation."""

    model_config = ConfigDict(extra="forbid")

    run: BenchmarkRunRecord
    metrics: BenchmarkMetricsSummary


class RunBenchmarkResult(BaseModel):
    """Output DTO for successful or failed benchmark execution attempts."""

    model_config = ConfigDict(extra="forbid")

    run: BenchmarkRunRecord
    repository: RetrievalRepositoryContext
    snapshot: RetrievalSnapshotContext
    build: BenchmarkRetrievalBuildContext
    dataset: BenchmarkDatasetSummary
    metrics: BenchmarkMetricsSummary | None = None


class BenchmarkRunFailure(BaseModel):
    """Stable failure metadata persisted inside raw benchmark artifacts."""

    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    phase: str | None = None
    failed_case_query_id: str | None = None
    details: dict[str, Any] | None = None


class BenchmarkCaseExecutionArtifact(BaseModel):
    """Normalized raw output for one executed benchmark case."""

    model_config = ConfigDict(extra="forbid")

    query_id: str
    source_kind: BenchmarkQuerySourceKind
    judgments: list[BenchmarkRelevanceJudgment] = Field(default_factory=list)
    result: BenchmarkCaseRetrievalResult


class BenchmarkRunArtifactDocument(BaseModel):
    """Raw benchmark artifact stored under the workspace artifact root."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = BENCHMARK_RUN_ARTIFACT_SCHEMA_VERSION
    run: BenchmarkRunRecord
    repository: RetrievalRepositoryContext
    snapshot: RetrievalSnapshotContext
    build: BenchmarkRetrievalBuildContext
    dataset: BenchmarkDatasetDocument
    dataset_summary: BenchmarkDatasetSummary
    max_results: int = Field(gt=0, le=100)
    cases: list[BenchmarkCaseExecutionArtifact] = Field(default_factory=list)
    failure: BenchmarkRunFailure | None = None


class BenchmarkMetricsArtifactDocument(BaseModel):
    """Benchmark metrics artifact stored separately from raw execution evidence."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = BENCHMARK_METRICS_ARTIFACT_SCHEMA_VERSION
    run: BenchmarkRunRecord
    repository: RetrievalRepositoryContext
    snapshot: RetrievalSnapshotContext
    build: BenchmarkRetrievalBuildContext
    dataset: BenchmarkDatasetSummary
    summary: BenchmarkMetricsSummary
    cases: list[BenchmarkCaseMetricResult] = Field(default_factory=list)


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
    "BENCHMARK_METRICS_ARTIFACT_SCHEMA_VERSION",
    "BENCHMARK_RUN_ARTIFACT_SCHEMA_VERSION",
    "BenchmarkAggregateMetrics",
    "BenchmarkCaseExecutionArtifact",
    "BenchmarkCaseMetricResult",
    "BenchmarkCaseRetrievalResult",
    "BenchmarkDatasetDocument",
    "BenchmarkDatasetSummary",
    "BenchmarkIndexingDurationSummary",
    "BenchmarkJudgmentMetricResult",
    "BenchmarkMetricsArtifactDocument",
    "BenchmarkMetricsSummary",
    "BenchmarkPerformanceSummary",
    "BenchmarkQueryCase",
    "BenchmarkQuerySourceKind",
    "BenchmarkQueryLatencySummary",
    "BenchmarkRelevanceJudgment",
    "BenchmarkRetrievalBuildContext",
    "BenchmarkRunArtifactDocument",
    "BenchmarkRunFailure",
    "BenchmarkRunRecord",
    "BenchmarkRunStatus",
    "CalculateBenchmarkMetricsRequest",
    "CalculateBenchmarkMetricsResult",
    "LoadBenchmarkDatasetRequest",
    "LoadBenchmarkDatasetResult",
    "RunBenchmarkRequest",
    "RunBenchmarkResult",
    "build_benchmark_dataset_canonical_json",
    "build_benchmark_dataset_fingerprint",
    "normalize_benchmark_relative_path",
]
