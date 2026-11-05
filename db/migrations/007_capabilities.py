"""
Migration 007: capabilities
Creates dynamic capability registry tables tracking skill maturity levels.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "capabilities",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("level", sa.String(30), nullable=False, server_default="EXPERIMENTAL"),  # MISSING, EXPERIMENTAL, BASIC, ADVANCED, ELITE
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("required_tools", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("success_rate", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_capabilities_name", "capabilities", ["name"])
    op.create_index("ix_capabilities_level", "capabilities", ["level"])
    op.create_index("ix_capabilities_category", "capabilities", ["category"])


def downgrade() -> None:
    op.drop_table("capabilities")
