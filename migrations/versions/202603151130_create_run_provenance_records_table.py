"""Create run provenance records table."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202603151130"
down_revision = "202603151000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_provenance_records",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("workflow_type", sa.String(length=64), nullable=False),
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
            nullable=True,
        ),
        sa.Column("configuration_id", sa.String(length=64), nullable=False),
        sa.Column("indexing_config_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("semantic_config_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("provider_id", sa.String(length=128), nullable=True),
        sa.Column("model_id", sa.String(length=255), nullable=True),
        sa.Column("model_version", sa.String(length=255), nullable=True),
        sa.Column("effective_config_json", sa.Text(), nullable=False),
        sa.Column("workflow_context_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_run_provenance_records_repository_created_at",
        "run_provenance_records",
        ["repository_id", "created_at"],
    )
    op.create_index(
        "ix_run_provenance_records_configuration_id",
        "run_provenance_records",
        ["configuration_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_run_provenance_records_configuration_id",
        table_name="run_provenance_records",
    )
    op.drop_index(
        "ix_run_provenance_records_repository_created_at",
        table_name="run_provenance_records",
    )
    op.drop_table("run_provenance_records")
