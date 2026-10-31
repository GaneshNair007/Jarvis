"""Add integrations registry, plugin catalog, agent plans, and finance ledger tables

Revision ID: 0002_integrations_plugins
Revises: 0dc406230232
Create Date: 2026-10-31 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "0002_integrations_plugins"
down_revision: Union[str, Sequence[str], None] = "0dc406230232"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add new tables for integrations, plugins, agent plans, and finance."""

    # ── integrations: live registry of all connected external services ─────────
    op.create_table(
        "integrations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("danger_level", sa.String(32), nullable=False, server_default="low"),
        sa.Column("approval_tier", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("connected", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("last_connected_at", sa.Float(), nullable=True),
        sa.Column("credentials_stored", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("health_status", sa.String(32), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
    )

    # ── integration_events: connection/disconnection/error audit trail ─────────
    op.create_table(
        "integration_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("integration_id", sa.String(64), sa.ForeignKey("integrations.id"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),  # CONNECT | DISCONNECT | ERROR | HEALTH_CHECK
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_integration_events_integration_id", "integration_events", ["integration_id"])

    # ── plugins: catalog of loaded plugins ────────────────────────────────────
    op.create_table(
        "plugins",
        sa.Column("plugin_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("plugin_dir", sa.String(512), nullable=False),
        sa.Column("entry_point", sa.String(128), nullable=True),
        sa.Column("approval_tier", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("tags_json", sa.Text(), nullable=True),
        sa.Column("powers_json", sa.Text(), nullable=True),
        sa.Column("load_errors_json", sa.Text(), nullable=True),
        sa.Column("loaded_at", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=True),
    )

    # ── agent_plans: multi-agent plan execution records ────────────────────────
    op.create_table(
        "agent_plans",
        sa.Column("plan_id", sa.String(64), primary_key=True),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("complexity", sa.String(16), nullable=True),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("total_estimated_cost_usd", sa.Float(), nullable=True, server_default="0"),
        sa.Column("total_actual_cost_usd", sa.Float(), nullable=True, server_default="0"),
        sa.Column("steps_count", sa.Integer(), nullable=True),
        sa.Column("steps_completed", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("completed_at", sa.Float(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
    )

    # ── agent_steps: individual steps within an agent plan ────────────────────
    op.create_table(
        "agent_steps",
        sa.Column("step_id", sa.String(64), primary_key=True),
        sa.Column("plan_id", sa.String(64), sa.ForeignKey("agent_plans.plan_id"), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assigned_role", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("input_json", sa.Text(), nullable=True),
        sa.Column("output_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True, server_default="0"),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("completed_at", sa.Float(), nullable=True),
    )
    op.create_index("ix_agent_steps_plan_id", "agent_steps", ["plan_id"])

    # ── critic_reports: quality review records from CriticAgent ───────────────
    op.create_table(
        "critic_reports",
        sa.Column("report_id", sa.String(64), primary_key=True),
        sa.Column("task_id", sa.String(64), nullable=True),
        sa.Column("step_id", sa.String(64), nullable=True),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("retry_recommended", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("issues_json", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=False),
    )

    # ── finance_quotes: cached market quotes ──────────────────────────────────
    op.create_table(
        "finance_quotes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=True, server_default="USD"),
        sa.Column("source", sa.String(32), nullable=True),
        sa.Column("market_cap", sa.Float(), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("fetched_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_finance_quotes_symbol", "finance_quotes", ["symbol"])

    # ── paper_trades: paper trading order book ─────────────────────────────────
    op.create_table(
        "paper_trades",
        sa.Column("order_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("action", sa.String(8), nullable=False),      # BUY | SELL
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("total_value", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_paper_trades_symbol", "paper_trades", ["symbol"])

    # ── finance_ledger: double-entry accounting ────────────────────────────────
    op.create_table(
        "finance_ledger",
        sa.Column("txn_id", sa.String(64), primary_key=True),
        sa.Column("debit_account", sa.String(128), nullable=False),
        sa.Column("credit_account", sa.String(128), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("reference_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_finance_ledger_debit", "finance_ledger", ["debit_account"])

    # ── calendar_events: cached/synced calendar entries ───────────────────────
    op.create_table(
        "calendar_events",
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("calendar_id", sa.String(256), nullable=True),
        sa.Column("backend", sa.String(32), nullable=True),      # google | caldav
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(512), nullable=True),
        sa.Column("start_time", sa.String(64), nullable=False),
        sa.Column("end_time", sa.String(64), nullable=False),
        sa.Column("attendees_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("synced_at", sa.Float(), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=True),
    )
    op.create_index("ix_calendar_events_start", "calendar_events", ["start_time"])

    # ── smart_home_states: cached Home Assistant entity states ────────────────
    op.create_table(
        "smart_home_states",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("entity_id", sa.String(128), nullable=False, unique=True),
        sa.Column("domain", sa.String(32), nullable=True),
        sa.Column("friendly_name", sa.String(256), nullable=True),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("attributes_json", sa.Text(), nullable=True),
        sa.Column("last_changed", sa.String(64), nullable=True),
        sa.Column("synced_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_smart_home_entity_id", "smart_home_states", ["entity_id"])


def downgrade() -> None:
    """Remove tables added in revision 0002."""
    op.drop_table("smart_home_states")
    op.drop_table("calendar_events")
    op.drop_table("finance_ledger")
    op.drop_table("paper_trades")
    op.drop_table("finance_quotes")
    op.drop_table("critic_reports")
    op.drop_table("agent_steps")
    op.drop_table("agent_plans")
    op.drop_table("plugins")
    op.drop_table("integration_events")
    op.drop_table("integrations")
