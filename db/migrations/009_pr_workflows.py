"""
Migration 009: pr_workflows
Creates tables for the Safe PR Workflow enforcing human gatekeeping and branch isolation.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pr_workflows",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("improvement_request_id", sa.UUID(as_uuid=True), sa.ForeignKey("improvement_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_name", sa.String(150), nullable=False),
        sa.Column("target_branch", sa.String(100), nullable=False, server_default="main"),
        sa.Column("pr_number", sa.Integer, nullable=True),
        sa.Column("pr_url", sa.String(255), nullable=True),
        sa.Column("workflow_state", sa.String(30), nullable=False, server_default="PROPOSED"),
        sa.Column("security_passed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("tests_passed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("approved_by", sa.String(100), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_pr_workflows_workflow_state", "pr_workflows", ["workflow_state"])
    op.create_index("ix_pr_workflows_improvement_request_id", "pr_workflows", ["improvement_request_id"])


def downgrade() -> None:
    op.drop_table("pr_workflows")
