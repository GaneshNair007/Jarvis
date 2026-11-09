"""Add LangGraph checkpoint tables and voice session tracking

Revision ID: 0003_graph_voice
Revises: 0002_integrations_plugins
Create Date: 2026-10-31 00:01:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_graph_voice"
down_revision: Union[str, Sequence[str], None] = "0002_integrations_plugins"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # ── graph_checkpoints: LangGraph state snapshots (SQLite fallback) ─────────
    # NOTE: The PostgreSQL checkpointer manages its own tables via saver.setup().
    # This table is the SQLite equivalent for offline / test mode.
    op.create_table(
        "graph_checkpoints",
        sa.Column("thread_id", sa.String(128), nullable=False),
        sa.Column("checkpoint_ns", sa.String(128), nullable=False, server_default=""),
        sa.Column("checkpoint_id", sa.String(64), nullable=False),
        sa.Column("parent_checkpoint_id", sa.String(64), nullable=True),
        sa.Column("type", sa.String(32), nullable=True),
        sa.Column("checkpoint_blob", sa.LargeBinary(), nullable=False),
        sa.Column("metadata_blob", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_ns", "checkpoint_id"),
    )
    op.create_index("ix_graph_checkpoints_thread", "graph_checkpoints", ["thread_id"])

    # ── voice_sessions: track STT/TTS voice interaction sessions ──────────────
    op.create_table(
        "voice_sessions",
        sa.Column("session_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("trigger_type", sa.String(32), nullable=False),   # wake_word | push_to_talk | api
        sa.Column("stt_engine", sa.String(64), nullable=True),      # faster_whisper | whisper_api | sapi
        sa.Column("tts_engine", sa.String(64), nullable=True),      # piper | sapi | elevenlabs
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("audio_file_path", sa.String(512), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("wer_score", sa.Float(), nullable=True),          # word error rate if evaluated
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("completed_at", sa.Float(), nullable=True),
    )
    op.create_index("ix_voice_sessions_user_id", "voice_sessions", ["user_id"])

    # ── kill_switch_events: immutable log of all kill switch activations ───────
    op.create_table(
        "kill_switch_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("activated_by", sa.String(64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("deactivated_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("deactivated_at", sa.Float(), nullable=True),
    )

    # ── rate_limit_events: track rate limiting per integration ─────────────────
    op.create_table(
        "rate_limit_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("integration_id", sa.String(64), nullable=False),
        sa.Column("endpoint", sa.String(256), nullable=True),
        sa.Column("requests_in_window", sa.Integer(), nullable=False),
        sa.Column("limit_rpm", sa.Integer(), nullable=False),
        sa.Column("throttled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_rate_limit_integration", "rate_limit_events", ["integration_id"])

    # ── cost_governor_events: per-request cost tracking ───────────────────────
    op.create_table(
        "cost_governor_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("task_id", sa.String(64), nullable=True),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("budget_remaining_usd", sa.Float(), nullable=True),
        sa.Column("budget_gate_passed", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_cost_governor_task", "cost_governor_events", ["task_id"])


def downgrade() -> None:
    op.drop_table("cost_governor_events")
    op.drop_table("rate_limit_events")
    op.drop_table("kill_switch_events")
    op.drop_table("voice_sessions")
    op.drop_table("graph_checkpoints")
