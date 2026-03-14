"""Create repositories table for local repository registration."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202603140040"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("repository_name", sa.String(length=255), nullable=False),
        sa.Column("canonical_path", sa.String(length=2048), nullable=False, unique=True),
        sa.Column("requested_path", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("repositories")
