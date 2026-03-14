"""Create lexical index build attribution table."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202603141430"
down_revision = "202603141330"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lexical_index_builds",
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
        sa.Column("indexing_config_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("lexical_engine", sa.String(length=64), nullable=False),
        sa.Column("tokenizer_spec", sa.String(length=255), nullable=False),
        sa.Column("indexed_fields_json", sa.String(length=4096), nullable=False),
        sa.Column("chunks_indexed", sa.Integer(), nullable=False),
        sa.Column("index_path", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_lexical_index_builds_repository_created_at",
        "lexical_index_builds",
        ["repository_id", "created_at"],
    )
    op.create_index(
        "ix_lexical_index_builds_snapshot_created_at",
        "lexical_index_builds",
        ["snapshot_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lexical_index_builds_snapshot_created_at",
        table_name="lexical_index_builds",
    )
    op.drop_index(
        "ix_lexical_index_builds_repository_created_at",
        table_name="lexical_index_builds",
    )
    op.drop_table("lexical_index_builds")
