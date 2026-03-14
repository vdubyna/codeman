"""Create chunks table for retrieval chunk metadata."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202603141100"
down_revision = "202603140930"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chunks",
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
        sa.Column(
            "source_file_id",
            sa.String(length=64),
            sa.ForeignKey("source_files.id"),
            nullable=False,
        ),
        sa.Column("relative_path", sa.String(length=2048), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("strategy", sa.String(length=64), nullable=False),
        sa.Column("serialization_version", sa.String(length=16), nullable=False),
        sa.Column("source_content_hash", sa.String(length=64), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("start_byte", sa.Integer(), nullable=False),
        sa.Column("end_byte", sa.Integer(), nullable=False),
        sa.Column("payload_path", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("chunks")
