"""
Migration 001: goals
Creates the primary goals table for high-level user and system objectives.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False, server_default="user"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="HIGH"),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("target_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_goals_status", "goals", ["status"])
    op.create_index("ix_goals_priority", "goals", ["priority"])


def downgrade() -> None:
    op.drop_index("ix_goals_priority", table_name="goals")
    op.drop_index("ix_goals_status", table_name="goals")
    op.drop_table("goals")
