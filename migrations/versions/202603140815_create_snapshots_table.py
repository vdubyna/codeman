"""Create snapshots table for immutable repository manifests."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202603140815"
down_revision = "202603140040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "snapshots",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "repository_id",
            sa.String(length=32),
            sa.ForeignKey("repositories.id"),
            nullable=False,
        ),
        sa.Column("revision_identity", sa.String(length=255), nullable=False),
        sa.Column("revision_source", sa.String(length=64), nullable=False),
        sa.Column("manifest_path", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("snapshots")
