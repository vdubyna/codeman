"""Create benchmark runs table."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202603151500"
down_revision = "202603151330"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "benchmark_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "repository_id",
            sa.String(length=32),
            sa.ForeignKey("repositories.id"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            sa.String(length=32),
            sa.ForeignKey("snapshots.id"),
            nullable=False,
        ),
        sa.Column("retrieval_mode", sa.String(length=32), nullable=False),
        sa.Column("dataset_id", sa.String(length=255), nullable=False),
        sa.Column("dataset_version", sa.String(length=255), nullable=False),
        sa.Column("dataset_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("completed_case_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("artifact_path", sa.String(length=2048), nullable=True),
        sa.Column("error_code", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_benchmark_runs_repository_started_at",
        "benchmark_runs",
        ["repository_id", "started_at"],
    )
    op.create_index(
        "ix_benchmark_runs_dataset_fingerprint",
        "benchmark_runs",
        ["dataset_fingerprint"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_benchmark_runs_dataset_fingerprint",
        table_name="benchmark_runs",
    )
    op.drop_index(
        "ix_benchmark_runs_repository_started_at",
        table_name="benchmark_runs",
    )
    op.drop_table("benchmark_runs")
