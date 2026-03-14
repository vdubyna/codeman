"""Create source_files table for extracted source inventory metadata."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202603140930"
down_revision = "202603140815"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_files",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.String(length=32),
            sa.ForeignKey("snapshots.id"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            sa.String(length=32),
            sa.ForeignKey("repositories.id"),
            nullable=False,
        ),
        sa.Column("relative_path", sa.String(length=2048), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "snapshot_id",
            "relative_path",
            name="uq_source_files_snapshot_relative_path",
        ),
    )


def downgrade() -> None:
    op.drop_table("source_files")
