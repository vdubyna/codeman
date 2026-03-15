"""Create retrieval strategy profiles table."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202603151000"
down_revision = "202603141500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "retrieval_strategy_profiles",
        sa.Column("name", sa.String(length=255), primary_key=True),
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("provider_id", sa.String(length=128), nullable=True),
        sa.Column("model_id", sa.String(length=255), nullable=True),
        sa.Column("model_version", sa.String(length=255), nullable=True),
        sa.Column("vector_engine", sa.String(length=64), nullable=False),
        sa.Column("vector_dimension", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_retrieval_strategy_profiles_name"),
    )
    op.create_index(
        "ix_retrieval_strategy_profiles_profile_id_name",
        "retrieval_strategy_profiles",
        ["profile_id", "name"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_retrieval_strategy_profiles_profile_id_name",
        table_name="retrieval_strategy_profiles",
    )
    op.drop_table("retrieval_strategy_profiles")
