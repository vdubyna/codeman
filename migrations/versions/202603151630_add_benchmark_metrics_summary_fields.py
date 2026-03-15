"""Add benchmark metrics summary and build duration fields."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202603151630"
down_revision = "202603151500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lexical_index_builds",
        sa.Column("build_duration_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "semantic_index_builds",
        sa.Column("build_duration_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "benchmark_runs",
        sa.Column("evaluated_at_k", sa.Integer(), nullable=True),
    )
    op.add_column(
        "benchmark_runs",
        sa.Column("recall_at_k", sa.Float(), nullable=True),
    )
    op.add_column(
        "benchmark_runs",
        sa.Column("mrr", sa.Float(), nullable=True),
    )
    op.add_column(
        "benchmark_runs",
        sa.Column("ndcg_at_k", sa.Float(), nullable=True),
    )
    op.add_column(
        "benchmark_runs",
        sa.Column("query_latency_mean_ms", sa.Float(), nullable=True),
    )
    op.add_column(
        "benchmark_runs",
        sa.Column("query_latency_p95_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "benchmark_runs",
        sa.Column("lexical_index_duration_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "benchmark_runs",
        sa.Column("semantic_index_duration_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "benchmark_runs",
        sa.Column("derived_index_duration_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "benchmark_runs",
        sa.Column("metrics_artifact_path", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "benchmark_runs",
        sa.Column("metrics_computed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("benchmark_runs", "metrics_computed_at")
    op.drop_column("benchmark_runs", "metrics_artifact_path")
    op.drop_column("benchmark_runs", "derived_index_duration_ms")
    op.drop_column("benchmark_runs", "semantic_index_duration_ms")
    op.drop_column("benchmark_runs", "lexical_index_duration_ms")
    op.drop_column("benchmark_runs", "query_latency_p95_ms")
    op.drop_column("benchmark_runs", "query_latency_mean_ms")
    op.drop_column("benchmark_runs", "ndcg_at_k")
    op.drop_column("benchmark_runs", "mrr")
    op.drop_column("benchmark_runs", "recall_at_k")
    op.drop_column("benchmark_runs", "evaluated_at_k")
    op.drop_column("semantic_index_builds", "build_duration_ms")
    op.drop_column("lexical_index_builds", "build_duration_ms")
