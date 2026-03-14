"""Add source inventory extraction marker to snapshots."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202603141215"
down_revision = "202603141100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "snapshots",
        sa.Column("source_inventory_extracted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("snapshots", "source_inventory_extracted_at")
