"""Evaluation application use cases."""

from codeman.application.evaluation.calculate_benchmark_metrics import (
    BenchmarkArtifactCorruptError,
    BenchmarkArtifactMissingError,
    BenchmarkMetricsError,
    BenchmarkMetricsInputShapeError,
    BenchmarkRunIncompleteError,
    BenchmarkRunNotFoundError,
    CalculateBenchmarkMetricsUseCase,
)
from codeman.application.evaluation.generate_report import (
    BenchmarkReportArtifactCorruptError,
    BenchmarkReportError,
    BenchmarkReportMetricsArtifactMissingError,
    BenchmarkReportProvenanceUnavailableError,
    BenchmarkReportRawArtifactMissingError,
    BenchmarkReportRunIncompleteError,
    BenchmarkReportRunNotFoundError,
    GenerateBenchmarkReportUseCase,
)
from codeman.application.evaluation.load_benchmark_dataset import (
    BenchmarkDatasetInvalidJsonError,
    BenchmarkDatasetLoadError,
    BenchmarkDatasetPathNotFileError,
    BenchmarkDatasetPathNotFoundError,
    BenchmarkDatasetUnsupportedFormatError,
    BenchmarkDatasetValidationError,
    LoadBenchmarkDatasetUseCase,
)
from codeman.application.evaluation.run_benchmark import (
    BenchmarkRunBaselineMissingError,
    BenchmarkRunError,
    BenchmarkRunModeUnavailableError,
    BenchmarkRunRepositoryNotRegisteredError,
    RunBenchmarkUseCase,
)

__all__ = [
    "BenchmarkArtifactCorruptError",
    "BenchmarkArtifactMissingError",
    "BenchmarkDatasetInvalidJsonError",
    "BenchmarkDatasetLoadError",
    "BenchmarkDatasetPathNotFileError",
    "BenchmarkDatasetPathNotFoundError",
    "BenchmarkDatasetUnsupportedFormatError",
    "BenchmarkDatasetValidationError",
    "BenchmarkMetricsError",
    "BenchmarkMetricsInputShapeError",
    "BenchmarkReportArtifactCorruptError",
    "BenchmarkReportError",
    "BenchmarkReportMetricsArtifactMissingError",
    "BenchmarkReportProvenanceUnavailableError",
    "BenchmarkReportRawArtifactMissingError",
    "BenchmarkReportRunIncompleteError",
    "BenchmarkReportRunNotFoundError",
    "BenchmarkRunBaselineMissingError",
    "BenchmarkRunError",
    "BenchmarkRunIncompleteError",
    "BenchmarkRunModeUnavailableError",
    "BenchmarkRunRepositoryNotRegisteredError",
    "BenchmarkRunNotFoundError",
    "CalculateBenchmarkMetricsUseCase",
    "GenerateBenchmarkReportUseCase",
    "LoadBenchmarkDatasetUseCase",
    "RunBenchmarkUseCase",
]
