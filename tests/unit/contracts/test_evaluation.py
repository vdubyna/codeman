from __future__ import annotations

import pytest
from pydantic import ValidationError

from codeman.contracts.evaluation import (
    BenchmarkDatasetDocument,
    GenerateBenchmarkReportRequest,
    build_benchmark_dataset_canonical_json,
    build_benchmark_dataset_fingerprint,
)


def build_valid_dataset_payload() -> dict[str, object]:
    return {
        "schema_version": "1",
        "dataset_id": "mixed-stack-golden",
        "dataset_version": "2026-03-15",
        "description": "Fixture benchmark dataset.",
        "cases": [
            {
                "query_id": "home-controller",
                "query_text": "Find the home controller action",
                "source_kind": "human_authored",
                "tags": ["php", "controller"],
                "judgments": [
                    {
                        "relative_path": "src/Controller/HomeController.php",
                        "language": "php",
                        "start_line": 5,
                        "end_line": 10,
                        "relevance_grade": 2,
                    }
                ],
            }
        ],
    }


def test_benchmark_dataset_normalizes_text_fields_and_relative_paths() -> None:
    payload = build_valid_dataset_payload()
    payload["dataset_id"] = " mixed-stack-golden "
    payload["dataset_version"] = " 2026-03-15 "
    payload["cases"] = [
        {
            "query_id": " home-controller ",
            "query_text": "  Find the home controller action  ",
            "source_kind": "human_authored",
            "tags": [" php ", "controller"],
            "judgments": [
                {
                    "relative_path": "./src\\Controller//HomeController.php",
                    "language": "php",
                    "start_line": 5,
                    "end_line": 10,
                    "relevance_grade": 2,
                }
            ],
        }
    ]

    dataset = BenchmarkDatasetDocument.model_validate(payload)

    assert dataset.dataset_id == "mixed-stack-golden"
    assert dataset.dataset_version == "2026-03-15"
    assert dataset.cases[0].query_id == "home-controller"
    assert dataset.cases[0].query_text == "Find the home controller action"
    assert dataset.cases[0].tags == ["php", "controller"]
    assert dataset.cases[0].judgments[0].relative_path == "src/Controller/HomeController.php"


def test_benchmark_dataset_canonical_json_is_deterministic_regardless_of_key_order() -> None:
    first = BenchmarkDatasetDocument.model_validate(build_valid_dataset_payload())
    second = BenchmarkDatasetDocument.model_validate(
        {
            "dataset_version": "2026-03-15",
            "cases": [
                {
                    "source_kind": "human_authored",
                    "judgments": [
                        {
                            "end_line": 10,
                            "relevance_grade": 2,
                            "start_line": 5,
                            "language": "php",
                            "relative_path": "src/Controller/HomeController.php",
                        }
                    ],
                    "query_text": "Find the home controller action",
                    "query_id": "home-controller",
                    "tags": ["php", "controller"],
                }
            ],
            "description": "Fixture benchmark dataset.",
            "dataset_id": "mixed-stack-golden",
            "schema_version": "1",
        }
    )

    assert build_benchmark_dataset_canonical_json(first) == build_benchmark_dataset_canonical_json(
        second
    )
    assert build_benchmark_dataset_fingerprint(first) == build_benchmark_dataset_fingerprint(second)


def test_benchmark_dataset_rejects_blank_query_text() -> None:
    payload = build_valid_dataset_payload()
    payload["cases"][0]["query_text"] = "   "

    with pytest.raises(ValidationError) as exc_info:
        BenchmarkDatasetDocument.model_validate(payload)

    assert "query_text" in str(exc_info.value)


def test_benchmark_dataset_rejects_empty_judgments() -> None:
    payload = build_valid_dataset_payload()
    payload["cases"][0]["judgments"] = []

    with pytest.raises(ValidationError) as exc_info:
        BenchmarkDatasetDocument.model_validate(payload)

    assert "judgments" in str(exc_info.value)


def test_benchmark_dataset_rejects_invalid_source_kind() -> None:
    payload = build_valid_dataset_payload()
    payload["cases"][0]["source_kind"] = "provider_generated"

    with pytest.raises(ValidationError) as exc_info:
        BenchmarkDatasetDocument.model_validate(payload)

    assert "source_kind" in str(exc_info.value)


@pytest.mark.parametrize(
    ("start_line", "end_line"),
    [
        (None, 10),
        (5, None),
        (0, 10),
        (10, 5),
    ],
)
def test_benchmark_dataset_rejects_invalid_line_spans(
    start_line: int | None,
    end_line: int | None,
) -> None:
    payload = build_valid_dataset_payload()
    payload["cases"][0]["judgments"][0]["start_line"] = start_line
    payload["cases"][0]["judgments"][0]["end_line"] = end_line

    with pytest.raises(ValidationError) as exc_info:
        BenchmarkDatasetDocument.model_validate(payload)

    assert "line" in str(exc_info.value)


def test_benchmark_dataset_rejects_parent_traversal_in_relative_path() -> None:
    payload = build_valid_dataset_payload()
    payload["cases"][0]["judgments"][0]["relative_path"] = "../secrets.txt"

    with pytest.raises(ValidationError) as exc_info:
        BenchmarkDatasetDocument.model_validate(payload)

    assert "relative_path" in str(exc_info.value)


def test_benchmark_dataset_rejects_windows_absolute_path() -> None:
    payload = build_valid_dataset_payload()
    payload["cases"][0]["judgments"][0]["relative_path"] = r"C:\repo\HomeController.php"

    with pytest.raises(ValidationError) as exc_info:
        BenchmarkDatasetDocument.model_validate(payload)

    assert "relative_path" in str(exc_info.value)


def test_benchmark_dataset_accepts_relevance_grade_above_previous_cap() -> None:
    payload = build_valid_dataset_payload()
    payload["cases"][0]["judgments"][0]["relevance_grade"] = 10

    dataset = BenchmarkDatasetDocument.model_validate(payload)

    assert dataset.cases[0].judgments[0].relevance_grade == 10


def test_generate_benchmark_report_request_normalizes_run_id() -> None:
    request = GenerateBenchmarkReportRequest.model_validate({"run_id": " run-123 "})

    assert request.run_id == "run-123"


def test_generate_benchmark_report_request_rejects_blank_run_id() -> None:
    with pytest.raises(ValidationError) as exc_info:
        GenerateBenchmarkReportRequest.model_validate({"run_id": "   "})

    assert "run_id" in str(exc_info.value)


@pytest.mark.parametrize("relevance_grade", [0, -1])
def test_benchmark_dataset_rejects_invalid_relevance_grades(relevance_grade: int) -> None:
    payload = build_valid_dataset_payload()
    payload["cases"][0]["judgments"][0]["relevance_grade"] = relevance_grade

    with pytest.raises(ValidationError) as exc_info:
        BenchmarkDatasetDocument.model_validate(payload)

    assert "relevance_grade" in str(exc_info.value)
