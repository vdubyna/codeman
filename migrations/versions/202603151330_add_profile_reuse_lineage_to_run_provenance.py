"""Add selected-profile reuse lineage fields to run provenance records."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202603151330"
down_revision = "202603151130"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "run_provenance_records",
        sa.Column("base_profile_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "run_provenance_records",
        sa.Column("base_profile_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "run_provenance_records",
        sa.Column(
            "reuse_kind",
            sa.String(length=32),
            nullable=False,
            server_default="ad_hoc",
        ),
    )


def downgrade() -> None:
    op.drop_column("run_provenance_records", "reuse_kind")
    op.drop_column("run_provenance_records", "base_profile_name")
    op.drop_column("run_provenance_records", "base_profile_id")
