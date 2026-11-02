"""
Migration 005: memories
Creates long-term episodic and semantic memory storage.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_task_id", sa.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("goal_id", sa.UUID(as_uuid=True), sa.ForeignKey("goals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category", sa.String(50), nullable=False),  # e.g. "engineering", "hackathon", "security"
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("importance_score", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("access_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_memories_category", "memories", ["category"])
    op.create_index("ix_memories_source_task_id", "memories", ["source_task_id"])
    op.create_index("ix_memories_goal_id", "memories", ["goal_id"])


def downgrade() -> None:
    op.drop_table("memories")
