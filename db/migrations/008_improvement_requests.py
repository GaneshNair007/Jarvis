"""
Migration 008: improvement_requests
Creates improvement requests emitted from reflections and capability gaps.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "improvement_requests",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("reflection_id", sa.UUID(as_uuid=True), sa.ForeignKey("reflections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("capability_id", sa.UUID(as_uuid=True), sa.ForeignKey("capabilities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("category", sa.String(50), nullable=False, server_default="architecture"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String(30), nullable=False, server_default="PROPOSED"),
        sa.Column("proposed_changes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_improvement_requests_status", "improvement_requests", ["status"])
    op.create_index("ix_improvement_requests_reflection_id", "improvement_requests", ["reflection_id"])
    op.create_index("ix_improvement_requests_capability_id", "improvement_requests", ["capability_id"])


def downgrade() -> None:
    op.drop_table("improvement_requests")
