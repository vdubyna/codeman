"""Add snapshot indexing markers and re-index run attribution."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202603141330"
down_revision = "202603141215"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "snapshots",
        sa.Column("chunk_generation_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "snapshots",
        sa.Column("indexing_config_fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_table(
        "reindex_runs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "repository_id",
            sa.String(length=32),
            sa.ForeignKey("repositories.id"),
            nullable=False,
        ),
        sa.Column(
            "previous_snapshot_id",
            sa.String(length=32),
            sa.ForeignKey("snapshots.id"),
            nullable=False,
        ),
        sa.Column(
            "result_snapshot_id",
            sa.String(length=32),
            sa.ForeignKey("snapshots.id"),
            nullable=False,
        ),
        sa.Column("previous_revision_identity", sa.String(length=255), nullable=False),
        sa.Column("result_revision_identity", sa.String(length=255), nullable=False),
        sa.Column("previous_config_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("current_config_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("change_reason", sa.String(length=64), nullable=False),
        sa.Column("source_files_reused", sa.Integer(), nullable=False),
        sa.Column("source_files_rebuilt", sa.Integer(), nullable=False),
        sa.Column("source_files_removed", sa.Integer(), nullable=False),
        sa.Column("chunks_reused", sa.Integer(), nullable=False),
        sa.Column("chunks_rebuilt", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("reindex_runs")
    op.drop_column("snapshots", "indexing_config_fingerprint")
    op.drop_column("snapshots", "chunk_generation_completed_at")
