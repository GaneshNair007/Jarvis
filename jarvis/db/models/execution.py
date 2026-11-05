"""
SQLAlchemy 2.x Execution Model for JARVIS
Records every tool call, latency, input payload, and output artifact for telemetry and debugging.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jarvis.db.models.base import Base, GUID, UniversalJSON


class ExecutionModel(Base):
    __tablename__ = "executions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID, sa.ForeignKey("agents.id", ondelete="SET NULL"), index=True, nullable=True)
    tool_name: Mapped[str] = mapped_column(sa.String(100), index=True, nullable=False)
    input_data: Mapped[Dict[str, Any]] = mapped_column(UniversalJSON, default=dict, nullable=False)
    output_data: Mapped[Dict[str, Any]] = mapped_column(UniversalJSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(20), default="SUCCESS", index=True, nullable=False)
    execution_time: Mapped[float] = mapped_column(sa.Float, default=0.0, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        index=True,
        nullable=False,
    )

    # Relationships
    task: Mapped["TaskModel"] = relationship("TaskModel", back_populates="executions")
    agent: Mapped[Optional["AgentModel"]] = relationship("AgentModel", back_populates="executions")

