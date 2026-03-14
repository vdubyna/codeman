"""Create semantic index build attribution table."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202603141500"
down_revision = "202603141430"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "semantic_index_builds",
        sa.Column("id", sa.String(length=32), primary_key=True),
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
        sa.Column("revision_identity", sa.String(length=255), nullable=False),
        sa.Column("revision_source", sa.String(length=64), nullable=False),
        sa.Column("semantic_config_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("model_version", sa.String(length=255), nullable=False),
        sa.Column("is_external_provider", sa.Integer(), nullable=False),
        sa.Column("vector_engine", sa.String(length=64), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("artifact_path", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_semantic_index_builds_repository_config_created_at",
        "semantic_index_builds",
        ["repository_id", "semantic_config_fingerprint", "created_at"],
    )
    op.create_index(
        "ix_semantic_index_builds_snapshot_config_created_at",
        "semantic_index_builds",
        ["snapshot_id", "semantic_config_fingerprint", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_semantic_index_builds_snapshot_config_created_at",
        table_name="semantic_index_builds",
    )
    op.drop_index(
        "ix_semantic_index_builds_repository_config_created_at",
        table_name="semantic_index_builds",
    )
    op.drop_table("semantic_index_builds")
