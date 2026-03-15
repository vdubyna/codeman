"""Load and validate authored benchmark dataset documents."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from codeman.contracts.errors import ErrorCode
from codeman.contracts.evaluation import (
    BenchmarkDatasetDocument,
    BenchmarkDatasetSummary,
    LoadBenchmarkDatasetRequest,
    LoadBenchmarkDatasetResult,
    build_benchmark_dataset_fingerprint,
)

__all__ = [
    "BenchmarkDatasetInvalidJsonError",
    "BenchmarkDatasetLoadError",
    "BenchmarkDatasetPathNotFileError",
    "BenchmarkDatasetPathNotFoundError",
    "BenchmarkDatasetUnsupportedFormatError",
    "BenchmarkDatasetValidationError",
    "LoadBenchmarkDatasetUseCase",
]


class BenchmarkDatasetLoadError(Exception):
    """Base exception for benchmark dataset loading and validation failures."""

    exit_code = 59
    error_code = ErrorCode.BENCHMARK_DATASET_LOAD_FAILED

    def __init__(self, message: str, *, details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class BenchmarkDatasetPathNotFoundError(BenchmarkDatasetLoadError):
    """Raised when the requested benchmark dataset path does not exist."""

    exit_code = 60
    error_code = ErrorCode.BENCHMARK_DATASET_PATH_NOT_FOUND


class BenchmarkDatasetPathNotFileError(BenchmarkDatasetLoadError):
    """Raised when the requested benchmark dataset path is not a file."""

    exit_code = 61
    error_code = ErrorCode.BENCHMARK_DATASET_PATH_NOT_FILE


class BenchmarkDatasetUnsupportedFormatError(BenchmarkDatasetLoadError):
    """Raised when the requested benchmark dataset is not a JSON file."""

    exit_code = 62
    error_code = ErrorCode.BENCHMARK_DATASET_UNSUPPORTED_FORMAT


class BenchmarkDatasetInvalidJsonError(BenchmarkDatasetLoadError):
    """Raised when the benchmark dataset file cannot be parsed as JSON."""

    exit_code = 63
    error_code = ErrorCode.BENCHMARK_DATASET_INVALID_JSON


class BenchmarkDatasetValidationError(BenchmarkDatasetLoadError):
    """Raised when the benchmark dataset document violates the contract schema."""

    exit_code = 64
    error_code = ErrorCode.BENCHMARK_DATASET_VALIDATION_FAILED


def _format_error_location(location: tuple[Any, ...]) -> str:
    """Convert a Pydantic error location into a stable dotted field path."""

    if not location:
        return "dataset"
    return ".".join(str(part) for part in location)


def _extract_query_id(raw_payload: Any, location: tuple[Any, ...]) -> str | None:
    """Resolve the query_id for a case-scoped validation error when possible."""

    if not isinstance(raw_payload, dict):
        return None

    if len(location) < 2 or location[0] != "cases" or not isinstance(location[1], int):
        return None

    cases = raw_payload.get("cases")
    if not isinstance(cases, list) or location[1] >= len(cases):
        return None

    case_payload = cases[location[1]]
    if not isinstance(case_payload, dict):
        return None

    query_id = case_payload.get("query_id")
    if not isinstance(query_id, str):
        return None

    normalized_query_id = query_id.strip()
    return normalized_query_id or None


def _find_duplicate_query_ids(raw_payload: Any) -> list[str]:
    """Return duplicate non-blank query ids from the raw JSON payload."""

    if not isinstance(raw_payload, dict):
        return []

    cases = raw_payload.get("cases")
    if not isinstance(cases, list):
        return []

    seen_query_ids: set[str] = set()
    duplicates: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            continue
        query_id = case.get("query_id")
        if not isinstance(query_id, str):
            continue
        normalized_query_id = query_id.strip()
        if not normalized_query_id:
            continue
        if normalized_query_id in seen_query_ids:
            duplicates.add(normalized_query_id)
            continue
        seen_query_ids.add(normalized_query_id)

    return sorted(duplicates)


def _build_validation_details(
    *,
    dataset_path: Path,
    raw_payload: Any,
    validation_error: ValidationError,
) -> dict[str, Any]:
    """Build compact, actionable validation details for operator-facing failures."""

    duplicate_query_ids = _find_duplicate_query_ids(raw_payload)
    errors: list[dict[str, str]] = []
    duplicate_error_added = False

    for error in validation_error.errors():
        location = tuple(error.get("loc", ()))
        entry: dict[str, str] = {
            "field": _format_error_location(location),
            "message": error["msg"],
        }

        if query_id := _extract_query_id(raw_payload, location):
            entry["query_id"] = query_id

        if duplicate_query_ids and entry["field"] == "dataset":
            for query_id in duplicate_query_ids:
                errors.append(
                    {
                        "field": "cases.query_id",
                        "message": f"Duplicate query_id '{query_id}' is not allowed.",
                        "query_id": query_id,
                    }
                )
            duplicate_error_added = True
            continue

        errors.append(entry)

    if duplicate_query_ids and not duplicate_error_added:
        for query_id in duplicate_query_ids:
            errors.append(
                {
                    "field": "cases.query_id",
                    "message": f"Duplicate query_id '{query_id}' is not allowed.",
                    "query_id": query_id,
                }
            )

    if not errors:
        errors.append(
            {
                "field": "dataset",
                "message": "Benchmark dataset validation failed.",
            }
        )

    return {
        "dataset_path": str(dataset_path),
        "errors": errors,
    }


@dataclass(slots=True)
class LoadBenchmarkDatasetUseCase:
    """Load a benchmark dataset JSON document and return validated metadata."""

    def execute(self, request: LoadBenchmarkDatasetRequest) -> LoadBenchmarkDatasetResult:
        """Validate the authored dataset path, JSON payload, and benchmark contracts."""

        dataset_path = request.dataset_path.expanduser()

        try:
            resolved_path = dataset_path.resolve(strict=True)
        except FileNotFoundError as exc:
            raise BenchmarkDatasetPathNotFoundError(
                f"Benchmark dataset file was not found: {dataset_path}",
                details={"dataset_path": str(dataset_path)},
            ) from exc

        if not resolved_path.is_file():
            raise BenchmarkDatasetPathNotFileError(
                f"Benchmark dataset path must be a file: {resolved_path}",
                details={"dataset_path": str(resolved_path)},
            )

        if resolved_path.suffix.lower() != ".json":
            raise BenchmarkDatasetUnsupportedFormatError(
                f"Benchmark dataset files must use the .json extension: {resolved_path}",
                details={"dataset_path": str(resolved_path)},
            )

        try:
            raw_document = resolved_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise BenchmarkDatasetLoadError(
                f"Benchmark dataset file could not be read: {resolved_path}",
                details={"dataset_path": str(resolved_path)},
            ) from exc

        try:
            dataset = BenchmarkDatasetDocument.model_validate_json(raw_document)
        except ValidationError as exc:
            if any(error["type"] == "json_invalid" for error in exc.errors()):
                raise BenchmarkDatasetInvalidJsonError(
                    f"Benchmark dataset file is not valid JSON: {resolved_path}",
                    details={"dataset_path": str(resolved_path)},
                ) from exc

            raw_payload = json.loads(raw_document)
            details = _build_validation_details(
                dataset_path=resolved_path,
                raw_payload=raw_payload,
                validation_error=exc,
            )
            first_error = details["errors"][0]
            raise BenchmarkDatasetValidationError(
                "Benchmark dataset validation failed for "
                f"{resolved_path}: {first_error['field']} - {first_error['message']}",
                details=details,
            ) from exc

        summary = BenchmarkDatasetSummary(
            dataset_path=resolved_path,
            schema_version=dataset.schema_version,
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.dataset_version,
            case_count=len(dataset.cases),
            judgment_count=sum(len(case.judgments) for case in dataset.cases),
            dataset_fingerprint=build_benchmark_dataset_fingerprint(dataset),
        )
        return LoadBenchmarkDatasetResult(dataset=dataset, summary=summary)
