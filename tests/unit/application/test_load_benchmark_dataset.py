from __future__ import annotations

import json
from pathlib import Path

import pytest

from codeman.application.evaluation.load_benchmark_dataset import (
    BenchmarkDatasetInvalidJsonError,
    BenchmarkDatasetPathNotFileError,
    BenchmarkDatasetPathNotFoundError,
    BenchmarkDatasetUnsupportedFormatError,
    BenchmarkDatasetValidationError,
    LoadBenchmarkDatasetUseCase,
)
from codeman.contracts.errors import ErrorCode
from codeman.contracts.evaluation import LoadBenchmarkDatasetRequest


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


def write_dataset(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_load_benchmark_dataset_returns_validated_dataset_and_summary(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.json"
    write_dataset(dataset_path, build_valid_dataset_payload())
    use_case = LoadBenchmarkDatasetUseCase()

    result = use_case.execute(LoadBenchmarkDatasetRequest(dataset_path=dataset_path))

    assert result.dataset.dataset_id == "mixed-stack-golden"
    assert result.summary.dataset_path == dataset_path.resolve()
    assert result.summary.schema_version == "1"
    assert result.summary.case_count == 1
    assert result.summary.judgment_count == 1
    assert len(result.summary.dataset_fingerprint) == 64


def test_load_benchmark_dataset_rejects_missing_path(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.json"
    use_case = LoadBenchmarkDatasetUseCase()

    with pytest.raises(BenchmarkDatasetPathNotFoundError) as exc_info:
        use_case.execute(LoadBenchmarkDatasetRequest(dataset_path=missing_path))

    assert exc_info.value.error_code == ErrorCode.BENCHMARK_DATASET_PATH_NOT_FOUND
    assert str(missing_path) in exc_info.value.message


def test_load_benchmark_dataset_rejects_directory_path(tmp_path: Path) -> None:
    use_case = LoadBenchmarkDatasetUseCase()

    with pytest.raises(BenchmarkDatasetPathNotFileError) as exc_info:
        use_case.execute(LoadBenchmarkDatasetRequest(dataset_path=tmp_path))

    assert exc_info.value.error_code == ErrorCode.BENCHMARK_DATASET_PATH_NOT_FILE


def test_load_benchmark_dataset_rejects_unsupported_extension(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.yaml"
    write_dataset(dataset_path, build_valid_dataset_payload())
    use_case = LoadBenchmarkDatasetUseCase()

    with pytest.raises(BenchmarkDatasetUnsupportedFormatError) as exc_info:
        use_case.execute(LoadBenchmarkDatasetRequest(dataset_path=dataset_path))

    assert exc_info.value.error_code == ErrorCode.BENCHMARK_DATASET_UNSUPPORTED_FORMAT


def test_load_benchmark_dataset_rejects_invalid_json(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text('{"schema_version":"1",', encoding="utf-8")
    use_case = LoadBenchmarkDatasetUseCase()

    with pytest.raises(BenchmarkDatasetInvalidJsonError) as exc_info:
        use_case.execute(LoadBenchmarkDatasetRequest(dataset_path=dataset_path))

    assert exc_info.value.error_code == ErrorCode.BENCHMARK_DATASET_INVALID_JSON
    assert exc_info.value.details == {"dataset_path": str(dataset_path.resolve())}


def test_load_benchmark_dataset_rejects_incomplete_cases_with_actionable_details(
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "dataset.json"
    payload = build_valid_dataset_payload()
    del payload["cases"][0]["query_text"]
    write_dataset(dataset_path, payload)
    use_case = LoadBenchmarkDatasetUseCase()

    with pytest.raises(BenchmarkDatasetValidationError) as exc_info:
        use_case.execute(LoadBenchmarkDatasetRequest(dataset_path=dataset_path))

    assert exc_info.value.error_code == ErrorCode.BENCHMARK_DATASET_VALIDATION_FAILED
    assert exc_info.value.details == {
        "dataset_path": str(dataset_path.resolve()),
        "errors": [
            {
                "field": "cases.0.query_text",
                "message": "Field required",
                "query_id": "home-controller",
            }
        ],
    }


def test_load_benchmark_dataset_rejects_duplicate_query_ids_with_query_context(
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "dataset.json"
    payload = build_valid_dataset_payload()
    payload["cases"].append(
        {
            "query_id": "home-controller",
            "query_text": "Find the controller again",
            "source_kind": "human_authored",
            "judgments": [
                {
                    "relative_path": "assets/app.js",
                    "language": "javascript",
                    "start_line": 1,
                    "end_line": 3,
                    "relevance_grade": 1,
                }
            ],
        }
    )
    write_dataset(dataset_path, payload)
    use_case = LoadBenchmarkDatasetUseCase()

    with pytest.raises(BenchmarkDatasetValidationError) as exc_info:
        use_case.execute(LoadBenchmarkDatasetRequest(dataset_path=dataset_path))

    assert exc_info.value.error_code == ErrorCode.BENCHMARK_DATASET_VALIDATION_FAILED
    assert exc_info.value.details == {
        "dataset_path": str(dataset_path.resolve()),
        "errors": [
            {
                "field": "cases.query_id",
                "message": "Duplicate query_id 'home-controller' is not allowed.",
                "query_id": "home-controller",
            }
        ],
    }


def test_seeded_mixed_stack_dataset_targets_real_fixture_files_and_line_spans() -> None:
    fixture_path = Path("tests/fixtures/queries/mixed_stack_fixture_golden_queries.json").resolve()
    repository_root = Path("tests/fixtures/repositories/mixed_stack_fixture").resolve()
    use_case = LoadBenchmarkDatasetUseCase()

    result = use_case.execute(LoadBenchmarkDatasetRequest(dataset_path=fixture_path))

    assert {case.source_kind for case in result.dataset.cases} == {"human_authored"}
    assert {
        judgment.relative_path for case in result.dataset.cases for judgment in case.judgments
    } == {
        "src/Controller/HomeController.php",
        "assets/app.js",
        "templates/page.html.twig",
        "public/index.html",
    }

    for case in result.dataset.cases:
        for judgment in case.judgments:
            target_path = repository_root / judgment.relative_path
            assert target_path.exists()
            assert target_path.is_file()
            assert target_path.relative_to(repository_root).as_posix() == judgment.relative_path

            target_lines = target_path.read_text(encoding="utf-8").splitlines()
            assert judgment.start_line is not None
            assert judgment.end_line is not None
            assert 1 <= judgment.start_line <= judgment.end_line <= len(target_lines)
